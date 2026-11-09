#!/usr/bin/env python3
"""Zero-Token Black-Hat Verification-In-Progress UX Hook (`PostInvocation` + Card Holdback).

Role:
  Antigravity PostInvocation UX Hook & Deliverable Artifact Holdback Controller (`src/hooks/`).

Purpose:
  Eliminates premature turn-completion UI state when the parent agent yields to
  `IDLE` while `black-hat-goldfish` (Stage 1) or `black-hat-judge` (Stage 2) is
  still executing in the background. Temporarily flips top-level
  `<artifact>.metadata.json` `"userFacing": true` to `false` (excluding
  `"requestFeedback": true` interactive plans) into
  `<artifact_dir>/scratch/.bh_staged_artifacts.json`, injects a zero-token
  UI-only `HookSystemMessage` (`systemMessage: ""`, `metadata.user_markdown`)
  with a live `conversation://<subagent_cid>` inspection link, formats subagent
  `Role` labels in plain English, and restores `"userFacing": true` atomically
  when `Stop` settles or on next top-level `PreInvocation` recovery.

How It Is Used:
  - Wired automatically via `hooks.json` and `config/hooks.json` `PostInvocation`
    (`stdin` JSON -> `stdout` JSON).
  - Imported by `sentinel_dispatch.py` (`rewrite_black_hat_subagent_role`),
    `agent_stop_black_hat_gate.py` (`restore_deliverable_artifact_cards`), and
    `kg_pre_invocation_hook.py` (next-turn crash recovery).
  - Standalone validation: `python3 -B src/hooks/black_hat_in_progress_ux_hook.py --self-test`
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

sys.dont_write_bytecode = True

STAGED_MANIFEST_REL = os.path.join("scratch", ".bh_staged_artifacts.json")
METADATA_SUFFIX = ".metadata.json"

STAGE1_ROLE_PREFIX = "⏳ Checking Results (1/2)"
STAGE2_ROLE_PREFIX = "⏳ Final Sign-Off (2/2)"

_CRYPTIC_ROLE_PREFIX_RE = re.compile(
    r"^(?:⏳\s*)?(?:stage[- ]?[12]\b|black[- ]hat[- ]?(?:goldfish|judge|critic)\b"
    r"|goldfish\b|judge\b|forensic\s+(?:investigator|verifier|auditor)\b"
    r"|checking\s+results\s*\(1/2\)|final\s+sign[- ]off\s*\(2/2\))[\s:—–-]*",
    re.IGNORECASE,
)
_SUBAGENT_CID_RE = re.compile(
    r'"conversationId"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
    re.IGNORECASE,
)
_SENDER_UUID_RE = re.compile(
    r"\bsender=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.IGNORECASE,
)
_SUBAGENT_AGENT_NAMES = frozenset({
    "black-hat-goldfish",
    "black_hat_goldfish",
    "black-hat-judge",
    "black_hat_judge",
    "black-hat-critic",
    "black_hat_critic",
    "research-assistant",
    "dreaming-improvement-reasoner",
    "workspace-housekeeper",
})


def _atomic_write_json(target_path: str, obj: Dict[str, Any]) -> None:
    parent = os.path.dirname(target_path)
    os.makedirs(parent, exist_ok=True)
    tmp_path = os.path.join(
        parent,
        f".bh_ux_{os.getpid()}_{time.time_ns() & 0xFFFFFFFF:08x}.tmp",
    )
    payload = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_path, target_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _manifest_path(artifact_dir: str) -> str:
    return os.path.join(artifact_dir, STAGED_MANIFEST_REL)


def _load_manifest(artifact_dir: str) -> Dict[str, Any]:
    mp = _manifest_path(artifact_dir)
    if not os.path.isfile(mp):
        return {"staged_metadata_files": [], "notified_cids": []}
    try:
        with open(mp, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict):
            staged = [
                str(x)
                for x in raw.get("staged_metadata_files") or []
                if isinstance(x, str) and x.endswith(METADATA_SUFFIX)
            ]
            notified = [str(x) for x in raw.get("notified_cids") or [] if isinstance(x, str)]
            return {"staged_metadata_files": staged, "notified_cids": notified}
    except Exception:
        pass
    return {"staged_metadata_files": [], "notified_cids": []}


def stage_deliverable_artifact_cards(
    artifact_dir: str,
    subagent_cid: Optional[str] = None,
    stage_num: int = 1,
) -> Tuple[int, bool]:
    """Hides top-level `userFacing: true` deliverable cards until verification completes."""
    if not artifact_dir or not os.path.isdir(artifact_dir):
        return 0, False

    state = _load_manifest(artifact_dir)
    staged_set = set(state["staged_metadata_files"])
    notified_list = list(state["notified_cids"])
    already_notified = bool(subagent_cid and subagent_cid in notified_list)

    try:
        entries = sorted(os.listdir(artifact_dir))
    except OSError:
        entries = []

    for name in entries:
        if name.startswith(".") or not name.endswith(METADATA_SUFFIX):
            continue
        meta_p = os.path.join(artifact_dir, name)
        artifact_name = name[: -len(METADATA_SUFFIX)]
        artifact_p = os.path.join(artifact_dir, artifact_name)
        if not os.path.isfile(meta_p) or not os.path.isfile(artifact_p):
            continue
        try:
            with open(meta_p, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
            if not isinstance(meta, dict) or meta.get("requestFeedback") is True:
                continue
            if meta.get("userFacing") is True:
                meta["userFacing"] = False
                _atomic_write_json(meta_p, meta)
                staged_set.add(name)
        except Exception:
            continue

    if subagent_cid and subagent_cid not in notified_list:
        notified_list.append(subagent_cid)

    held_files = [
        fn
        for fn in sorted(staged_set)
        if os.path.isfile(os.path.join(artifact_dir, fn))
        and os.path.isfile(os.path.join(artifact_dir, fn[: -len(METADATA_SUFFIX)]))
    ]
    if held_files or notified_list:
        _atomic_write_json(
            _manifest_path(artifact_dir),
            {
                "staged_metadata_files": held_files,
                "notified_cids": notified_list[-16:],
                "active_stage": int(stage_num),
                "updated_at_epoch": round(time.time(), 3),
            },
        )
    return len(held_files), already_notified


def restore_deliverable_artifact_cards(artifact_dir: str) -> List[str]:
    """Restores `"userFacing": true` on all held deliverable cards in O(1) when verification settles."""
    if not artifact_dir:
        return []
    mp = _manifest_path(artifact_dir)
    if not os.path.isfile(mp):
        return []

    state = _load_manifest(artifact_dir)
    restored: List[str] = []
    for name in state.get("staged_metadata_files") or []:
        if "/" in name or "\\" in name or name.startswith("."):
            continue
        meta_p = os.path.join(artifact_dir, name)
        if not os.path.isfile(meta_p):
            continue
        try:
            with open(meta_p, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
            if isinstance(meta, dict) and meta.get("userFacing") is False:
                meta["userFacing"] = True
                _atomic_write_json(meta_p, meta)
                restored.append(name[: -len(METADATA_SUFFIX)])
        except Exception:
            continue

    try:
        os.unlink(mp)
    except OSError:
        pass
    return restored


def _format_single_bh_role(tname: str, raw_role: str) -> Optional[str]:
    tn = tname.strip().lower()
    if tn in ("black-hat-goldfish", "black_hat_goldfish"):
        prefix = STAGE1_ROLE_PREFIX
        default_tail = "Files & Data Verification"
    elif tn in ("black-hat-judge", "black_hat_judge"):
        prefix = STAGE2_ROLE_PREFIX
        default_tail = "Verification Review"
    else:
        return None

    role_str = raw_role.strip()
    if role_str.startswith(prefix):
        return None

    cleaned = role_str
    for _ in range(2):
        nxt = _CRYPTIC_ROLE_PREFIX_RE.sub("", cleaned).strip(" :—–-")
        if nxt == cleaned:
            break
        cleaned = nxt
    tail = cleaned or default_tail
    if len(tail) > 48:
        tail = tail[:45].rstrip() + "..."
    new_role = f"{prefix}: {tail}"
    return new_role if new_role != role_str else None


def rewrite_black_hat_subagent_role(args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Returns a minimal PreToolUse `overwrite` delta adding plain-English progress prefixes."""
    if not isinstance(args, dict):
        return None
    subs = args.get("Subagents")
    if isinstance(subs, list) and subs:
        changed = False
        new_subs: List[Any] = []
        for item in subs:
            if isinstance(item, dict):
                nr = _format_single_bh_role(
                    str(item.get("TypeName") or ""), str(item.get("Role") or "")
                )
                if nr is not None:
                    cp = dict(item)
                    cp["Role"] = nr
                    new_subs.append(cp)
                    changed = True
                    continue
            new_subs.append(item)
        if changed:
            return {"decision": "allow", "overwrite": {"Subagents": new_subs}}
        return None

    nr_single = _format_single_bh_role(
        str(args.get("TypeName") or ""), str(args.get("Role") or "")
    )
    if nr_single is None:
        return None
    return {"decision": "allow", "overwrite": {"Role": nr_single}}


def _decode_tc_args(raw_args: Any) -> Dict[str, Any]:
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except Exception:
            return {}
    if not isinstance(raw_args, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in raw_args.items():
        if isinstance(v, str) and v[:1] in ("[", "{"):
            try:
                out[k] = json.loads(v)
                continue
            except Exception:
                pass
        out[k] = v
    return out


def _read_current_turn_tail(transcript_path: str, max_bytes: int = 131072) -> List[Dict[str, Any]]:
    if not transcript_path or not os.path.isfile(transcript_path):
        return []
    try:
        sz = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as fh:
            if sz > max_bytes:
                fh.seek(sz - max_bytes)
                raw = fh.read().decode("utf-8", errors="ignore")
                nl = raw.find("\n")
                lines = raw[nl + 1 :].splitlines() if nl >= 0 else raw.splitlines()
            else:
                lines = fh.read().decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    parsed: List[Dict[str, Any]] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                parsed.append(obj)
        except Exception:
            continue

    last_user_idx = -1
    for idx, entry in enumerate(parsed):
        if entry.get("type") == "USER_INPUT" or entry.get("source") == "USER_EXPLICIT":
            last_user_idx = idx
    return parsed[last_user_idx + 1 :] if last_user_idx >= 0 else parsed


def _subagent_finished_on_disk(parent_transcript_path: str, scid: str) -> bool:
    try:
        logs_dir = os.path.dirname(os.path.abspath(parent_transcript_path))
        brain_root = os.path.dirname(os.path.dirname(os.path.dirname(logs_dir)))
        sub_tf = os.path.join(brain_root, scid, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.isfile(sub_tf):
            return False
        sz = os.path.getsize(sub_tf)
        with open(sub_tf, "rb") as fh:
            if sz > 24576:
                fh.seek(sz - 24576)
            tail_txt = fh.read().decode("utf-8", errors="ignore")
        if "FORENSIC_EVIDENCE_DOSSIER" in tail_txt or "CRITIC_VERDICT:" in tail_txt:
            if '"send_message"' in tail_txt:
                return True
        return False
    except Exception:
        return False


def find_active_verification_subagent(transcript_path: str) -> Optional[Tuple[int, str, str]]:
    """Returns `(stage_num, subagent_cid, role_label)` when parent yields while BH runs."""
    turn = _read_current_turn_tail(transcript_path)
    if not turn:
        return None

    last_planner: Optional[Dict[str, Any]] = None
    for entry in reversed(turn):
        if entry.get("type") == "PLANNER_RESPONSE":
            last_planner = entry
            break
    if not last_planner or last_planner.get("tool_calls"):
        return None

    returned_senders = set()
    killed_cids = set()
    spawns: List[Tuple[int, int, str, str]] = []

    for idx, entry in enumerate(turn):
        etype = str(entry.get("type") or "")
        content = str(entry.get("content") or "")
        if etype == "SYSTEM_MESSAGE":
            for m in _SENDER_UUID_RE.finditer(content):
                returned_senders.add(m.group(1).lower())
        for tc in entry.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            name = str(tc.get("name") or tc.get("tool_name") or "")
            targs = _decode_tc_args(tc.get("args"))
            if name == "manage_subagents" and str(targs.get("Action") or "") == "kill":
                for kcid in targs.get("ConversationIds") or []:
                    killed_cids.add(str(kcid).lower())
            elif name == "invoke_subagent":
                req_list = targs.get("Subagents")
                reqs = req_list if isinstance(req_list, list) else [targs]
                bh_reqs: List[Tuple[int, int, str]] = []
                for req_i, req in enumerate(reqs):
                    if not isinstance(req, dict):
                        continue
                    tn = str(req.get("TypeName") or "").strip().lower()
                    rl = str(req.get("Role") or "").strip()
                    if tn in ("black-hat-goldfish", "black_hat_goldfish"):
                        bh_reqs.append((req_i, 1, rl or "Result Verification"))
                    elif tn in ("black-hat-judge", "black_hat_judge"):
                        bh_reqs.append((req_i, 2, rl or "Final Sign-Off"))
                if not bh_reqs:
                    continue
                found_cids: List[str] = []
                scan_j = idx + 1
                while scan_j < len(turn) and len(found_cids) < len(reqs):
                    nxt = turn[scan_j]
                    ntype = str(nxt.get("type") or "")
                    if ntype in ("PLANNER_RESPONSE", "USER_INPUT"):
                        break
                    nc = str(nxt.get("content") or "")
                    if "conversationId" in nc:
                        for m_cid in _SUBAGENT_CID_RE.finditer(nc):
                            found_cids.append(m_cid.group(1).lower())
                    scan_j += 1
                if len(bh_reqs) == 1 and found_cids and bh_reqs[0][0] >= len(found_cids):
                    spawns.append((idx, bh_reqs[0][1], found_cids[-1], bh_reqs[0][2]))
                else:
                    for req_i, stg, rl in bh_reqs:
                        if req_i < len(found_cids):
                            spawns.append((idx, stg, found_cids[req_i], rl))

    for _, stage_num, scid, role_lbl in reversed(spawns):
        if scid in returned_senders or scid in killed_cids:
            continue
        if _subagent_finished_on_disk(transcript_path, scid):
            continue
        return stage_num, scid, role_lbl
    return None


def build_verification_banner_markdown(stage_num: int, subagent_cid: str, held_cards: int) -> str:
    hold_note = (
        f" `{held_cards}` deliverable artifact card(s) stay temporarily hidden until sign-off completes."
        if held_cards > 0
        else ""
    )
    if stage_num == 1:
        return (
            "> [!WARNING]\n"
            "> **⏳ Checking Results in Progress (Step 1 of 2 — Forensic Verification)** — "
            "Turn is **still running** while an isolated read-only investigator independently "
            f"re-verifies files, commands, and claims.{hold_note} "
            f"[Open Result Check](conversation://{subagent_cid})"
        )
    return (
        "> [!WARNING]\n"
        "> **⏳ Final Sign-Off in Progress (Step 2 of 2 — Holistic Adjudication)** — "
        "Turn is **still running** while the isolated judge inspects Stage-1 transcripts "
        f"and spot-checks deliverables before posting the final summary.{hold_note} "
        f"[Open Final Sign-Off](conversation://{subagent_cid})"
    )


def evaluate_post_invocation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates Antigravity `PostInvocation` hook payload (`0` model tokens added)."""
    if not isinstance(payload, dict):
        return {}
    agent_name = str(payload.get("agentName") or payload.get("agent_name") or "").strip().lower()
    if agent_name in _SUBAGENT_AGENT_NAMES:
        return {}
    conv_id = str(payload.get("conversationId") or payload.get("conversation_id") or "").strip()
    root_cid = str(payload.get("rootConversationId") or payload.get("root_conversation_id") or "").strip()
    if conv_id and root_cid and conv_id != root_cid:
        return {}

    transcript_path = str(payload.get("transcriptPath") or payload.get("transcript_path") or "")
    artifact_dir = str(payload.get("artifactDirectoryPath") or payload.get("artifact_directory_path") or "")
    active = find_active_verification_subagent(transcript_path)
    if not active:
        return {}

    stage_num, scid, _role = active
    held_count, already_notified = stage_deliverable_artifact_cards(
        artifact_dir, subagent_cid=scid, stage_num=stage_num
    )
    if already_notified:
        return {}

    md = build_verification_banner_markdown(stage_num, scid, held_count)
    return {
        "injectSteps": [
            {
                "systemMessage": {
                    "systemMessage": "",
                    "metadata": {"user_markdown": md},
                }
            }
        ]
    }


evaluate = evaluate_post_invocation


def run_self_test() -> Dict[str, Any]:
    """Runs deterministic holdback/banner/restore verification and returns `{verdict, checks}`."""
    td = tempfile.mkdtemp(prefix="bh_ux_selftest_")
    try:
        cid_parent = "11111111-1111-4111-8111-111111111111"
        cid_gf = "22222222-2222-4222-8222-222222222222"
        art_dir = os.path.join(td, "brain", cid_parent)
        logs_dir = os.path.join(art_dir, ".system_generated", "logs")
        os.makedirs(logs_dir, exist_ok=True)

        rep_p = os.path.join(art_dir, "report.md")
        rep_m = os.path.join(art_dir, "report.md.metadata.json")
        plan_p = os.path.join(art_dir, "plan.md")
        plan_m = os.path.join(art_dir, "plan.md.metadata.json")
        with open(rep_p, "w", encoding="utf-8") as f:
            f.write("# Report\n")
        with open(rep_m, "w", encoding="utf-8") as f:
            json.dump({"userFacing": True, "requestFeedback": False, "summary": "r"}, f)
        with open(plan_p, "w", encoding="utf-8") as f:
            f.write("# Plan\n")
        with open(plan_m, "w", encoding="utf-8") as f:
            json.dump({"userFacing": True, "requestFeedback": True, "summary": "p"}, f)

        tf_path = os.path.join(logs_dir, "transcript.jsonl")
        steps = [
            {"type": "USER_INPUT", "content": "ship feature"},
            {
                "type": "PLANNER_RESPONSE",
                "tool_calls": [
                    {"name": "invoke_subagent", "args": {"TypeName": "black-hat-goldfish", "Role": "Goldfish"}}
                ],
            },
            {"type": "GENERIC", "content": f'Created subagent {{"conversationId": "{cid_gf}"}}'},
            {"type": "PLANNER_RESPONSE", "content": "", "tool_calls": []},
        ]
        with open(tf_path, "w", encoding="utf-8") as f:
            for st in steps:
                f.write(json.dumps(st) + "\n")

        out1 = evaluate_post_invocation({
            "conversationId": cid_parent,
            "rootConversationId": cid_parent,
            "transcriptPath": tf_path,
            "artifactDirectoryPath": art_dir,
        })
        assert "injectSteps" in out1
        sm = out1["injectSteps"][0]["systemMessage"]
        assert sm["systemMessage"] == ""
        assert f"conversation://{cid_gf}" in sm["metadata"]["user_markdown"]
        with open(rep_m, encoding="utf-8") as f_rm:
            assert json.load(f_rm)["userFacing"] is False
        with open(plan_m, encoding="utf-8") as f_pm:
            assert json.load(f_pm)["userFacing"] is True

        # Idempotent second call for same subagent CID emits {}
        out2 = evaluate_post_invocation({
            "conversationId": cid_parent,
            "rootConversationId": cid_parent,
            "transcriptPath": tf_path,
            "artifactDirectoryPath": art_dir,
        })
        assert out2 == {}

        # Restore cards atomically
        restored = restore_deliverable_artifact_cards(art_dir)
        assert restored == ["report.md"]
        with open(rep_m, encoding="utf-8") as f_rm2:
            assert json.load(f_rm2)["userFacing"] is True

        rw = rewrite_black_hat_subagent_role({"TypeName": "black-hat-goldfish", "Role": "Stage 1: Audit"})
        assert rw is not None and rw["overwrite"]["Role"].startswith(STAGE1_ROLE_PREFIX)
        return {"verdict": "PASS", "checks": 6}
    finally:
        shutil.rmtree(td, ignore_errors=True)


def _run_self_test() -> int:
    res = run_self_test()
    print(json.dumps(res))
    return 0 if res.get("verdict") == "PASS" else 1


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(_run_self_test())
    if "--restore" in sys.argv:
        idx = sys.argv.index("--restore")
        if idx + 1 < len(sys.argv):
            restore_deliverable_artifact_cards(sys.argv[idx + 1])
        print("{}")
        return
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}
    try:
        out = evaluate_post_invocation(payload)
    except Exception:
        out = {}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
