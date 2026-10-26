# 0008 — Providers: Anthropic and Google

- **Status:** Done
- **Depends on:** 0004 (providers), 0005 (agents), 0006 (judges), 0010 (embeddings)
- **Django apps:** `providers` (adapter layer, provider kinds), `rag` (embeds through the
  embedding's adapter, small calls via adapters), `agents` (loop runs through an adapter),
  `scoring` / `benchmarks` (judge through an adapter)
- **Touches:** frontend, backend, jobs, docs (changes CLAUDE.md architecture rules and
  conventions, ARCHITECTURE.md, System Design page)

## Why
You want Claude and Gemini models next to OpenAI-compatible ones — for agents, judges and
generation. Doing that properly means talking to each provider in its own API, so features like
Claude's streamed thinking, prompt caching and refusal handling actually work.

## Decisions (2026-10-25)
1. **Native adapters**, not compatibility shims: OpenAI-compatible (today's code), **Anthropic**
   via the official `anthropic` SDK, **Google** via the official `google-genai` SDK.
2. **Embeddings are spec 0010's** (revised 2026-10-25): named embeddings, each with its own
   endpoint and model, replaced the single Embeddings setting this spec used to plan. This
   spec only adds **Google** as an endpoint an embedding can use. **Anthropic** can't be
   chosen for one, because it has no embeddings API.
3. **CLAUDE.md changes** (in the same change as the code):
   - Architecture table, LLM row: from "OpenAI-compatible client" to "LLMs only through
     `providers` adapters (OpenAI-compatible, Anthropic, Google); provider SDKs are imported
     nowhere else".
4. **ARCHITECTURE.md and the System Design page** gain the adapter layer and the two SDKs.

## Scope
- In: provider *kinds* on the default chat provider and on connections; presets for Anthropic
  and Google; model lists for every kind; Test connection per kind; streaming chat with tools
  and thinking for agents; judges, query rewriting, reranking and (0007) generation through any
  kind; Google as an endpoint for 0010's embeddings; kinds in 0010's model picker.
- Out: Amazon Bedrock / Vertex AI / Foundry routes to Claude, Anthropic server tools (web
  search, code execution), Batches, Managed Agents.

## Design notes
**Adapter interface** (`apps/providers/llm/`): one protocol, three implementations.
```
stream_chat(system, messages, tools, *, is_cancelled) -> iterator of
    Thinking(text) | Text(text) | ToolCall(id, name, args) | Usage(prompt, completion)
    | Refusal(category) | Done(stop, raw_assistant)
complete(prompt, *, max_tokens) -> str        # judges, rewriting, reranking, generation
list_models() -> [ModelInfo]                  # 0010's picker: id, kind, dimensions, tools
supports_tools(model) -> bool                 # False → the agent uses the pipeline fallback
embed(texts) -> [[float]]                     # raises EmbeddingsUnsupported for Anthropic
```
**History** — the agent loop keeps a neutral history (role, text, tool calls, tool results) for
display and for switching models, **plus the provider's raw assistant content** for every
assistant turn (`Done.raw_assistant`). When the next request goes to the same kind, the adapter
resends the raw content **byte for byte** (Claude's thinking blocks carry signatures and are
bound to the model and conversation); otherwise it translates the neutral form. The history is
**append-only**: nothing is trimmed, reordered or edited — cancel or retry starts a new turn
instead of rewriting an old one (edited history returns 400 on newer Anthropic accounts).

**Tool-calling fallback** — "agent runs keep working for models without tool calling" still
holds: each adapter answers `supports_tools(model)` (OpenAI-compatible: today's detection;
Anthropic/Google: always true), and the loop picks the pipeline fallback when it's false.

**Anthropic adapter** (official `anthropic` SDK, Messages API):
- Streaming with **adaptive thinking**, `display: "summarized"`, so Claude's reasoning streams
  into the Thinking panel (the default, `"omitted"`, would show nothing until the answer).
- **Effort is set explicitly** via `output_config.effort` — Claude Opus 5.5 defaults to
  `medium`, one level below earlier models. Default `high` for agents and judges, `low` for
  query rewriting/reranking; an agent may override it (new optional agent field
  `effort: low|medium|high|xhigh|max`, ignored by other kinds).
- The `search_documents` tool with `eager_input_streaming: true`; the parsed input is validated
  against its schema before running it (an invalid input goes back as an error `tool_result`).
  `tool_choice` stays `auto` (forced tool use returns 400 on current models).
- **No `temperature`/`top_p`/`top_k`** (rejected on every model since 2026-10-21) — judges rely
  on a fixed rubric instead.
- **Refusals**: `stop_reason: "refusal"` → `agent.error` "The model declined to answer". A
  refusal can arrive **mid-stream** after some tokens were shown — the UI replaces the partial
  answer with the error rather than leaving half an answer. For Claude Opus 5.5 / Sonnet 5.5 the
  request enables Anthropic's server-side **fallbacks** by default (beta
  `server-side-fallback-2026-07-01` + `fallbacks: "default"`; Sonnet 5.5 accepts only that
  form) so a declined request is retried on a suitable model. Haiku 5.5 has no server-side
  fallback — its refusals go straight to `agent.error`.
- **Prompt caching** on the system prompt + tools (identical across every turn). Note: below
  the model's minimum cacheable prefix (512–4096 tokens) nothing is cached and no error is
  raised — pytest asserts `cache_read_input_tokens > 0` on the second request with a prefix
  that's long enough.
- Presets list `claude-opus-5-5` (default), `claude-sonnet-5-5`, `claude-haiku-5-5`; the live
  list comes from the Models API.
- Usage from `usage.input_tokens` / `output_tokens` (feeds 0007's token accounting).

**Google adapter** (official `google-genai` SDK): streaming with thought summaries, function
calling for `search_documents`, embeddings, model listing.

**Data model**
- `ProviderConfig` → the **chat provider**: `kind`, base URL (optional for Anthropic/Google —
  the SDK's default endpoint), encrypted key, chat model. (0010 already moved the embedding
  fields onto each embedding.)
- `Connection.kind`. 0010's embedding form hides Anthropic connections.
- `Agent.effort` (optional, see above).

**Settings UI** — **Chat provider** (kind picker: OpenAI-compatible / Anthropic / Google,
presets, key, model from 0010's picker), **Connections** (now with a kind and presets).
Embeddings live in their own menu section (0010).

**Tests** — pytest with fake SDK clients per adapter; the acceptance fake server learns two more
dialects: Anthropic Messages (SSE events incl. **signed** thinking blocks, `tool_use` and
`refusal`; it also records each request body so tests can check what was sent back) and Gemini
`generateContent`/`embedContent`, so every scenario runs offline and free. In acceptance runs
every kind's base URL points at the fake server — no scenario ever reaches a real provider.
Real keys are only for your own manual checks.

pytest backing specific behaviour (named `test_at_0008_<nn>_…` where it backs a scenario):
- the second tool round resends the first round's thinking blocks unchanged (signature intact);
- sampling parameters are never sent to Anthropic; effort always is;
- the prompt-caching assertion above.

# Feature: Anthropic and Google providers

## Background:
* Given I am signed in

## Scenario: AT-0008-01 — Claude as the chat provider
* When I set my chat provider to the fake Anthropic provider with the API key "sk-ant-good" and the model "claude-opus-5-5"
* And I press "Test connection"
* Then the connection results show "Chat: Replied"

## Scenario: AT-0008-02 — A wrong Anthropic key is reported
* When I set my chat provider to the fake Anthropic provider with the API key "bad-key" and the model "claude-opus-5-5"
* And I press "Test connection"
* Then the "Chat" check fails with "invalid x-api-key"

## Scenario: AT-0008-03 — An embedding from Google
* Given I have a "Google" connection "Gemini" to the fake Google provider
* And I have the folder "Policies"
* And I upload "handbook.md" to "Policies"
* When I create the embedding "Gemini docs" with the folder "Policies" and the model "gemini-embed-fake" from "Gemini"
* Then the embedding "Gemini docs" shows "Ready"
* And the chunks of "handbook.md" in "Gemini docs" have 8-dimensional embeddings

## Scenario: AT-0008-04 — Anthropic can't be chosen for an embedding
* Given I have an "Anthropic" connection "Claude" to the fake Anthropic provider
* When I start a new embedding
* Then "Claude" is not offered as an embedding connection
* And I see "Anthropic has no embeddings API"

## Scenario: AT-0008-05 — An agent on Claude thinks, searches and cites
* Given my chat provider is the fake Anthropic provider
* And the embedding "Docs" is built from "handbook.md"
* And the agent "Claude helper" exists
* When I start a chat with the agent "Claude helper", the embedding "Docs" and the model "claude-opus-5-5"
* And I send "What is the refund window?"
* Then I see the agent's thinking
* And I see the tool call "search_documents"
* And the answer cites "handbook.md"
* And the answer comes from "Default provider · claude-opus-5-5"

## Scenario: AT-0008-06 — An agent on Gemini through a connection
* Given the embedding "Docs" is built from "handbook.md"
* And I have a "Google" connection "Gemini" to the fake Google provider
* And the agent "Gemini helper" exists
* When I start a chat with the agent "Gemini helper", the embedding "Docs" and the model "gemini-fake" from "Gemini"
* And I send "What is the refund window?"
* Then I see the tool call "search_documents"
* And the answer cites "handbook.md"

## Scenario: AT-0008-07 — A declined request is reported, not shown as an empty answer
* Given my chat provider is the fake Anthropic provider
* And the agent "Careful" exists
* When I start a chat with the agent "Careful", no embedding and the model "claude-fake-refuses"
* And I send "Tell me something"
* Then the latest answer shows "The model declined to answer"

## Scenario: AT-0008-08 — A refusal mid-answer replaces the partial text
* Given my chat provider is the fake Anthropic provider
* And the agent "Careful" exists
* When I start a chat with the agent "Careful", no embedding and the model "claude-fake-refuses-midway"
* And I send "Tell me something"
* Then the latest answer shows "The model declined to answer"
* And the latest answer does not show "Partial answer"

## Scenario: AT-0008-09 — Claude as a benchmark judge
* Given my provider is the fake LLM provider
* And the embedding "Docs" is built from "handbook.md"
* And the agent "Docs helper" exists
* And I have an "Anthropic" connection "Claude" to the fake Anthropic provider
* And the suite "Basics" exists
* And "Basics" is judged by the model "claude-opus-5-5" from "Claude"
* When I run "Basics" against the agent "Docs helper" with the embedding "Docs"
* Then the run is marked "Passed"
* And the judge's requests went to "claude-opus-5-5"

## Scenario: AT-0008-10 — Model lists come from each provider
* Given I have an "Anthropic" connection "Claude" to the fake Anthropic provider
* And I have a "Google" connection "Gemini" to the fake Google provider
* When I list the models of "Claude"
* Then I see "claude-opus-5-5"
* When I list the models of "Gemini"
* Then I see "gemini-fake"

## Implementation notes
- **Adapter layer** `backend/apps/providers/llm/`: one neutral `Adapter` interface
  (`stream_chat` → `Thinking` / `Text` / `ToolCall` / `Done(stop, raw)`, `complete`, `embed`,
  `list_models`) with `openai_compat.py`, `anthropic_adapter.py` (`anthropic` SDK) and
  `google_adapter.py` (`google-genai` SDK). `make_adapter(kind, …)`; callers use
  `providers.services.adapter_for()` / `chat_target()`. The agent loop, retrieval, rerank,
  judges and indexing are single code paths; the `agent.*` websocket events are unchanged.
  `test_architecture.py` now fails if a provider SDK is imported outside `providers/llm`.
- **Claude**: adaptive thinking with summarized display, explicit `effort` (new agent field
  "Reasoning effort", default high), no sampling params, cached system prompt, tools with eager
  input streaming, server-side refusal fallbacks on Opus 5.5 / Sonnet 5.5. The assistant turn's
  content blocks (signed thinking included) travel as the opaque `raw` turn and are resent
  unchanged within a run. A `refusal` stop becomes `agent.error` "The model declined to answer";
  errored replies drop their partial text (cancelled ones keep it).
- **Gemini**: thought summaries, automatic function calling off, model turn (with thought
  signatures) resent as `raw`, safety stops → refusal, embeddings via `embed_content`, models
  from `supported_actions`.
- `ProviderConfig` and `Connection` gained `kind` (migration providers 0004); base URL is
  optional for Anthropic/Google. Embedding form hides Anthropic endpoints.
- Fake LLM serves `/anthropic` (Messages API, signed thinking, refusals) and `/google`
  (streamGenerateContent, embeddings, models) so specs run the real SDKs offline.
- Not covered offline: a real cache hit (`cache_read_input_tokens`) — tests assert
  `cache_control` is set. Thinking blocks are resent within a run, not across chat turns
  (history between turns is text only).
- Wording fixed while building: "the embedding "Docs" is built from "handbook.md"" (was
  "covers", which clashed with a 0010 step), and AT-0008-09 gained "Given my provider is the
  fake LLM provider".
- New deps: `anthropic`, `google-genai` (uv downgraded `tenacity` 9.2.1 → 9.1.4).
