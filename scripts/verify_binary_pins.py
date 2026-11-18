#!/usr/bin/env python3
"""
Role: Supply-Chain Binary Pin & Digest Verifier for Antigravity Web Hub (ACE-WS-01).
Purpose: Resolves official Antigravity Hub and CLI release URLs strictly from allowlisted
  Google Cloud hosts, validates version/execution-ID syntax, downloads archives over HTTPS,
  and cryptographically verifies SHA-512 (CLI manifest), optional pinned SHA-256, and GCS
  object x-goog-hash MD5 integrity BEFORE archive extraction.
How It Is Used: Invoked by scripts/install.sh prior to tar extraction, or tested via
  `python3 -B scripts/verify_binary_pins.py --self-test`.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

ALLOWED_RELEASE_HOSTS = frozenset({
    "storage.googleapis.com",
    "antigravity-hub-auto-updater-974169037036.us-central1.run.app",
    "antigravity-cli-auto-updater-974169037036.us-central1.run.app",
    "antigravity.static.usercontent.goog",
})

CLI_MANIFEST_URL = (
    "https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/linux_amd64.json"
)
HUB_GCS_PREFIX = "https://storage.googleapis.com/antigravity-public/antigravity-hub/"
CLI_GCS_PREFIX = "https://storage.googleapis.com/antigravity-public/antigravity-cli/"

VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}$")
EXEC_ID_RE = re.compile(r"^[0-9]+$")


def validate_release_url(url: str, required_prefix: Optional[str] = None) -> str:
    """Enforces HTTPS, strict host allowlist, zero path traversal, and optional prefix."""
    parsed = urllib.parse.urlparse(url or "")
    if parsed.scheme != "https":
        raise ValueError(f"Non-HTTPS release URL rejected: {url}")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_RELEASE_HOSTS:
        raise ValueError(f"Disallowed release host '{host}' in URL: {url}")
    if ".." in parsed.path or "\\" in parsed.path:
        raise ValueError(f"Path traversal rejected in URL: {url}")
    if required_prefix and not url.startswith(required_prefix):
        raise ValueError(f"URL outside required prefix '{required_prefix}': {url}")
    return url


def validate_release_ids(version: str, exec_id: str) -> Tuple[str, str]:
    """Validates numeric release version and execution ID before URL interpolation."""
    v = (version or "").strip()
    e = (exec_id or "").strip()
    if not VERSION_RE.match(v):
        raise ValueError(f"Invalid release version token: {v!r}")
    if not EXEC_ID_RE.match(e):
        raise ValueError(f"Invalid execution_id token: {e!r}")
    return v, e


def normalize_hex_digest(raw_digest: str, expected_hex_len: int) -> str:
    """Accepts lowercase/uppercase hex or base64-encoded digest strings."""
    cleaned = (raw_digest or "").strip()
    if re.fullmatch(rf"[0-9a-fA-F]{{{expected_hex_len}}}", cleaned):
        return cleaned.lower()
    decoded = base64.b64decode(cleaned, validate=True).hex().lower()
    if len(decoded) != expected_hex_len:
        raise ValueError(f"Digest length mismatch after base64 decode: got {len(decoded)} hex chars")
    return decoded


def verify_file_digest(path: str, expected_hex: str, algo: str = "sha256") -> str:
    """Streams a local file and asserts exact cryptographic digest match."""
    expected_len = {"md5": 32, "sha256": 64, "sha512": 128}.get(algo.lower())
    if not expected_len:
        raise ValueError(f"Unsupported digest algorithm: {algo}")
    norm_expected = normalize_hex_digest(expected_hex, expected_len)
    h = hashlib.new(algo.lower())
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1048576), b""):
            h.update(chunk)
    actual = h.hexdigest().lower()
    if actual != norm_expected:
        raise ValueError(f"{algo.lower()} mismatch for {path}: expected={norm_expected} actual={actual}")
    return actual


def _extract_gcs_md5_header(headers) -> str:
    """Parses x-goog-hash: md5=<base64> response headers returned by GCS."""
    raw_headers = headers.get_all("x-goog-hash") if hasattr(headers, "get_all") else []
    for line in raw_headers or []:
        for part in str(line).split(","):
            part = part.strip()
            if part.startswith("md5="):
                return part[4:].strip()
    return ""


def download_and_verify(
    url: str,
    dest_path: str,
    required_prefix: Optional[str] = None,
    expected_sha512: str = "",
    expected_sha256: str = "",
    timeout_sec: int = 180,
) -> Dict[str, str]:
    """Downloads an allowlisted HTTPS artifact to dest_path and verifies digests before returning."""
    validate_release_url(url, required_prefix=required_prefix)
    req = urllib.request.Request(url, headers={"User-Agent": "antigravity-web-hub-verifier/3.10"})
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    md5 = hashlib.md5()
    tmp_path = f"{dest_path}.part.{os.getpid()}"
    gcs_md5 = ""
    total_bytes = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            final_url = resp.geturl()
            validate_release_url(final_url, required_prefix=required_prefix)
            gcs_md5 = _extract_gcs_md5_header(resp.headers)
            with open(tmp_path, "wb") as out:
                while True:
                    chunk = resp.read(1048576)
                    if not chunk:
                        break
                    out.write(chunk)
                    sha256.update(chunk)
                    sha512.update(chunk)
                    md5.update(chunk)
                    total_bytes += len(chunk)
        if total_bytes == 0:
            raise ValueError(f"Downloaded empty artifact from {url}")
        if expected_sha512:
            verify_file_digest(tmp_path, expected_sha512, "sha512")
        if expected_sha256:
            verify_file_digest(tmp_path, expected_sha256, "sha256")
        if gcs_md5:
            norm_gcs_md5 = normalize_hex_digest(gcs_md5, 32)
            if md5.hexdigest().lower() != norm_gcs_md5:
                raise ValueError(f"GCS x-goog-hash md5 mismatch: header={norm_gcs_md5} actual={md5.hexdigest()}")
        os.replace(tmp_path, dest_path)
        return {
            "url": url,
            "dest": dest_path,
            "bytes": str(total_bytes),
            "sha256": sha256.hexdigest(),
            "sha512": sha512.hexdigest(),
            "gcs_md5_verified": str(bool(gcs_md5)).lower(),
        }
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def fetch_verified_cli(dest_path: str, manifest_url: str = CLI_MANIFEST_URL) -> Dict[str, str]:
    """Resolves the signed official CLI manifest and enforces SHA-512 before writing dest_path."""
    validate_release_url(manifest_url)
    with urllib.request.urlopen(manifest_url, timeout=20) as resp:
        manifest = json.loads(resp.read().decode("utf-8"))
    url = str(manifest.get("url") or "").strip()
    sha512 = str(manifest.get("sha512") or "").strip()
    version = str(manifest.get("version") or "").strip()
    if not url or not sha512:
        raise ValueError("CLI manifest missing required url or sha512 field")
    res = download_and_verify(
        url=url,
        dest_path=dest_path,
        required_prefix=CLI_GCS_PREFIX,
        expected_sha512=sha512,
        timeout_sec=120,
    )
    res["version"] = version
    return res


def fetch_verified_hub(
    version: str,
    exec_id: str,
    dest_path: str,
    expected_sha256: str = "",
) -> Dict[str, str]:
    """Downloads Antigravity Hub tarball from allowlisted GCS prefix with transport & optional pin checks."""
    v, e = validate_release_ids(version, exec_id)
    url = f"{HUB_GCS_PREFIX}{v}-{e}/linux-x64/Antigravity.tar.gz"
    res = download_and_verify(
        url=url,
        dest_path=dest_path,
        required_prefix=HUB_GCS_PREFIX,
        expected_sha256=expected_sha256,
        timeout_sec=240,
    )
    res["version"] = v
    res["execution_id"] = e
    return res


def _self_test() -> int:
    validate_release_url(f"{HUB_GCS_PREFIX}2.33.0-4731201358004224/linux-x64/Antigravity.tar.gz", HUB_GCS_PREFIX)
    try:
        validate_release_url("https://evil.example.com/Antigravity.tar.gz", HUB_GCS_PREFIX)
        raise AssertionError("Disallowed host was not rejected")
    except ValueError:
        pass
    try:
        validate_release_url(f"{HUB_GCS_PREFIX}../escape/Antigravity.tar.gz", HUB_GCS_PREFIX)
        raise AssertionError("Traversal URL was not rejected")
    except ValueError:
        pass
    validate_release_ids("2.33.0", "4731201358004224")
    with tempfile.TemporaryDirectory() as td:
        sample = os.path.join(td, "sample.bin")
        payload = b"antigravity-verified-payload"
        with open(sample, "wb") as fh:
            fh.write(payload)
        h512 = hashlib.sha512(payload).hexdigest()
        h256 = hashlib.sha256(payload).hexdigest()
        assert verify_file_digest(sample, h512, "sha512") == h512
        assert verify_file_digest(sample, h256, "sha256") == h256
        b64_md5 = base64.b64encode(hashlib.md5(payload).digest()).decode("ascii")
        assert verify_file_digest(sample, b64_md5, "md5") == hashlib.md5(payload).hexdigest()
        try:
            verify_file_digest(sample, "0" * 64, "sha256")
            raise AssertionError("Mismatched digest was not rejected")
        except ValueError:
            pass
    print("verify_binary_pins.py self-test: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify & download allowlisted Antigravity release tarballs.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--mode", choices=["cli", "hub"], default="")
    parser.add_argument("--dest", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--exec-id", default="")
    parser.add_argument("--expected-sha256", default="")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()
    if args.mode == "cli":
        res = fetch_verified_cli(args.dest)
        print(json.dumps(res))
        return 0
    if args.mode == "hub":
        res = fetch_verified_hub(args.version, args.exec_id, args.dest, expected_sha256=args.expected_sha256)
        print(json.dumps(res))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
