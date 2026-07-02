# Troubleshooting

Known failure modes and their fixes. All fixes assume you can
`journalctl -u antigravity-web.service -f` and edit files under
`~/.gemini/antigravity/bin/`.

## Browser shows "Working…" forever, no reply

**Cause:** proxy.py's shim didn't call Vertex, or Vertex 4xx'd, or the
StreamAgentStateUpdates stream isn't emitting a frame with the response.

**Diagnose:** find your cascade id in the URL bar or DevTools Network tab,
then

```bash
journalctl -u antigravity-web.service --since '5 min ago' | grep <cid>
```

Look for `[CLAUDE] {cid} turn=N got response (…B)`. If missing, Vertex
never returned. If present, the polling stream isn't seeing the change —
usually a frame-shape regression; check the console for `[consumeAgentStateStream]
… error` (Connect will name the exact field that didn't decode).

## Console spams `cannot decode message google.protobuf.Timestamp from JSON: object`

**Cause:** you added a Timestamp field to a synthetic frame using the
`{seconds: N}` object form. Connect's protojson requires an RFC3339 STRING.

**Fix:** `"2026-07-02T13:27:12Z"`.

## After restart, Claude cascades don't appear in sidebar

**Cause:** persistence files exist but the `JetboxSubscribeToSummaries` hook
isn't emitting them.

**Diagnose:** confirm files exist under
`/mnt/data/antigravity/claude_cascades/*.json`, then curl the endpoint
directly:

```bash
timeout 2 curl -s -N -X POST \
  http://127.0.0.1:8080/exa.language_server_pb.LanguageServerService/JetboxSubscribeToSummaries \
  -H 'Content-Type: application/grpc-web+json' \
  -H "x-codeium-csrf-token: $CSRF_TOKEN" \
  --data-binary $'\x00\x00\x00\x00\x02{}'
```

Should return an enveloped JSON payload with your cascade cids in `updates`.

## Model dropdown reverts to Gemini after page reload

**Cause:** the SPA's chip-label render fires before our injected JS's
5-second user-click lock, and the observer helper clobbers the persisted
preference back to Gemini.

**Fix in proxy.py:** confirm `_setModel` has the
`(Date.now() - __userClickAt) < 5000` guard, and that
`_forceChipLabel(window.__selectedModelLabel)` runs at 200/500/1000/2000/4000ms
after DOMContentLoaded.

## `/mcp start` reports "failed to open port in 8s"

**Cause:** MCP subprocess crashed on startup, most likely missing
`fastmcp` in `pip --user`'s path for the systemd user.

**Fix:**

```bash
sudo -u <RUN_USER> pip install --user --break-system-packages fastmcp
```

## "MCP already running" but `/mcp status` reports stopped

**Cause:** stale `MCP_STATE["proc"]` reference after a proxy restart (in-
memory state is lost, but the child subprocess might still be alive).

**Fix:**

```bash
pkill -f mcp_deep_research
```

Then re-run `/mcp start`.

## GCP LB returns `ERR_HTTP2_PROTOCOL_ERROR`

**Cause:** nginx isn't using chunked framing for streams — LB converts
close-delimited h1 to h2 RST_STREAM at end-of-stream. Or backendService
`timeoutSec` is at the default 30s, killing long streams.

**Fix:**

1. In `nginx.conf`, ensure the streams `location` has
   `chunked_transfer_encoding on` and `proxy_buffering off`.
2. `gcloud compute backend-services update <name> --global --timeout=86400`

## "trajectory not found in any store" ConnectError in console

**Cause:** the SPA opened `StreamAgentStateUpdates(cid)` BEFORE
`StartCascade` registered the cascade with agy. On Claude cascades,
proxy.py's shim absorbs this by serving synthetic frames.

**Fix:** confirm your Claude cascade path in proxy.py registers the cid on
StreamAgentStateUpdates if `x-user-model in CLAUDE_MODELS`, so we don't
fall through to agy on the very first stream.

## GetTurnDiff spams "trajectory not found" for Claude cascades

**Cause:** agy doesn't know about Claude cascades, so it can't return diffs
for their turns.

**Fix:** the shim short-circuits `GetTurnDiff` for Claude cids with an empty
`{}`. If it's still firing, the request lacks `x-user-model` — confirm
`RPC_NEEDS_LABEL` in the injected JS includes `"GetTurnDiff"`.
