#!/usr/bin/env python3
"""
Role: Multi-Zone Capacity & CPU Quota Preflight Selector (ACE-WS-05).
Purpose: Probes Google Compute Engine regional CPU quotas and zonal machine-type availability
  via REST API (sending X-Goog-User-Project for ADC quota attribution) across a prioritized
  fallback list before VM creation, preventing mid-deploy regional stockout failures.
How It Is Used: Invoked by scripts/gcp_setup_vm.sh to resolve the first viable zone, or
  verified offline via `python3 -B scripts/preflight_zone_check.py --self-test`.
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence

DEFAULT_FALLBACK_ZONES = (
    "us-central1-a",
    "us-central1-b",
    "us-central1-c",
    "us-east4-a",
    "us-east1-b",
    "europe-west1-b",
)


def parse_vcpu_count(machine_type: str) -> int:
    """Extracts vCPU count from standard GCE machine-type names (e.g. e2-standard-4 -> 4)."""
    m = re.search(r"-(\d+)$", (machine_type or "").strip())
    return int(m.group(1)) if m else 4


def family_quota_metric(machine_type: str) -> Optional[str]:
    """Maps GCE machine family prefix to its regional family-specific CPU quota metric."""
    fam = (machine_type or "").strip().lower().split("-")[0]
    mapping = {
        "n4": "N4_CPUS",
        "c2": "C2_CPUS",
        "c3": "C3_CPUS",
        "c4": "C4_CPUS",
        "n2": "N2_CPUS",
        "n2d": "N2D_CPUS",
    }
    return mapping.get(fam)


def select_available_zone(
    candidates: Sequence[str],
    zone_probes: Dict[str, Dict[str, Any]],
    required_cpus: int = 4,
) -> str:
    """Returns the first candidate zone with machine-type availability and sufficient free CPUs."""
    for zone in candidates:
        info = zone_probes.get(zone, {})
        if not info.get("machine_available"):
            continue
        if float(info.get("free_cpus", 0.0)) < float(required_cpus):
            continue
        fam_free = info.get("free_family_cpus")
        if fam_free is not None and float(fam_free) < float(required_cpus):
            continue
        return zone
    raise RuntimeError(
        f"No candidate zone satisfied machine availability and {required_cpus} free vCPUs: {list(candidates)}"
    )


def _get_gcloud_token(account: str = "") -> str:
    cmd = ["gcloud", "auth", "print-access-token"]
    if account:
        cmd.extend(["--account", account])
    return subprocess.check_output(cmd, text=True, timeout=15).strip()


def _gce_get(url: str, token: str, project_id: str) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Goog-User-Project": project_id,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def probe_live_zones(
    project_id: str,
    machine_type: str,
    candidates: Sequence[str],
    account: str = "",
) -> Dict[str, Dict[str, Any]]:
    """Queries Compute Engine REST API for region quotas and zone machine types."""
    token = _get_gcloud_token(account)
    region_cache: Dict[str, Dict[str, float]] = {}
    fam_metric = family_quota_metric(machine_type)
    results: Dict[str, Dict[str, Any]] = {}

    for zone in candidates:
        parts = zone.split("-")
        region = "-".join(parts[:2]) if len(parts) >= 3 else zone
        if region not in region_cache:
            try:
                rdata = _gce_get(
                    f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}",
                    token,
                    project_id,
                )
                quotas: Dict[str, float] = {}
                for q in rdata.get("quotas", []):
                    metric = str(q.get("metric", ""))
                    quotas[metric] = max(0.0, float(q.get("limit", 0.0)) - float(q.get("usage", 0.0)))
                region_cache[region] = quotas
            except Exception as exc:
                region_cache[region] = {"_error": -1.0}
                results[zone] = {"machine_available": False, "free_cpus": 0.0, "error": str(exc)}
                continue

        quotas = region_cache[region]
        if "_error" in quotas:
            results[zone] = {"machine_available": False, "free_cpus": 0.0, "error": "region_query_failed"}
            continue

        free_cpus = quotas.get("CPUS", 0.0)
        free_fam = quotas.get(fam_metric) if fam_metric and fam_metric in quotas else None
        machine_ok = False
        try:
            _gce_get(
                f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zone}/machineTypes/{machine_type}",
                token,
                project_id,
            )
            machine_ok = True
        except urllib.error.HTTPError:
            machine_ok = False
        except Exception:
            machine_ok = False

        results[zone] = {
            "machine_available": machine_ok,
            "free_cpus": free_cpus,
            "free_family_cpus": free_fam,
        }
    return results


def _self_test() -> int:
    assert parse_vcpu_count("n4-standard-2") == 2
    assert parse_vcpu_count("c2-standard-16") == 16
    assert family_quota_metric("n4-standard-2") == "N4_CPUS"
    probes = {
        "us-central1-a": {"machine_available": False, "free_cpus": 24.0, "free_family_cpus": 24.0},
        "us-central1-b": {"machine_available": True, "free_cpus": 2.0, "free_family_cpus": 2.0},
        "us-central1-c": {"machine_available": True, "free_cpus": 16.0, "free_family_cpus": 16.0},
    }
    chosen = select_available_zone(["us-central1-a", "us-central1-b", "us-central1-c"], probes, required_cpus=4)
    assert chosen == "us-central1-c", f"Expected us-central1-c, got {chosen}"
    print("preflight_zone_check.py self-test: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Select first available GCE zone with quota & machine stock.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--project", default="")
    parser.add_argument("--machine-type", default="e2-standard-4")
    parser.add_argument("--preferred-zone", default="us-central1-c")
    parser.add_argument("--fallback-zones", default=",".join(DEFAULT_FALLBACK_ZONES))
    parser.add_argument("--account", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    ordered: List[str] = []
    for z in [args.preferred_zone] + [x.strip() for x in args.fallback_zones.split(",") if x.strip()]:
        if z and z not in ordered:
            ordered.append(z)
    req_cpus = parse_vcpu_count(args.machine_type)
    probes = probe_live_zones(args.project, args.machine_type, ordered, account=args.account)
    selected = select_available_zone(ordered, probes, required_cpus=req_cpus)
    if args.json:
        print(json.dumps({"selected_zone": selected, "required_cpus": req_cpus, "probes": probes}, indent=2))
    else:
        print(selected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
