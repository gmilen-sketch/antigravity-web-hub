#!/usr/bin/env bash
# Role:
#   Resilient Lifecycle Hook Launcher for Antigravity Web Hub & Subagent Hooks.
#
# Purpose:
#   Resolves target Python lifecycle hook scripts (`kg_pre_invocation_hook.py`,
#   `black_hat_in_progress_ux_hook.py`, `sentinel_dispatch.py`,
#   `agent_stop_black_hat_gate.py`) across plugin-root, repository `src/hooks/`,
#   or `~/.gemini/antigravity/bin/hooks/` layouts, executes them under
#   `PYTHONDONTWRITEBYTECODE=1 python3 -B` with zero `.pyc` side effects, and
#   emits fail-open `{}` JSON only when a script path is absent during bootstrap.
#
# How It Is Used:
#   Referenced by root `hooks.json`, `config/hooks.json`, `agents/*/hooks.json`,
#   and `scripts/install.sh`:
#     bash <hooks_dir>/run_hook_safe.sh <hook_script_basename_or_path> [args...]

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_RAW="${1:-}"
if [ -z "$TARGET_RAW" ]; then
  printf '{}\n'
  exit 0
fi
shift || true

RESOLVED=""
for CAND in \
  "$TARGET_RAW" \
  "$SCRIPT_DIR/$TARGET_RAW" \
  "$SCRIPT_DIR/$(basename "$TARGET_RAW")" \
  "$HOME/.gemini/antigravity/bin/hooks/$(basename "$TARGET_RAW")"; do
  if [ -n "$CAND" ] && [ -f "$CAND" ]; then
    RESOLVED="$CAND"
    break
  fi
done

if [ -z "$RESOLVED" ]; then
  printf '{}\n'
  exit 0
fi

export PYTHONDONTWRITEBYTECODE=1
export PYTHONSAFEPATH=1
exec python3 -B "$RESOLVED" "$@"
