# 0005 — Agents + RAG chat

- **Status:** Done
- **Depends on:** 0003, 0004
- **Django apps:** `agents` + `chat`, using `rag` and `providers` services
- **Touches:** frontend, backend, jobs
- **Added while building (your request):** local models — extra OpenAI-compatible
  *connections* such as Ollama, chosen per agent (AT-07), and a fallback for models that
  can't call tools (AT-08).

## Why
The payoff: configure an agent (system message + RAG strategy) and chat with it, watching it
think, search, and answer from your documents in real time.

## Scope
- In: agent CRUD; per-agent RAG pipeline config; folder scoping; real `agent-run` task replacing
  `demo-agent`; saved conversations.
- Out: multi-agent orchestration, tools other than document search.

## Design notes
- `Agent(owner, name, system_message, connection?, model, folders[], rag_config JSON)`.
  `rag_config`: `query_transform` (none|multi_query|hyde|step_back), `retrieval`
  (dense|keyword|hybrid|mmr), `top_k`, `rerank` (none|llm), `generation`
  (stuff|cited|map_reduce|refine|corrective). Cross-encoder rerank is deferred (needs a local
  model download).
- `providers.Connection(owner, name, base_url, encrypted key)`: extra OpenAI-compatible
  endpoints (e.g. Ollama) an agent can answer with. Embeddings always use the default provider.
- `agent-run` Hatchet task: a tool-calling loop with `search_documents(query)`; streams the
  existing `agent.*` events; persists the final message.
- Chat page agent picker reads `GET /api/agents/` via React Query.

# Feature: Agents and RAG chat

## Background:
* Given I am signed in
* And my provider is the fake LLM provider

## Scenario: AT-0005-01 — Create an agent and pick it in Chat
* When I create the agent "Docs helper" with the system message "Answer only from my documents"
* Then I can choose "Docs helper" in Chat

## Scenario: AT-0005-02 — Answers cite the retrieved chunks
* Given "handbook.md" containing "The refund window is 30 days" is indexed
* And the agent "Docs helper" can search all my folders
* When I ask "Docs helper" "What is the refund window?"
* Then the answer cites "handbook.md"
* And every cited chunk is among the retrieved chunks shown

## Scenario: AT-0005-03 — Folder scoping
* Given "a.md" is indexed in "Folder A" and "b.md" in "Folder B"
* And the agent "Scoped" can only search "Folder A"
* When I ask "Scoped" a question both documents answer
* Then no retrieved chunk comes from "b.md"

## Scenario: AT-0005-04 — Hybrid retrieval changes results for keyword-heavy questions
* Given "error-codes.md" is indexed with one chunk per heading
* And an agent with dense retrieval and an identical agent with hybrid retrieval
* When I ask both "Which error code is E-4012?"
* Then the retrieved chunks differ and the hybrid agent's include the "E-4012" chunk

## Scenario: AT-0005-05 — Stop keeps the partial answer
* Given the agent "Docs helper" can search all my folders
* When I ask "Docs helper" a long question
* And I stop the agent while it is answering
* Then the partial answer stays visible marked "Stopped."

## Scenario: AT-0005-07 — An agent can answer with a local model
* Given I have a model connection "Local" to the fake LLM provider
* When I create the agent "Local helper" using the model "fake-local" from "Local"
* And I ask "Local helper" "Hello there"
* Then the answer comes from "Local · fake-local"

## Scenario: AT-0005-08 — Models without tool calling still answer from my documents
* Given "handbook.md" containing "The refund window is 30 days" is indexed
* And the agent "Basic" uses the model "fake-notools" from my default provider
* When I ask "Basic" "What is the refund window?"
* Then the answer cites "handbook.md"

## Scenario: AT-0005-06 — Conversations survive a reload
* Given I had a conversation with "Docs helper"
* When I reload the page
* Then I can open that conversation and see its messages

## Implementation notes
- `apps/rag`: `retrieval.py` (dense with the `vector(N)` cast for HNSW, keyword with OR-ed
  tsquery, RRF hybrid, MMR, multi-query / HyDE / step-back, LLM rerank), `generation.py`
  (stuff / cited / map-reduce / refine / corrective, shaping the search tool's result), `llm.py`.
- `apps/agents`: `Agent`, `runner.py` (streamed tool-calling loop, max 4 rounds, reads
  `reasoning_content`/`reasoning`, checks `ctx.is_cancelled` per token, falls back to
  retrieve-then-answer when the model rejects tools), `agent-run` task (no retries, 2 per user),
  `services.astart_run` (also routes the demo agent).
- `apps/chat`: `Conversation`/`Message` (reply metadata: thinking, tool calls, chunks, model),
  websocket handlers `agent.ask`/`agent.cancel` (moved here from jobs), REST
  `/api/chat/conversations/`. Stopped replies are saved as `cancelled` with the partial text.
- `apps/providers`: `Connection` + `/api/providers/connections/` (+ `/models/`), `chat_target()`.
- Frontend: Agents page + editor (model list from the endpoint), Chat with history (`?c=`),
  agent picker, citation chips, model label; Settings → Connections with an Ollama preset.
- Verified against a real local model: Ollama `gemma4:e4b` called `search_documents`, streamed
  its reasoning, and answered (2026-10-24).
- Spec changes while building: added the preconditions AT-04 and AT-05 were missing, put the
  refund sentence into `handbook.md`, and added AT-07/08 for local models (your request).
- The fake provider's embeddings are a toy 8-topic model that, like real embedders, ignores
  codes such as "E-4012" — that is what makes AT-04 show hybrid search's advantage.
