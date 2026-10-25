# 0010 — Embeddings: named indexes you build, compare and chat with

- **Status:** Done
- **Depends on:** 0003 (library), 0004 (providers), 0005 (agents, chat), 0006 (benchmarks)
- **Django apps:** `rag` (owns `EmbeddingIndex`, its folders/documents, chunking, indexing),
  `providers` (model catalogue for the picker), `agents` (loses folders, connection and model;
  keeps system message + retrieval strategy), `chat` (conversation remembers agent + embedding
  + LLM), `benchmarks` (a run targets agent + embedding + LLM)
- **Touches:** frontend (new **Embeddings** menu section, chat pickers + settings header,
  Settings slimmed down), backend, jobs, websocket contract, docs (**changes CLAUDE.md
  conventions and the apps table**, ARCHITECTURE.md, System Design page)

## Why
Today every user has exactly one embedding: one model, one chunking setting, all documents.
You can't answer the question "would a different embedding model (or chunk size) find better
passages for my documents?" without throwing the old index away.

With this spec an **embedding** is something you create: a name, a set of folders/files, an
embedding model and chunking settings. You can keep several side by side, over the same
documents or different ones, and in Chat you pick which one to search, together with the
agent and the LLM. The chat shows what it's using, and Benchmarks can compare two embeddings
on the same suite.

What you learn: why every vector in one index must come from one model (and how pgvector
partial indexes per dimension make several models in one table work), how chunking and the
model interact, and how to compare retrieval set-ups objectively.

## Decisions (2026-10-25)
1. **Embeddings get their own menu section.** An embedding = name + folders and/or files +
   endpoint + model + chunking. Creating one starts indexing; you can edit its folders, change
   its model/chunking (confirmed re-index) and re-index it from there.
2. **Chat picks three things:** **Agent** (system message + retrieval strategy: query
   transforms, dense/keyword/hybrid/MMR, rerank, generation), **Embedding** (what is searched),
   **Model** (the LLM that answers). Agents no longer own folders, a connection or a model.
   An agent alone doesn't decide what gets searched.
3. **Chunking is per embedding** (strategy, size, overlap), so "small chunks + model A" can be
   compared with "large chunks + model B". The per-user Indexing settings tab goes away.
4. **Text only.** Image models and image embeddings are out of scope for now.
5. **0010 takes over embeddings from 0008.** 0008 drops its single `EmbeddingConfig` and the
   Embeddings tab, and keeps Anthropic/Google for chat, judges and model lists. 0008 now depends
   on 0010 and adds Google as an embeddings endpoint. Done in this change, with your OK.
6. **Benchmarks target an embedding too.** The run comparison shows each run's embedding, so
   two embeddings can be compared on the same suite.
7. **The model picker** (originally the whole of this spec) replaces every free-text model
   field: the embedding's model, the chat's model, the default provider's chat model and the
   benchmark model/judge. A custom model id is always allowed.

## Scope
- In: Embeddings section (list with status, create, edit folders/files, change model or
  chunking with confirmation, re-index, delete); indexing per embedding on Hatchet with live
  status; chat choosing agent + embedding (or **None**) + model, remembered per conversation
  and shown in a settings header; changing them mid-chat for the next answer; each answer
  records what produced it; benchmarks with an embedding; the model picker with kinds and
  dimensions; migration of today's data into one embedding with no re-index.
- Out (later specs): image/vision models and image embeddings; searching several embeddings in
  one answer (fusion across indexes); sharing embeddings between users; pulling Ollama models
  from the app; prices and context windows.

## CLAUDE.md / architecture changes (raised for review, applied when built)
- Convention "Embeddings always use the default provider (every vector must come from one
  model)" becomes **"Every vector in an embedding index comes from that index's one model;
  retrieval searches one index at a time, embedding the query with that index's model."**
- Event `provider.embedding_changed` is **removed**: the model lives on the index, inside
  `rag`, so changing it doesn't need to cross layers. `document.uploaded` /
  `document.reindex_requested` now fan out to **every index that covers the document**. New
  library event **`document.moved`**, because a move can take a document into or out of an
  index's folders. `apps/jobs/events.py` updated.
- Apps table: `rag` owns embedding indexes; `agents` no longer owns folders; **`chat` may
  import `rag`** (a conversation references an index), so `ALLOWED_DEPENDENCIES` gets
  `chat → rag`. `benchmarks` already may import `rag`.
- Websocket contract (`socket.ts` + emitter): new **`embedding.status`**
  `{embedding_id, status, done, total, error?}`. `agent.ask` gains `embedding_id` (nullable),
  `connection_id`, `model`, and `agent.done` already carries `model`. `document.status` stays
  (a document's worst state across its indexes).
- Redis stays Channels-only. Nothing new is cached server-side.

## Design notes
**Data model** (`rag`):
```
EmbeddingIndex(owner, name, connection → providers.Connection | null (= default provider),
               model, dimensions, strategy, chunk_size, chunk_overlap,
               status: indexing|ready|failed, created/updated)
EmbeddingIndexFolder(index, folder)       # a folder includes its subfolders
EmbeddingIndexDocument(index, document)   # single files picked directly
Chunk + index FK (EmbeddingIndex, cascade); unique (index, document, position)
```
`Chunk.embedding_model` / `dimensions` stay (the HNSW partial indexes per dimension need them).
Retrieval adds `WHERE index_id = …`, so two indexes of the same model never mix. An
embedding's documents = documents in its folders (recursively) ∪ its picked documents,
resolved by a selector at query time, never copied.

**Indexing** — `index-document` takes `(index_id, document_id)`; parsing is cached per
document (parse once, chunk + embed per index). Event handlers work out which indexes cover
the document and enqueue one task each. `reindex-embedding` (index_id) fans out the same
way. Editing folders/files only indexes what was added and deletes chunks of what was
removed, with no full re-index. Changing endpoint, model, dimensions or chunking asks
**"Re-index this embedding?"** (409 + confirm, like today) and rebuilds just that index.
Progress → `embedding.status`.

**Migration (no re-index):** for every user with a provider, create one embedding "My
documents" with all their top-level folders, the provider's embedding model/dimensions and
their `IndexingConfig`, and attach every existing chunk to it. Each agent's folders become
nothing (the agent no longer owns them). Its connection/model are copied onto its existing
conversations as their model, and every conversation gets "My documents" as its embedding.
`ProviderConfig.embedding_*` and `IndexingConfig` are dropped after the copy.

**Agents** keep name, system message and `rag_config` (retrieval strategy). The answer
pipeline gets the index, connection and model as arguments from the run input instead of
reading them from the agent. The "models without tool calling" fallback still applies, decided
by the chosen model. With embedding **None** the `search_documents` tool isn't offered and
the agent answers from the model alone.

**Chat** — a new chat shows three pickers in the composer: **Agent**, **Embedding**, **Model**
(the picker, with "No tools" badges). Defaults for a new chat = the last ones you used.
The conversation stores them; a header line shows them, e.g. "Docs helper · Embedding: Handbook
small (fake-embed, 8 dims, recursive 512/64) · Model: Default provider · fake-chat". Changing
any of them mid-chat applies from the next message, and each assistant message stores what
produced it (`agent`, `embedding` name + model, `model` label), shown on the message.
If the conversation's embedding was deleted, the header says "Embedding deleted — pick another".

**Benchmarks** — "Run against" an agent now also asks for an embedding and a model (bare
model runs unchanged: retrieval metrics n/a). `target_snapshot` records the embedding (name,
model, dimensions, chunking) so old runs stay readable after edits. The comparison view shows
each side's embedding.

**Settings** — the Default provider form keeps base URL, key and chat model. Its embedding
fields and the Indexing tab move into each embedding. Test connection checks chat only. The
embedding form has its own **Test** (one embedding call → dimensions).

**Model picker** — `GET /api/providers/models/?kind=embedding|chat`,
`/connections/<id>/models/?kind=…` and `POST /models/probe/` (unsaved base URL + key) return
`[{id, kind: chat|embedding|unknown, source: endpoint|known|guessed, dimensions, tools}]` plus
an `endpoint` type and a `hint`. Kinds come from, in order:
1. **Endpoint metadata:** Ollama (detected by `GET <root>/api/version`) `/api/show`
   capabilities + `embedding_length`; OpenRouter `architecture` modalities; with 0008, Google
   generation methods and Anthropic (all chat).
2. **Built-in table** of well-known models (e.g. `text-embedding-3-small` 1536,
   `text-embedding-3-large` 3072, `nomic-embed-text` 768, `mxbai-embed-large` 1024,
   `bge-m3` 1024, `all-minilm` 384).
3. **Name guess** (`embed`, `bge`, `e5-`, `gte-`, `minilm`), labelled "guessed from the name".
4. Otherwise **Unknown**, which is always listed.

UI: shadcn `Command` in a `Popover` (combobox) named after its field, with search, groups
Embedding / Chat / Unknown, "Show all models", **Use “<id>”** for custom ids, and dimensions
filled in when known. An empty Embedding group shows the endpoint's hint: Ollama "Run `ollama
pull nomic-embed-text`, then press Refresh"; OpenAI "Try text-embedding-3-small";
OpenRouter "OpenRouter has no embedding models — use another connection". An unreachable
endpoint shows its own error and still allows a custom id. `/api/show` calls run at most 8
at a time with a 5 s timeout. React Query caches lists for 5 minutes, and Refresh reloads.

**Acceptance fake server** additions: an Ollama personality under `/ollama/…`
(`/api/version`, `/api/tags`, `/api/show`: `fake-embed` embedding 8 dims, `fake-embed-16`
embedding 16 dims, `fake-chat` completion + tools, `fake-notools` completion only); any model
named `…-<n>` embeds into `n` dimensions; a `/bare/…` endpoint listing `acme-embed-small` and
`mystery-7b` with no metadata; a `/chat-only/…` endpoint listing no embedding models.

pytest (named `test_at_0010_<nn>_…` where it backs a scenario): migration attaches existing
chunks to "My documents" with no embedding calls; documents resolved through nested folders
and picked files; folder edits index only the difference; retrieval never crosses indexes;
moves fire `document.moved` and update coverage; owner scoping of indexes, chunks and model
lists; architecture guard with `chat → rag`; detection sources and fallbacks.

# Feature: Embeddings you build, compare and chat with

## Background:
* Given I am signed in
* And my provider is the fake LLM provider

## Scenario: AT-0010-01 — Creating an embedding indexes its folders
* Given I have the folder "Policies"
* And I upload "handbook.md" to "Policies"
* When I create the embedding "Handbook small" with the folder "Policies" and the model "fake-embed"
* Then the embedding "Handbook small" shows "Ready"
* And the embedding "Handbook small" covers "handbook.md"

## Scenario: AT-0010-02 — Single files can be picked as well as folders
* Given I have the folder "Policies"
* And I upload "handbook.md" to "Policies"
* And I upload "faq.md" to "Policies"
* When I create the embedding "Just FAQ" with the file "faq.md" and the model "fake-embed"
* Then the embedding "Just FAQ" covers "faq.md"
* And the embedding "Just FAQ" does not cover "handbook.md"

## Scenario: AT-0010-03 — Two embeddings of the same documents keep separate vectors
* Given "handbook.md" is indexed
* When I create the embedding "Small" with all my folders and the model "fake-embed"
* And I create the embedding "Wide" with all my folders and the model "fake-embed-16"
* Then the chunks of "handbook.md" in "Small" have 8-dimensional embeddings
* And the chunks of "handbook.md" in "Wide" have 16-dimensional embeddings

## Scenario: AT-0010-04 — Chunking is set per embedding
* Given "handbook.md" is indexed
* When I create the embedding "Fine" with all my folders, the model "fake-embed" and chunk size 64
* And I create the embedding "Coarse" with all my folders, the model "fake-embed" and chunk size 1024
* Then "Fine" has more chunks than "Coarse"

## Scenario: AT-0010-05 — Adding a folder indexes only the new documents
* Given the embedding "Handbook small" covers the folder "Policies"
* And I have the folder "Support" containing "faq.md"
* When I add the folder "Support" to the embedding "Handbook small"
* Then the embedding "Handbook small" shows "Ready"
* And the embedding "Handbook small" covers "faq.md"
* And only "faq.md" was sent to be embedded

## Scenario: AT-0010-06 — Removing a folder removes its documents from the embedding
* Given the embedding "Handbook small" covers the folders "Policies" and "Support"
* When I remove the folder "Support" from the embedding "Handbook small"
* Then the embedding "Handbook small" does not cover "faq.md"
* And "faq.md" is still in my library

## Scenario: AT-0010-07 — A new upload is indexed in every embedding that covers its folder
* Given the embedding "Small" covers the folder "Policies" with the model "fake-embed"
* And the embedding "Wide" covers the folder "Policies" with the model "fake-embed-16"
* When I upload "faq.md" to "Policies"
* Then the embedding "Small" covers "faq.md"
* And the embedding "Wide" covers "faq.md"

## Scenario: AT-0010-08 — Changing an embedding's model asks to re-index it
* Given the embedding "Handbook small" covers the folder "Policies" with the model "fake-embed"
* When I change the model of "Handbook small" to "fake-embed-16"
* Then I am asked "Re-index this embedding?"
* When I press "Save and re-index"
* Then the embedding "Handbook small" shows "Ready"
* And the chunks of "handbook.md" in "Handbook small" have 16-dimensional embeddings

## Scenario: AT-0010-09 — Re-indexing from the Embeddings page shows live progress
* Given the embedding "Handbook small" covers the folder "Policies"
* When I re-index the embedding "Handbook small"
* Then the embedding "Handbook small" shows "Indexing"
* And then shows "Ready" without reloading the page

## Scenario: AT-0010-10 — The model picker offers the endpoint's embedding models with their dimensions
* Given I have a connection "Local" to the fake Ollama provider
* When I start a new embedding using the connection "Local"
* And I open the "Embedding model" picker
* Then the picker offers "fake-embed"
* And the picker does not offer "fake-chat"
* When I choose "fake-embed" in the "Embedding model" picker
* Then the "Dimensions" field shows "8"

## Scenario: AT-0010-11 — A custom model id can be used, and an unknown model stays visible
* Given I have a connection "Bare" to the fake bare provider
* When I start a new embedding using the connection "Bare"
* And I open the "Embedding model" picker
* Then "acme-embed-small" is marked "guessed from the name"
* And the picker offers "mystery-7b" under "Unknown"
* When I search the "Embedding model" picker for "my-own-embedder"
* And I press "Use “my-own-embedder”"
* Then the "Embedding model" field shows "my-own-embedder"

## Scenario: AT-0010-12 — No embedding models shows how to get one
* Given I have a connection "Local" to the fake Ollama provider
* And the fake Ollama provider has no embedding models
* When I start a new embedding using the connection "Local"
* And I open the "Embedding model" picker
* Then I see "ollama pull nomic-embed-text"

## Scenario: AT-0010-13 — A chat uses the agent, embedding and model I choose, and shows them
* Given the embedding "Handbook small" covers the folder "Policies"
* And the agent "Docs helper" exists
* When I start a chat with the agent "Docs helper", the embedding "Handbook small" and the model "fake-chat"
* And I send "What is the refund window?"
* Then the chat settings show "Docs helper", "Handbook small" and "fake-chat"
* And the answer cites "handbook.md"
* And the answer comes from "Default provider · fake-chat"

## Scenario: AT-0010-14 — The answer only searches the chosen embedding
* Given the embedding "Policies only" covers the folder "Policies"
* And the embedding "Support only" covers the folder "Support"
* And the agent "Docs helper" exists
* When I start a chat with the agent "Docs helper", the embedding "Support only" and the model "fake-chat"
* And I send "What is the refund window?"
* Then no retrieved chunk comes from "handbook.md"

## Scenario: AT-0010-15 — Switching the embedding mid-chat applies to the next answer
* Given the embedding "Small" covers the folder "Policies" with the model "fake-embed"
* And the embedding "Wide" covers the folder "Policies" with the model "fake-embed-16"
* And I had a chat with the embedding "Small"
* When I switch the chat's embedding to "Wide"
* And I send "What is the refund window?"
* Then the latest answer shows it used "Wide"
* And the previous answer still shows it used "Small"

## Scenario: AT-0010-16 — The chat's model picker marks models without tool calling
* Given I have a connection "Local" to the fake Ollama provider
* When I start a new chat
* And I open the "Model" picker for the connection "Local"
* Then "fake-notools" is marked "No tools"
* And the picker does not offer "fake-embed"

## Scenario: AT-0010-17 — Benchmarks compare two embeddings on the same suite
* Given the embedding "Small" covers the folder "Policies" with the model "fake-embed"
* And the embedding "Wide" covers the folder "Policies" with the model "fake-embed-16"
* And the agent "Docs helper" exists
* And the suite "Basics" exists
* When I compare "Basics" on the agent "Docs helper" with the embeddings "Small" and "Wide"
* Then I see both runs side by side with per-metric deltas
* And each run shows its embedding

## Scenario: AT-0010-18 — Deleting an embedding is confirmed and its chats ask for another
* Given the embedding "Handbook small" covers the folder "Policies"
* And I had a chat with the embedding "Handbook small"
* When I delete the embedding "Handbook small"
* Then I am asked "Delete this embedding?"
* When I press "Delete"
* Then "handbook.md" is still in my library
* And that chat says "Embedding deleted — pick another"

## Implementation notes
Built in four phases (2026-10-25); all 18 scenarios pass, with `make test` and `make check`.

- **rag:** `EmbeddingIndex` (coverage: `all_documents` | folders | picked files, endpoint +
  model + dimensions, chunking, status, `version`), `IndexedDocument` (one document's state in
  one embedding), `ParsedText` (parse once per document), `Chunk.embedding_index`. Tasks:
  `route-document` (on `document.uploaded|moved|reindex_requested`), `sync-embedding` (create /
  edit / re-index: indexes only what was gained, all on a re-index), `index-document`
  (per document per embedding). A run queued for an older `version` throws its vectors away.
  API `/api/rag/embeddings/` (+ `reindex`, `documents`, `test`); 409 `reindex_required` for
  endpoint/model/dimensions/chunking changes. Retrieval filters on `embedding_index_id`.
- **Decisions made while building (tell me if you'd rather have it otherwise):**
  - An **"All documents"** option (also covers top-level files and future folders); the
    migrated "My documents" and the step "with all my folders" use it, instead of copying
    today's top-level folders.
  - A document no embedding covers shows **"Not indexed"** (new library status).
  - The dimensions field is cleared when the model changes; the picker or the first indexing
    run fills it in.
- **chat:** `Conversation.embedding` (+ `embedding_name`, so a deleted one reads "pick
  another"), `connection`, `model`; `agent.ask` carries the picks, which apply from that
  message; each reply's metadata records agent + embedding + model. A new chat starts with the
  last chat's picks (else the oldest embedding and the default provider).
- **agents** lost `connection`, `model`, `folders` (copied onto conversations by
  `chat/0004`); with embedding None the model answers alone (`mode: "model"`).
- **benchmarks:** agent targets take `embedding` / `connection` / `model`; the snapshot keeps
  the embedding's name, model, dimensions and chunking; a deleted embedding fails the case.
- **providers:** `catalog.py` (Ollama `/api/version` + `/api/show`, OpenRouter modalities,
  built-in table, name guess, unknown always listed); `?kind=` on model lists and
  `POST /models/probe/`. The embedding field no longer lives on the provider.
- **Frontend:** Embeddings page, chat pickers + settings line, `ModelCombobox`
  (shadcn Command + Popover; `cmdk` added) for embedding, chat, Settings, benchmark and judge
  models. Settings lost the Indexing tab.
- **Specs reworded:** 0003 (Background creates "My documents"), 0004 (Test connection is chat
  only; the overlap check is on the embedding form; re-index scenarios moved here), 0005
  (folder scoping = an embedding; the chat picks the model), 0006 / 0009 ("the agent … exists").
- **Tests:** pytest in `rag/test_embeddings.py` (incl. the migration), `rag/test_retrieval.py`,
  `chat/test_chat.py`, `agents/test_runner.py`, `benchmarks/test_benchmarks.py`,
  `providers/test_catalog.py`; the fake server gained sized embeddings and Ollama / bare /
  chat-only personalities.
