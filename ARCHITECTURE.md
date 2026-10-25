# Architecture — what is used for what

> Kept in sync with the in-app **System Design** page (`frontend/src/features/system-design/content.ts`).
> Last updated: 2026-10-24 (specs 0001–0006 done; executable specs; Django app layering).
> Status: ✅ live · 🧪 demo (wired with fake data) · 📝 planned (spec drafted)

## The picture

```
                    ┌──────────────┐  ORM   ┌────────────────────────┐        ┌──────────────┐
          REST+JWT  │  Django API  │───────▶│ Postgres + pgvector    │◀───────│ LLM provider │ 📝
   ┌───────────────▶│  DRF         │        │ db "rag" + db "hatchet"│ vectors│ OpenAI-compat│
   │                └──────┬───────┘        └───────────▲────────────┘   ┌────┴──────▲───────┘
   │                       │ start run                   │ state         │           │ HTTPS
┌──┴──────┐                ▼                             │               │           │
│ Browser │         ┌─────────────────────────────────────┴─┐   gRPC   ┌──┴───────────┴─┐
│ React   │         │ Hatchet engine (hatchet-lite)          │◀────────▶│ Hatchet worker │
│ (Vite+) │         │ queue · retries · concurrency · cron   │          │ (Django tasks) │
└──┬──────┘         │ streams · dashboard :8888              │          └───────┬────────┘
   │                └─────────────────────▲─────────────────┘                  │ progress
   │ WebSocket      ┌──────────────┐      │ run + subscribe to stream          │ events
   └───────────────▶│  Channels    │──────┘                                    ▼
                    │  /ws/events/ │◀──────────── group_send ───────── ┌──────────────┐
                    └──────────────┘                                   │ Redis        │
                                                                       │ channel layer│
                                                                       └──────────────┘
```

## Technology → responsibility

### Frontend (`frontend/`)
| Tech | Used for | Where |
|---|---|---|
| **Vite+** (`vp`) | Dev server, build, lint (Oxlint), format (Oxfmt), type-check, tests, dependency management | `vite.config.ts`, `package.json` scripts |
| **React 19** | UI | `src/` |
| **TanStack Router** | File-based routes, auth guard (`beforeLoad`), code-splitting | `src/routes/` — `_app.tsx` is the authenticated layout |
| **React Query** | All server state (`/api/*`): caching, refetching, mutations | `useQuery` / `useMutation` in routes; client in `main.tsx` |
| **shadcn/ui** | Components (sidebar/nav drawer, cards, tabs, forms…), vendored into the repo | `src/components/ui/` |
| **Tailwind v4** | Styling, theme tokens, dark mode | `src/index.css` |
| **next-themes** | Light/dark/system theme toggle | `main.tsx`, user menu |
| **sonner** | Toast notifications | `components/ui/sonner.tsx` |
| Native **WebSocket** | Single live connection per tab; auto-reconnect; JWT as first message | `src/lib/socket.ts` |

### Backend (`backend/`)
| Tech | Used for | Where |
|---|---|---|
| **uv** | Python version, venv, dependencies, running commands | `pyproject.toml`, `uv.lock` |
| **Django 6** | Project, ORM, admin, migrations | `config/`, `apps/*` |
| **DRF** | REST endpoints, validation (serializers), permissions | `apps/*/views.py` |
| **SimpleJWT** | Login (access 15 min + rotating refresh 7 days) | `apps/accounts/` |
| **Channels + Daphne** | ASGI server; websocket consumer at `/ws/events/` | `config/asgi.py`, `apps/realtime/` |
| **channels-redis** | Channel layer so other processes (workers) can reach a user's sockets | `CHANNEL_LAYERS` in settings |
| **Hatchet SDK** | Define tasks, start runs, stream, cancel, cron; the worker process | `apps/jobs/` |
| **pgvector** (Python) | `VectorField` + extension migration | `apps/core/migrations/0001_pgvector.py`, `apps/rag/models.py` |
| **pypdf**, **python-docx** | Extracting text from PDF and Word files | `apps/rag/parsing.py` |
| **django.contrib.postgres** | Generated `tsvector` + GIN index for keyword search | `apps/rag/models.py` |
| **openai** SDK | Talking to any OpenAI-compatible endpoint (chat + embeddings) | `apps/providers/services.py` |
| **cryptography** (Fernet) | Encrypting LLM API keys at rest (`FIELD_ENCRYPTION_KEY`) | `apps/providers/crypto.py` |
| **django-environ** | Settings from `backend/.env` | `config/settings.py` |
| **pytest / pytest-django / ruff** | Tests and lint/format | `conftest.py`, `apps/*/test_*.py` |

### Backend Django apps (layered)

Lower layers never import higher ones — enforced by `apps/core/test_architecture.py`.

```
 Layer 5 │                     benchmarks
 Layer 4 │  chat
 Layer 3 │  agents            evals
 Layer 2 │  rag               scoring
 Layer 1 │  library           providers
 ────────┼──────────────────────────────────────  domain ▲  platform ▼
Platform │  jobs ─▶ realtime ─▶ core ◀─ accounts
```
An app may import only from lower layers, and only the ones listed for it in
`ALLOWED_DEPENDENCIES` (e.g. `chat` → agents, providers; `evals` → library, providers, scoring; `scoring` → providers;
`benchmarks` → evals, scoring, agents, rag, library, providers).

| App | Layer | Owns | Status |
|---|---|---|---|
| `core` | platform | health, pgvector extension, shared base code | ✅ |
| `accounts` | platform | users, JWT login/refresh, `/me` | ✅ |
| `realtime` | platform | websocket gateway, `send_to_user()`, ws message-handler registry | ✅ |
| `jobs` | platform | Hatchet client, worker, task auto-discovery, demo tasks + demo ws handlers | ✅ |
| `providers` | domain | default provider (Fernet-encrypted key), extra **connections** (e.g. Ollama), `chat_target()`, model lists, Test connection | ✅ 0004–0005 |
| `library` | domain | folders, documents, uploads, statuses; emits `document.uploaded` / `document.reindex_requested` | ✅ 0003 |
| `rag` | domain | indexing (parse, chunk, embed, store) + answering (`retrieval.py`, `generation.py`) | ✅ 0003–0005 |
| `agents` | domain | agent config, agent loop (`runner.py`), `agent-run` task | ✅ 0005 |
| `chat` | domain | conversations + messages, `agent.ask`/`agent.cancel` websocket handlers | ✅ 0005 |
| `scoring` | domain | **how to score**: retrieval metrics, LLM-judge rubrics, aggregation, boundaries — no models | ✅ 0006 |
| `evals` | domain | **what to test**: suites, cases (relevant documents + evidence), metrics, boundaries, judge, JSONL | ✅ 0006 |
| `benchmarks` | domain | **running tests**: runs, case results, Hatchet fan-out, live progress, comparisons, retries | ✅ 0006 |

How domain apps plug into the platform without the platform importing them:
- **Websocket**: `@ws_handler("agent.ask")` in the app, imported from `AppConfig.ready()`.
- **Background work**: `TASKS = [...]` in `<app>/tasks.py`, discovered by the worker.
- **Lower → higher triggers**: Hatchet events (`on_events=[...]`) or Django signals.

### Infrastructure (`docker-compose.yml`)
| Service | Used for | Port |
|---|---|---|
| **Postgres 18 + pgvector 0.8** | App data, documents, chunks + embeddings (HNSW), Hatchet's own DB | 5432 |
| **Redis 8** | Channels layer **only** | 6379 |
| **hatchet-lite** | Hatchet engine + API + dashboard; uses Postgres as its queue (no RabbitMQ) | 8888 UI, 7077 gRPC |
| **Ollama** (optional, on the host) | Local models for agents (e.g. `gemma4:e4b`), added as a connection | 11434 |

## Who calls whom

| From → To | How | Why |
|---|---|---|
| Browser → API | `fetch /api/*` with `Authorization: Bearer` (Vite proxies in dev) | CRUD, login, start jobs |
| Browser ↔ Channels | WebSocket `/ws/events/`, first message `{type:"auth"}` | Live progress + agent streams |
| API → Hatchet | `task.run_no_wait(input)` | Queue background work, return `run_id` immediately (202) |
| Channels (chat handler) → agents → Hatchet | `agents.services.astart_run` → `agent_run.aio_run_no_wait`; `runs.subscribe_to_stream`; `runs.aio_cancel` | Agent runs streamed to the socket that asked; reply saved by chat |
| Hatchet → Worker | gRPC assignment | Executes tasks with retries/concurrency/rate limits |
| Worker → Redis → Channels | `asend_to_user()` → `group_send("user.<id>")` | Job progress reaches every open tab |
| Worker → Postgres | Django ORM | Store chunks/vectors, read config |
| Worker → LLM | OpenAI-compatible HTTP (streaming) | ✅ embeddings via the default provider; chat via the agent's connection (default or e.g. Ollama at `localhost:11434/v1`) |
| API → LLM | OpenAI-compatible HTTP | Settings → Test connection (one tiny chat + one embedding call) |
| providers → rag | Hatchet event `provider.embedding_changed` | Lower layer triggers higher layer without importing it |
| library → rag | Hatchet events `document.uploaded`, `document.reindex_requested` | Same pattern for indexing |
| rag → library | `library.services.set_status()` | Higher layer may call lower; also sends websocket `document.status` |

## Hatchet tasks

| Task | Trigger | Features | Status |
|---|---|---|---|
| `demo-index` | `POST /api/jobs/demo-index/` | retries=2, exponential backoff, max 2 concurrent per user, progress events | ✅ (fake work) |
| `demo-agent` | websocket `agent.ask` | streams `agent.*` events, cancellable | 🧪 |
| `nightly-housekeeping` | cron `0 3 * * *` | cron | ✅ (no-op) |
| `reindex-user-documents` (rag) | chunking change, or event `provider.embedding_changed` | queues one `index-document` per document; 1 per user (cancels older) | ✅ |
| `index-document` (rag) | events `document.uploaded`, `document.reindex_requested` | parse → chunk → embed → store; 3 per user; retries 2; user errors non-retryable | ✅ |
| `agent-run` (agents) | websocket `agent.ask` (via chat) | streamed tool-calling loop; no retries; 2 per user; checks `ctx.is_cancelled` per token; no-tools fallback | ✅ |
| `benchmark-run` → `benchmark-case` (benchmarks) | Benchmarks → Run / Retry failed cases | child runs via `run_many`, 2 per user, children record failures instead of raising; parent aggregates + checks boundaries | ✅ |
| `generate-testset` (evals) | Benchmarks → Generate | LLM writes Q/A/evidence + refusal cases from sampled chunks | 📝 0007 |

## RAG pipeline (where each step will live)

| Step | Implementation | Status |
|---|---|---|
| Upload & store | DRF multipart → `Document(queued)` → event `document.uploaded` on commit | ✅ |
| Parse | pypdf / python-docx / UTF-8 by extension; empty → failed with reason | ✅ |
| Chunk | Fixed / recursive / markdown / semantic / parent-document, approximate tokens | ✅ |
| Embed | User's embeddings endpoint, batches of 64, heading path prepended | ✅ (rate limits 📝) |
| Store | `Chunk.embedding vector` + `dimensions`, partial HNSW per size, generated `tsvector` + GIN | ✅ |
| Query transform | none / multi-query / HyDE / step-back (per agent) | ✅ |
| Retrieve | pgvector `<=>` cast to `vector(N)`, full-text (OR-ed lexemes), hybrid RRF, MMR, top-k, folder scope | ✅ |
| Rerank | LLM rerank ✅; cross-encoder 📝 (needs a local model) | ✅ |
| Augment | system message + RAG rules + last 20 messages + `[doc#chunk]`-tagged passages | ✅ |
| Generate | stuff / cited / map-reduce / refine / corrective, streamed | ✅ |
| Agent loop | `search_documents` tool, ≤4 rounds, retrieve-then-answer fallback for non-tool models | ✅ |
| Stream to UI | `ctx.aio_put_stream` → consumer → websocket → Chat | ✅ |

## Testing — executable specs

Specs are Markdown that Cucumber executes (Specification by Example / BDD).

```
specs/NNNN-name.feature.md  ──▶  Cucumber.js  ──▶  acceptance/steps/*.steps.ts
 (prose + # Feature:             (Markdown with      (thin: read like the spec)
  ## Scenario: AT-… bullets)      Gherkin parser)             │
                                                              ▼
            acceptance/pages/* (Playwright page objects) · support/app.ts (ApiClient, test users)
            support/socket.ts (SocketClient) · support/fake-llm.ts (OpenAI-compatible fake)
                                                              │
                                                              ▼
                     running app: Vite :5173 → Django/Channels :8000 → Hatchet worker
```

| Layer | Tool | Proves | Command |
|---|---|---|---|
| Executable specs | Cucumber.js 13, Playwright (Chromium), `ws`, fetch | Behaviour promised in each spec, end to end | `make acceptance` |
| Unit / integration | pytest, pytest-django, Channels communicator | Services, serializers, permissions, consumer protocol | `make test` |
| Architecture guard | pytest + `ast` | Django app layering | `make test` |
| Static | ruff, Oxlint (type-aware), tsc | Style, lint, types | `make check` |

- Only specs with Status Approved / In progress / Done run (`acceptance/cucumber.mjs`); strict
  mode fails on undefined steps.
- Every scenario: fresh user (`manage.py create_test_user`, DEBUG only), fresh browser context
  and sockets. Failures attach a screenshot to `acceptance/reports/acceptance.html`.
- No real LLM in specs — a local fake server; real-model quality is Benchmarks' job.
- The System Design page reads `specs/*.md` at build time, and spec 0002 checks the page lists
  every spec and Django app on disk, so docs can't drift silently.

## Evaluation (spec 0006)

| Group | Metrics | Scored by |
|---|---|---|
| Retrieval | hit rate@k, recall@k, precision@k, MRR, nDCG@k | exact maths vs labelled relevant chunks |
| Generation | faithfulness, answer relevancy, context precision/recall, answer correctness, citation accuracy | LLM judge (temp 0, stored rubric + reasoning) |
| Behaviour | refusal rate ✅; injection resistance, format compliance 📝 0007 | judge / rules |
| Operational | TTFT, total latency (p50/p95), answer tokens (approx.), error rate ✅; cost 📝 0007 | measured |

Boundaries (`metric · aggregate · comparator · value`) decide pass/fail for a run.

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-24 | Hatchet instead of Spark / Celery / RQ / django.tasks | Spark is a batch engine, not a task queue. Celery on Redis has no DLQ/requeue UI. Hatchet gives a run UI with replay/cancel, rate limits, per-user concurrency, cron and streaming, and stores state in Postgres. |
| 2026-10-24 | Agent runs are Hatchet tasks, streamed through Channels | Every agent run is observable, cancellable and replayable in the Hatchet UI. |
| 2026-10-24 | Postgres + pgvector for vectors | One database; SQL filtering by owner/folder alongside vector search. |
| 2026-10-24 | Redis only for the Channels layer | Hatchet uses Postgres for its queue, so Redis has one job. |
| 2026-10-24 | JWT as first websocket message | Browsers can't set headers on websockets; URLs leak into logs. |
| 2026-10-24 | Channels Redis `socket_timeout: 15` | redis-py 8's 5 s default equals channels-redis' 5 s BZPOPMIN, which randomly dropped sockets. |
| 2026-10-24 | One Django app per domain, layered, enforced by a test | Keeps features separable and the dependency graph acyclic; the test catches drift immediately. |
| 2026-10-24 | Websocket handler registry + task auto-discovery | Lets domain apps plug into platform apps (`realtime`, `jobs`) without the platform importing them. |
| 2026-10-24 | Benchmarks split into `scoring` / `evals` / `benchmarks` | One responsibility each (how to score / what to test / running tests). `scoring` stays pure and testable; suites don't depend on agents, so they're reusable; only `benchmarks` sees everything, and nothing depends on it. |
| 2026-10-24 | Eval relevance by document + evidence snippet, not chunk number | Chunk numbers change on every re-index or chunking change; documents and quoted evidence don't. |
| 2026-10-24 | Executable specs: Markdown with Gherkin run by Cucumber.js + Playwright | Specs stay readable documents *and* become the acceptance suite, so docs can't drift from behaviour. Cucumber reads `.feature.md` natively; TypeScript step defs run via Node type stripping. |
| 2026-10-24 | Fake OpenAI-compatible server for specs | Deterministic, free, offline; exercises the real HTTP path through the openai SDK. |
| 2026-10-24 | Fernet-encrypted, write-only API keys | A DB dump doesn't leak keys; the browser never receives them (only the last 4). |
| 2026-10-24 | Re-index needs explicit confirmation (409 `reindex_required`) | Embedding/chunking changes invalidate every vector; the user must opt in. |
| 2026-10-24 | Unsized `vector` column + partial HNSW index per common dimension | Each user brings their own embedding model; HNSW requires a fixed size, so one index per size (384/768/1024/1536) covers the common models and other sizes fall back to exact search. |
| 2026-10-24 | Approximate token counting | Avoids model-specific tokenizers and runtime vocabulary downloads; accurate enough for chunk sizing. |
| 2026-10-24 | Websocket `document.status` patches React Query caches | Live status without polling; the server stays the source of truth. |
| 2026-10-24 | Extra model connections (e.g. Ollama) per agent; embeddings stay on the default provider | You asked for local models. Answers can come from any model, but every stored vector must come from one embedder to be comparable. |
| 2026-10-24 | Agent loop falls back to retrieve-then-answer when a model rejects tools | Many local models lack tool calling; they should still answer from your documents. |
| 2026-10-24 | chat (top layer) owns `agent.ask`; agents owns the loop | Persistence needs the conversation; the loop must not depend on chat. Matches the app layering. |
| 2026-10-24 | Fake provider uses a toy 8-topic embedding | Deterministic semantic behaviour in specs — and, like real embedders, it ignores codes, so hybrid search's value is testable. |
| 2026-10-24 | An unreadable judge verdict fails the case | Found with real Gemma: reasoning models spend tokens thinking, so judges returned cut-off/empty JSON and runs passed with n/a scores. A broken evaluation must never look like a pass. |
| 2026-10-24 | `evals` may import `scoring` and `providers` | Suites validate metric ids against the scoring registry and pick a judge connection; neither app depends back, so no cycle. |
