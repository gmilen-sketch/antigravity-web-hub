#!/usr/bin/env python3
"""
Bi-Temporal Knowledge Graph Engine (OKF v0.4 Clean-Room Edition).
Maintains both Valid-Time [valid_from, valid_until] (when a fact was true in reality)
and Transaction-Time [tx_from, tx_until] (when the fact was recorded in the KG),
enabling non-destructive point-in-time historical queries and contradiction superseding.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def supersede_fact(
    existing_facts: List[Dict[str, Any]],
    subject: str,
    predicate: str,
    new_object: Any,
    valid_from: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ts = valid_from or now_iso()
    updated: List[Dict[str, Any]] = []
    for fact in existing_facts:
        f = dict(fact)
        if f.get("subject") == subject and f.get("predicate") == predicate and f.get("valid_until") is None:
            f["valid_until"] = ts
            f["tx_until"] = ts
        updated.append(f)
    updated.append({
        "subject": subject,
        "predicate": predicate,
        "object": new_object,
        "valid_from": ts,
        "valid_until": None,
        "tx_from": ts,
        "tx_until": None,
    })
    return updated


def query_as_of(facts: List[Dict[str, Any]], as_of_iso: str) -> List[Dict[str, Any]]:
    active = []
    for f in facts:
        vf = str(f.get("valid_from") or "")
        vu = f.get("valid_until")
        if vf <= as_of_iso and (vu is None or str(vu) > as_of_iso):
            active.append(f)
    return active
