# The Vertex Claude shim

## What "shim" means

A *shim* is a term borrowed from carpentry — a thin wedge slipped between
two things that weren't designed to meet, to make them line up. In software
it's a small piece of code that intercepts calls to one system and
translates them into another's language, filling a gap that wasn't built
into either side.

The **Vertex Claude shim** is the block of code in `src/proxy.py` that lets
you pick Claude models in the Antigravity SPA even though the SPA and the
agy backend only know how to speak to Gemini. Neither side is modified —
the shim sits in the middle and does the translation transparently.

## Why we need one

Antigravity's `language_server` binary has a **server-side allowlist** of
model enums, all Gemini variants. Even if you enable Claude on Vertex and
set the org-level `dataSharingEnabledProvider` flag, agy still refuses to
route Claude — the allowlist is baked into the binary. You can't opt in
from the outside.

The only way to add Claude to the dropdown without forking or patching
Antigravity is to **intercept the requests before they reach agy** and
serve Claude's responses ourselves.

## How the shim works — three stages

### Stage 1 — Advertise Claude in the dropdown

When the SPA loads, it calls `GetUserStatus` and reads
`cascadeModelConfigData.clientModelConfigs` for the list of picker options.
Normally agy returns Gemini-only.

The shim (proxy.py) intercepts `GetUserStatus`:
1. Passes it through to agy so we get the real, live response.
2. Appends our extra entries — `Claude Opus 4.8`, `Claude Fable 5` — to
   `clientModelConfigs` by emitting the raw protobuf wire bytes for the
   list and letting proto3's "last value wins for repeated fields" rule
   merge them in.
3. Returns the augmented payload to the SPA. The SPA renders Opus/Fable
   as normal-looking dropdown options with no idea they're special.

The values assigned to the Claude entries are cosmetic — the SPA's
protobuf-es library can only serialize known-in-schema enum values, so it
always sends `MODEL_UNSPECIFIED` back on the wire regardless of which
option the user picks. **The picker labels are the only signal we need**,
which brings us to stage 2.

### Stage 2 — Route by user's picked label, not by wire enum

The proxy injects a `<script>` block into `index.html` before the SPA
loads. Two things happen there:

1. A capture-phase `click` listener on the whole document catches clicks
   on popover option buttons whose text matches a known Claude label. On
   click, it writes the label to `window.__selectedModelLabel` and
   `localStorage`, and force-repaints the chip so the UI reflects the
   choice even if the SPA's React handler would revert it.
2. `window.fetch` gets wrapped. Every request to a cascade RPC
   (`StartCascade`, `SendUserCascadeMessage`,
   `StreamAgentStateUpdates`, `GetSlashCommands`, `GetTurnDiff`,
   `UpdateConversationAnnotations`) gets an extra header:

   ```
   x-user-model: Claude Opus 4.8
   ```

That header is the entire routing key. When the request arrives at
proxy.py, if `x-user-model` matches a Claude label (or the cid is in
`CLAUDE_CASCADES` — sticky routing for reopened conversations), we take
the Claude path. Otherwise it's a plain Gemini cascade and we passthrough
to agy.

### Stage 3 — Translate cascade RPCs into Anthropic API calls

Once in the Claude path, the shim owns the whole cascade lifecycle:

| SPA RPC                       | Shim behavior |
|-------------------------------|---|
| `StartCascade`                | Register `CLAUDE_CASCADES[cid]` in memory + persist to `/mnt/data`. Return synthetic `{cascadeId}` response so the SPA thinks agy started it. |
| `SendUserCascadeMessage`      | Append `{prompt, response=null}` to `entry["turns"]`. Fire an async `_call_vertex_claude(entry)` in the background. Return synthetic 200 immediately. |
| `_call_vertex_claude` (bg)    | Build the full messages array from `entry["turns"]` (all prior user/assistant pairs + current prompt). POST to Vertex `…/publishers/anthropic/models/{claude-opus-4-8,claude-fable-5}:rawPredict` with `Authorization: Bearer <ADC token>`. Run a tool loop for `fetch_url` / `web_search` / `deep_research` (see [request-flow.md](request-flow.md) § 6). Store the final text on `entry["turns"][-1]["response"]`. |
| `StreamAgentStateUpdates`     | Long-lived stream. Polls `entry` every 500 ms; emits a fresh synthetic `CascadeAgentState` JSON frame whenever `(turn, response, tool_status, len(tool_history))` changes. Frame shape matches what the SPA's own merger expects so it renders as a normal reply. |
| `GetTurnDiff`                 | Return empty `{}` — agy doesn't know about Claude turns, so there's no diff to fetch. Prevents a benign console error. |
| `JetboxSubscribeToSummaries`  | Emit synthetic sidebar summaries for every persisted Claude cascade so past conversations appear in the sidebar after restart. |

The SPA sees an entirely normal-looking cascade lifecycle. Claude sees an
entirely normal-looking Anthropic API call with tools. Neither knows the
other exists.

## Where each piece lives in the code

| Concern | Location in `src/proxy.py` |
|---|---|
| Model list | `CLAUDE_MODELS` (dict), `DROPDOWN_MODELS` (list) at top of file |
| In-memory + persisted cascade state | `CLAUDE_CASCADES` dict; `_persist_cascade` / `_load_cascades_from_disk` |
| Vertex call + tool loop | `_call_vertex_claude(model_cfg, prompt, entry)` |
| Frame synthesis | `_synthesize_claude_state_frame(cid, entry)` |
| RPC-level interception | inside `stream_language_server_request` — search `if user_model in CLAUDE_MODELS` |
| Injected JS (fetch wrapper, click listener, chip force) | search `KNOWN_LABELS =` |
| Sidebar hookup | search `JetboxSubscribeToSummaries` |

## Adding another model backend

Say you want to add OpenAI GPT-x via a similar shim. Rough shape:

1. **Extend the dropdown** — add `("GPT-x", <cosmetic-enum>)` to
   `DROPDOWN_MODELS` and `"GPT-x": {…}` to a new `OPENAI_MODELS` dict
   with the API config (base URL, auth env var, model id).
2. **Add label to `KNOWN_LABELS`** in the injected JS block.
3. **Add an interception branch** — copy the `if user_model in
   CLAUDE_MODELS:` block and adapt to check `OPENAI_MODELS`. All the
   frame-synthesis / persistence / sidebar plumbing is model-agnostic;
   reuse it as-is.
4. **Write a `_call_openai(entry)`** that mirrors `_call_vertex_claude`
   but speaks the OpenAI Responses API instead of Anthropic Messages.
5. **Route tool_use** — if OpenAI's tool schema differs, map inside
   `_call_openai` or add a translation layer.

That's the whole pattern — the shim is just a *narrow* translator, not a
whole agent runtime. You can bolt on any tool-calling LLM in ~300 lines
by copying and adapting the Claude one.

## Trade-offs and known limitations

- **Model dropdown resets to Gemini on page reload.** The SPA's chip
  reflects a Gemini enum by default. We force the chip label back via a
  MutationObserver, but there's a ~200 ms flash before the observer
  catches up. Sticky routing (by cid) covers the correctness gap.
- **Sidebar-click reopen for Claude cascades isn't fully wired yet.**
  The summary appears in the list, but clicking it doesn't fully hydrate
  the SPA into that cascade — needs a real `trajectoryMetadata`. Filed as
  a follow-up. Direct URL navigation and continuing from an open tab both
  work.
- **No live streaming of Claude token deltas.** We wait for the full
  Vertex response, then push one frame. Latency ≈ end-to-end Vertex
  turn. Fine for typical Q&A; not great for long chain-of-thought where
  incremental deltas would help perceived responsiveness.
- **No fork/edit-message support** — the SPA has a "fork from this
  message" UI that assumes agy's trajectory store. Not wired for Claude
  cascades.

The shim is deliberately thin. If you need Claude behavior the SPA can't
express (thinking blocks, streaming, forks), you'd want to write a real
Claude-native chat UI instead — that's out of scope here.
