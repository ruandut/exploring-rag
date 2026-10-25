# Changelog

## 2026-10-24
- **0001 Foundation — Done.** JWT login, navigation drawer, authenticated websocket,
  Hatchet worker with `demo-index` (progress), `demo-agent` (streamed, cancellable) and
  `nightly-housekeeping` (cron). Fixed websocket drops caused by redis-py 8's 5 s socket timeout,
  and pinned the layout to the viewport so the chat composer never scrolls away.
- **0002 System Design page — Done.** Architecture diagram, live health, RAG step-by-step,
  realtime/job flows, Hatchet features, gotchas, glossary, spec index.
- Drafted 0003 (Library), 0004 (Settings), 0005 (Agents + chat) for review.
- **Architecture:** split the backend into layered Django apps (platform: core, accounts,
  realtime, jobs; domain skeletons: providers, library, rag, agents, chat, evals) with a test
  enforcing the import rules. Added a websocket handler registry and Hatchet task auto-discovery
  so domain apps plug into the platform without the platform importing them.
- Drafted **0006 Benchmarks**: eval suites, industry-standard metrics, boundaries, runs on Hatchet.
  Added Benchmarks nav item (preview) and an Evaluation tab on the System Design page.
- **0004 Settings — Done.** `apps/providers` (encrypted, write-only API key; Test connection with
  the provider's own error messages; `client_for(user)`) and `apps/rag` indexing settings with a
  confirmed re-index (Hatchet event `provider.embedding_changed` → `reindex-user-documents`).
  Settings UI with presets and a confirmation dialog.
- **Executable specs.** Specs are now `*.feature.md` (Markdown with Gherkin) run by Cucumber.js +
  Playwright from `acceptance/` (`make acceptance`). 0001, 0002 and 0004 are executable and pass
  (24 scenarios); drafts 0003/0005/0006 were rewritten as scenarios. System Design gained a
  Testing tab and reads the spec list from the files.
- **0003 Library — Done.** Nested folders, multi-file upload (PDF/DOCX/MD/TXT), live per-document
  status over the websocket, re-index, move, delete; full indexing pipeline in `rag` (parse →
  five chunking strategies → batched embeddings → pgvector + tsvector) on Hatchet, triggered by
  `document.*` events. Chunk inspector in the UI. The demo job moved to System Design.
- **0005 Agents + RAG chat — Done.** Agents (system message, model, folders, RAG pipeline:
  query transforms, dense/keyword/hybrid/MMR retrieval, LLM rerank, five generation
  strategies), a streamed tool-calling agent loop on Hatchet, conversations saved with their
  thinking/tool calls/chunks, citations. **Local models:** model connections (Ollama) chosen per
  agent, and a retrieve-then-answer fallback for models without tool calling. Verified with
  Ollama `gemma4:e4b`. Spec 0001's drawer scenario now lists Agents.
- **0006 reviewed and rewritten** (still Draft): decisions recorded (reusable suites, own
  documents only, no cost yet, relevance by document + evidence, n/a for bare models, in-app
  retry), missing preconditions added, 12 scenarios. Split into three Django apps — `scoring`,
  `evals`, `benchmarks` (skeletons created, layering enforced). Deferred features drafted as
  **0007 Benchmarks II**.
- **0006 Benchmarks — Done.** Suites (cases with relevant documents + evidence, metrics, judge,
  boundaries, JSONL), runs against an agent or a bare model on any connection, Hatchet fan-out
  with live progress, per-case drill-down showing the maths or the judge's reasoning, retry,
  and side-by-side comparison. Three apps: `scoring`, `evals`, `benchmarks`. Verified with a
  local Gemma judge, which exposed (and led to fixing) cut-off judge replies from reasoning models.
  Public datasets dropped from 0007 (your call).

## 2026-10-25
- **0007 reviewed and rewritten** (still Draft): repeats default to 1; tokens only — no dollar
  costs or price table; unreported usage is estimated and labelled; direct *and* indirect
  (planted-document) prompt injection with canaries; generated evidence must appear verbatim;
  CSV import + export. Scenarios now test both the passing and failing side. 9 scenarios.
- **Chat composer redesigned** after Claude's text bar: one rounded card with an auto-growing
  text area, the agent picker and send/stop inside it, and a centred greeting + composer for
  empty chats. The message box now has the accessible name "Message".
- **Drafted 0009 Delete a chat** (your request): delete from the chat list behind a confirmation
  dialog, messages cascade, owner-only (another user's id → 404), deleting the open chat returns
  to an empty chat, and a reply still streaming is cancelled first (new
  `Conversation.active_run_id`); 5 scenarios.
- **0009 Delete a chat — Done.** Trash button per chat behind a confirmation dialog;
  `DELETE /api/chat/conversations/<id>/` goes through `chat.services.delete_conversation`
  (owner-only → 404, messages cascade). A reply still streaming is cancelled first: the run is
  now recorded on the conversation (`active_run_id`), and `send_to_user(cancel_background=…)`
  stops the relay on whichever socket owns it. Deleting the open chat returns to an empty chat.
