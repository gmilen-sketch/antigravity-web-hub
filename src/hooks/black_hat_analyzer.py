#!/usr/bin/env python3
"""
Role: Clean-Room Repository IP, Secret, Binary & AST Safety Scanner (v3.9.0).
Purpose: Audits target files and directories for Python AST syntax errors, JSON validity,
  bare `except: pass` silent fallbacks, binary/bytecode artifacts outside `.git`, leaked
  workstation home directories, corporate domains/shortlinks/paths, hardcoded credentials,
  and one-way SHA-256 digests of prohibited internal codenames/tools/identifiers.
How It Is Used: Invoked via `python3 -B src/hooks/black_hat_analyzer.py --target .` in CI,
  `tests/test_autonomy_kg_hooks.py`, and pre-release clean-room certification sweeps.
"""

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from typing import Any, Dict, List

PROHIBITED_LEAK_PATTERNS = [
    (r"\bAKIA[0-9A-Z]{16}\b", "Hardcoded AWS access key ID"),
    (r"\bghp_[A-Za-z0-9_]{20,}\b", "Hardcoded GitHub personal access token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", "Hardcoded GitHub fine-grained token"),
    (r"\bAIza[0-9A-Za-z\-_]{35}\b", "Hardcoded Google Cloud API key"),
    (r"@[A-Za-z0-9.-]*google\.com\b", "Corporate email address leak"),
    (r"\b[A-Za-z0-9.-]*g\x6fogleplex\.com\b", "Internal corporate host leak"),
    (r"\b[A-Za-z0-9.-]*\.corp\.google\.com\b", "Internal corporate subdomain leak"),
    (r"\b[A-Za-z0-9.-]*\.c\.g\x6foglers\.com\b", "Internal workstation FQDN leak"),
    (r"\bsso://[A-Za-z0-9_./-]+", "Internal SSO repository URI leak"),
    (r"(?<![A-Za-z0-9_:])//depot/[A-Za-z0-9_./-]+", "Internal monorepo depot path leak"),
    (r"/google/src/(?:cloud|files|head)/", "Internal workstation mount path leak"),
    (r"\bcompany/teams/[A-Za-z0-9_./-]+", "Internal corporate team path leak"),
    (
        r"(?<![A-Za-z0-9_./:-])(?:go/[a-z0-9][a-z0-9_-]{2,}|b/\d{6,}|cl/\d{6,})\b",
        "Internal corporate shortlink or tracker ID leak",
    ),
]

PROHIBITED_BINARY_EXTENSIONS = (
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".whl", ".zip", ".tar", ".gz", ".tgz", ".deb", ".rpm",
)

# One-way SHA-256 digests of prohibited internal codenames, tool names, retired checkpoints, and personal/tenant IDs
PROHIBITED_TOKEN_SHA256 = {
    "026451766041c80355486ec0ac8646297bddc78374bb039a0c6da8a966dcbcd7",
    "05bc6fa1ff0770f5de13c86f1d27418c938adea2dac09bf99680e8c31bf89c1c",
    "068425c4fdd03f5fce5df0b3acef6750c138f40b730ec057c1b410cf34cb046d",
    "085dd84e04ce8c00f409f7923b6ea0a7104427c52717d12c441d0032e38e6494",
    "0d3f4b5cf006a8244eb77efe0a4732e4f61c4eded583fa7dfa3ee170b7c6b844",
    "121778aac180ffb910480e9c156737993f2e7ef1e43da192ceb3fbb6511e858b",
    "13da8580ec41963d03186bcd3edabd5b6868ac65721b8b05009742f4132e493c",
    "1637f2d1f2f6efe5ee593bca165f11c0cad8bde593fc0499edf50c668eaeda66",
    "1a594173df29beaf020ab42d3667f984659b298f3b73381b69aff73ee4cb7cc7",
    "1abd3be8267804007ea1a7cc37b21e75fba35b32523e6b9f1251439d221dbb47",
    "1dba1d0b2fb2c7a8ae4c601e019595b09e5fc8e9714afe9cb163ba1c90de6d20",
    "1ea9ccb8657801321ad969f574d3de77c1c466647844bf418645d88f2d8b368c",
    "1ebcaa8021b3bf85c6e16ff894b98e5f0741285afa9ecac7ee1d226ffe713f29",
    "244ea6f7756d1c5c09a4af114b6f8901654a873aeea75958fe0886bba6815491",
    "24e7bf7451f37f10121f46ff0bbce77e72e7913432593d740caf0695462f0ced",
    "2b1c46d5fcada05e9c9db17faa4371768e98f3afbbcf3a5dbd391310de7c4a3b",
    "2d46d9e693ae13a9c49e2e5689354847f2c9f2bcfea49f863ab762bf1fdf7582",
    "2e2943ed09299b1cecb996822bba5e6cebc97f30f3be8172cfa69d391274f079",
    "3013d0805994035600038bfa097483dbcc304d0c0e3496bb0b452bd5126a8b0f",
    "34f62330dab329804641a03da8056ae7a71e0010b541adef9dffbd0eda773ef8",
    "37c3219fd1059fb361dc07fa9d95fed9c12b7855d99bfd626336b9128eb4c59b",
    "3a4ef2f8983186e7303a3cc643be4a1600a79790d22c5d93d5bfb8a91f3a0af1",
    "3b3387b96d92bcc780d9e58b0c2845b07734a21ce41b8ff91c92ad24b720eb80",
    "3cd9c951954fb7c17dc2472c0c64914d7ea223b0c5c0135085cd5c987feea9e4",
    "3fe4c0dfdc77c371c44e1b449ac5bc25535232672784fb53c0cafbecdf07b97c",
    "46248ac689828800502186d8753cc5717c5c2b47712e8158705a510dc892f00b",
    "4aa2768e1515ce3f2ba78034ea57c7f4816057500e898b904de2b052a3cd6c69",
    "4acd0cdca1033d84298f2622a2dd0da33223037ddfbc6cea7330df0bf65a0cf9",
    "4c4e17432121eb59b4de9392a36040b5ea52d54bea30dbd262328c49ccf68312",
    "4cda13e9da6b18c130048cf552317c17dec815aa7a37571f67b691d4fe274110",
    "50081b0ded927135bd05e93d2c7f390b13cd374d00020367b5d4035d12461f1f",
    "546f028dac5bbe1b967cdb7009e03526d5ff2a29885e5d838d8599fefd46fad0",
    "55b5b346f53e638ca35ae0519f458c5f46308b98f6979a9719b4d0cac7f43f42",
    "58c942cd4ea1cbf7199a5faf099f2bf6bf1ed6a6735633e156ba35cb461c7a4e",
    "5f8943ba9f5820644ded25d08cef7c4ec1d6bd1e857d68d7cd21c5cb22f3069a",
    "5ffdc2e99ef60fb246b3dc1d0de39d6b6e6e938be64a85d5acac47328f037b36",
    "618f38273f37bf28e0dfdfe9c466a987ddd3d7ad64757136c44bd8a2bc2a8d2a",
    "6a6cb25e084f8559a36cd87f7d9913dd5360e534c7f39f6cbf86cf5814b83913",
    "6ae4163f29d4a1c8d76ac2fd00ec5c074c5601780c7512364ccf20551caafe37",
    "6b062a8c187a2e40a1b6391552bff6404617b5a3baea9d8763e0aa3efe620613",
    "7287afc74731c5aa749600569b97735f06e83c1faf1c7b7becc07a5e9a158cc6",
    "739de437a01cb18fdfa2af63e9fbb9eae7873bebf159a0187a37f0e645b537ea",
    "79eedaed2d9d011e9d3d54555bde3b3d6043b35094d477947146c384d525b4bd",
    "7a039460d488c46aab1a70265bf960d045684b20ff94c89e65a284f6a788a069",
    "7a58057b9700a3b6b81765f99daccd90380146e06ae5303db594f4eca5599364",
    "7abfe2408f385a6302690c6cfb3c7e091ff8877738bec527967d1dac67040dbe",
    "7d43247f52c56e7c5a16971d98552785ae640faf24f0f4518e320076b875d3a0",
    "7e692a6bd210312e9928fe2588676ec5efbaa4f1943682f83e6306b4a8dbb944",
    "809d703a0055b8c2db6ebcf5bfa3fc565f0b4d9b70626716572d08d548444cd7",
    "80f400c0518cd218b0c5af99959e5e35797ac378ffd72b55944132fd43d710a3",
    "84df8346dcb11faab6246fe89ddef174cc195787810b391130e676a721e03fda",
    "887e0b455907e2a0c8df6b582b88a310a1f4d38aa6212b7cf315d0f5b39c54a5",
    "8ec7a63946d6998c05ac5767119524dbd4acfa6ce2100ddc082fd2d859d4c567",
    "908ee8d0ce45017a9212a09c55272e7d9c77852218706c54e1264384429e4834",
    "96839b38daa19348e9b64431fe2a124c03c8b3fd64b53c1091218d952e621818",
    "96db16b696c381f13c20558a92e4c4cf73c67f8758a027e63f1d14f6c69e8694",
    "97897a111d485af1048bece173d2980a15870ca079281b79c7ca755356847602",
    "9827d7ffd6737fbbbfda3ebb9019b78297854485104192d4bf85ea86a3d9bd3c",
    "9918f0455cefecd78b99a6d8daf7da74732ccd50fdbafda860ecc0f050f2e725",
    "a2ccd9890912865ac499d9f9144df1a55649485311c724d8389370a19e2fec0d",
    "a394ba2d007ba8e8112f1f700052e4abfcd7a65ff5e3732ddf20df817f2f5018",
    "a63e3cd33fd7d9aeadaa209e754caa59b6134410dbfdb3921de04d110417d5ab",
    "a6564e8693e1bb6061b32cdd603af69ae6f0236460285fab84d8f40f31f01341",
    "a85225383333b5121c283ce29d19df80b965ab18c2005e36234b542317463bcb",
    "a993841015c2bd443458d35c51d2869d1dda3580d514143ec2f1f5b0aa8ec982",
    "ac463ac547d4f3089d4d3cf5d7e4a9bc478b30685fc2d7c41fedabcfd508af37",
    "ad351a045814b855d54c569d0acfeef5d2e2856403409df2d7c740594af962f1",
    "b55c51dc47b5dbc1729fba33d7e595b9706ff29665b686e5f4ff8d64a0595b46",
    "b58c68f3f56a4e014da7d9f3b8e9ece81447c19a230cab8c9dea2f076664c882",
    "b75d95b29a949da588bae22e6837f5352d01835f90f7a3384326dd0c59ab7eb9",
    "b7c5113c4bf3bbc0e4909bba5bd34a4a19826af7f87c1eef4ab3f5d1d69f3f92",
    "b9c6505df56123cfa556c00c2bd30dc0607c33505d579a1babe1a351ca1db7e8",
    "c855c7805c7816740364e948f2babe7cbc8b6317fc8e8784b0b62f7247f94281",
    "cebb544920c67648fd45a2a4aa536eb7bc50ad1f7506eaa85d762f8f32915981",
    "d291cb308c2e1d8ce9a65444ad1551243bdfe5df9033e0ec81c0b3ba6b4ed670",
    "d341aec24ff9578c4391328b2e1396d09fe568e967a022d7bbc08b98303412c1",
    "d43e610ed1d8b1bdf2fc1d636d5db802e331d6c3e8467e65f26b1ed874f5ad55",
    "d4e557e54c8189a8025951be03d071d009284fc9be6a8bf2f6dc7b22f53e900e",
    "d5b7b23e6461293a8a2b4e12c8dfbfa394e39f091f567b11f66b9baa3fc8e338",
    "d6bf0ec06b18bfc5489033c22bc53e15ded58840c85525b4df87eafb4ac2bb4c",
    "dbf0759caae83fe9f0d8c35c56f7bffb35d8b7a9b40ac612ecbc06e84b924fff",
    "dcc6cb19909102b1a7a6c3234148d726d7f324e9011be47aa4f50f9a3451e79e",
    "e027f8ef8add57ca1cabfb6a90a9bbe9d63ae8e08ca6f024b0daa7e8434cdede",
    "e115702a38a06500983c7efddc8abcb17c5fa9a016ee1da0a86facc86f4b05d9",
    "e134c033e88fbff499696afe2aa8744805969081fb2ef10369661c3e640082eb",
    "e1aafe66299f163ec01243b2ac0281f3023a809ab5ca9ed935328a05ac04e7ce",
    "e2657581fe469aaafbd93d93124a1de94671af12d8b65cc6c97eb2356e2518bd",
    "e3652ee763affcd38977b3519dcc1d0920b5348a6dea2e1739a91a572d271226",
    "e7e4deec233fd7e220b0754becfc11e010a33eb3ffd7f318d01a40d883402da3",
    "ef31a17cd31ff1fd12767f958fcdaf6f75f78ae51a4c648788295a51bcbe85ab",
    "f0ab296ac531c989a60fd0019c703a22e7af90ae83a10cb764679fd7f4c70ca7",
    "f4cdde86ce9ba1f27679ca97cd4412ffb8cbb02716a6f066339130d554160baf",
    "f4f90ccbf0a72670e8326ecfaf34df2e2c9fad52e3c133cac5ab6550ce3d9683",
    "fb80fbedb3d94a4d8e6c5650f5c731b7c853398941296deed7a849ae3d1b8f9e",
    "fcc72010527a8b1e70484b3d4de133ad8db9055754d18a945a894a945f3d5cc1",
}


def scan_ast_silent_fallbacks(source_code: str, filename: str = "<memory>") -> List[str]:
    """Scans Python AST for silent-fallback anti-patterns (bare except: pass)."""
    issues: List[str] = []
    try:
        tree = ast.parse(source_code, filename=filename)
    except SyntaxError as exc:
        return [f"{filename}:{exc.lineno}: SyntaxError: {exc.msg}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                if node.type is None:
                    issues.append(f"{filename}:{node.lineno}: Bare 'except: pass' silent fallback detected")
    return issues


def scan_target(target_path: str) -> Dict[str, Any]:
    py_files_checked = 0
    json_files_checked = 0
    syntax_errors: List[str] = []
    path_leaks: List[str] = []
    silent_fallbacks: List[str] = []

    if os.path.isfile(target_path):
        files_to_scan = [target_path]
    else:
        files_to_scan = []
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [
                d for d in dirs
                if d not in (".git", "node_modules", "__pycache__", "venv", ".venv", "bin", "assets", "builtin", "conversations", "brain")
            ]
            for fname in sorted(files):
                if fname == ".env" or fname.endswith((".db", ".pb")):
                    continue
                files_to_scan.append(os.path.join(root, fname))

    home_dir = os.path.expanduser("~")
    for fpath in files_to_scan:
        if os.path.abspath(fpath) == os.path.abspath(__file__):
            continue
        ext = os.path.splitext(fpath)[1].lower()
        if fpath.lower().endswith(PROHIBITED_BINARY_EXTENSIONS):
            path_leaks.append(f"{fpath}: Prohibited binary/archive/bytecode artifact ('{os.path.basename(fpath)}')")
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="strict") as f:
                content = f.read()
        except UnicodeDecodeError:
            path_leaks.append(f"{fpath}: Non-UTF-8 binary file detected outside allowed directories")
            continue
        except Exception:
            continue

        if ext == ".py":
            py_files_checked += 1
            try:
                ast.parse(content, filename=fpath)
            except SyntaxError as exc:
                syntax_errors.append(f"{fpath}:{exc.lineno}: {exc.msg}")
            silent_fallbacks.extend(scan_ast_silent_fallbacks(content, fpath))
        elif ext == ".json":
            json_files_checked += 1
            try:
                json.loads(content)
            except Exception as exc:
                syntax_errors.append(f"{fpath}: JSON error: {exc}")

        if home_dir and len(home_dir) > 6 and home_dir in content:
            path_leaks.append(f"{fpath}: Hardcoded workstation home directory")
        for pattern, desc in PROHIBITED_LEAK_PATTERNS:
            if re.search(pattern, content):
                path_leaks.append(f"{fpath}: {desc}")
        for token in set(re.findall(r"[A-Za-z0-9._-]{4,}", content)):
            clean_tok = token.strip("._-").lower()
            if len(clean_tok) < 4:
                continue
            for candidate in {clean_tok} | set(re.findall(r"[a-z0-9_-]{4,}", clean_tok)):
                h = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
                if h in PROHIBITED_TOKEN_SHA256:
                    path_leaks.append(f"{fpath}: Prohibited token '{candidate}'")

    verdict = "PASS" if (not syntax_errors and not path_leaks) else "FAIL"
    return {
        "verdict": verdict,
        "py_files_checked": py_files_checked,
        "json_files_checked": json_files_checked,
        "prohibited_digest_count": len(PROHIBITED_TOKEN_SHA256),
        "syntax_errors": syntax_errors,
        "path_leaks": path_leaks,
        "silent_fallbacks": silent_fallbacks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Hat Forensic Analyzer v3.9.0")
    parser.add_argument("--target", type=str, required=True, help="Target file or directory to audit")
    args = parser.parse_args()
    res = scan_target(args.target)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
