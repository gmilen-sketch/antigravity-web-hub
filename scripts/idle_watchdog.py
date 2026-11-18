#!/usr/bin/env python3
"""
Role: Stream-Aware Idle Cost-Governance Watchdog for Antigravity Web Hub (ACE-WS-06).
Purpose: Evaluates whether the GCE hub VM has remained idle beyond IDLE_SUSPEND_MINUTES
  with zero active TCP streams on ports 8081/8083 and stale session file mtime, emitting
  KEEP_RUNNING or SUSPEND_VM (and optionally issuing graceful system poweroff when --apply
  is enabled).
How It Is Used: Installed as an opt-in cron watchdog by scripts/install.sh when
  IDLE_SUSPEND_MINUTES > 0, or verified via `python3 -B scripts/idle_watchdog.py --self-test`.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Dict


def evaluate_idle_shutdown_policy(
    idle_minutes: float,
    active_streams: int,
    threshold_minutes: int = 720,
) -> str:
    """Returns KEEP_RUNNING when threshold <= 0, active streams > 0, or idle < threshold."""
    if threshold_minutes <= 0 or active_streams > 0:
        return "KEEP_RUNNING"
    return "SUSPEND_VM" if idle_minutes >= float(threshold_minutes) else "KEEP_RUNNING"


def count_active_hub_streams(ports=(8081, 8083)) -> int:
    """Counts ESTABLISHED TCP connections targeting language_server or ccpa_mock ports."""
    try:
        out = subprocess.check_output(["ss", "-Htn", "state", "established"], text=True, timeout=5)
    except Exception:
        return 0
    count = 0
    for line in out.splitlines():
        cols = line.split()
        if len(cols) < 4:
            continue
        local_ep = cols[2]
        for p in ports:
            if local_ep.endswith(f":{p}"):
                count += 1
                break
    return count


def compute_session_idle_minutes(
    session_store_path: str = "/mnt/data/projects/persistent_ui_sessions.json",
    now_epoch: float = 0.0,
) -> float:
    """Returns minutes elapsed since the latest recorded UI session update or system boot."""
    now = now_epoch or time.time()
    latest_mtime = 0.0
    if os.path.isfile(session_store_path):
        latest_mtime = max(latest_mtime, os.path.getmtime(session_store_path))
    if latest_mtime <= 0.0:
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as fh:
                uptime_sec = float(fh.read().split()[0])
            return uptime_sec / 60.0
        except Exception:
            return 0.0
    return max(0.0, (now - latest_mtime) / 60.0)


def check_idle_state(threshold_minutes: int, session_store_path: str) -> Dict[str, object]:
    active = count_active_hub_streams()
    idle_min = round(compute_session_idle_minutes(session_store_path), 2)
    action = evaluate_idle_shutdown_policy(idle_min, active, threshold_minutes)
    return {
        "action": action,
        "idle_minutes": idle_min,
        "active_streams": active,
        "threshold_minutes": threshold_minutes,
    }


def _self_test() -> int:
    assert evaluate_idle_shutdown_policy(800, 1, 720) == "KEEP_RUNNING"
    assert evaluate_idle_shutdown_policy(800, 0, 720) == "SUSPEND_VM"
    assert evaluate_idle_shutdown_policy(120, 0, 720) == "KEEP_RUNNING"
    assert evaluate_idle_shutdown_policy(9999, 0, 0) == "KEEP_RUNNING"
    print("idle_watchdog.py self-test: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream-aware idle auto-stop watchdog.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--threshold-minutes", type=int, default=int(os.environ.get("IDLE_SUSPEND_MINUTES", "0")))
    parser.add_argument("--session-store", default="/mnt/data/projects/persistent_ui_sessions.json")
    parser.add_argument("--apply", action="store_true", help="Invoke systemctl poweroff when SUSPEND_VM triggers.")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    state = check_idle_state(args.threshold_minutes, args.session_store)
    print(json.dumps(state))
    if args.apply and state["action"] == "SUSPEND_VM":
        subprocess.run(["sudo", "-n", "systemctl", "poweroff"], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
