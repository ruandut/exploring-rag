# CLAUDE.md — RAG Lab

A learning project: users log in, upload documents into folders, configure an OpenAI-compatible
LLM, choose RAG strategies, configure agents, and chat with them while watching the agent's
thinking / tool calls / retrieval / tokens stream live.

The owner is learning this stack. Explain *why* in code comments where a choice isn't obvious,
and keep the **System Design page** and **ARCHITECTURE.md** accurate — they are the learning material.

## Architecture (do not drift without discussing first)

| Concern | Use | Never use instead |
|---|---|---|
| Frontend build/tooling | **Vite+ (`vp`)** | raw `pnpm add` / `npm i`, separate eslint/prettier |
| Routing | TanStack Router (file routes in `frontend/src/routes`) | react-router |
| Server state | React Query | global stores for API data |
| UI | shadcn (`frontend/src/components/ui`, vendored) + Tailwind v4 | other component libs |
| API | Django 6 + DRF + SimpleJWT | |
| Python tooling | **uv** (`uv add`, `uv run`) | pip, poetry, venv by hand |
| Realtime | Django Channels, single socket `/ws/events/` | SSE, polling, extra socket endpoints |
| Background work, agents, cron | **Hatchet** (tasks in `backend/apps/jobs/tasks/`) | Celery, RQ, django.tasks, threads |
| Database + vectors | Postgres + pgvector | separate vector DBs |
| Redis | **Only** the Channels layer | queues, caching, sessions |
| LLM | OpenAI-compatible client: default provider (embeddings + chat) + extra connections such as Ollama (chat) | provider-specific SDKs |

Full map of what is used for what: [ARCHITECTURE.md](ARCHITECTURE.md).

## Repo layout

```
backend/                 Django project (uv)
  config/                settings, urls, asgi (HTTP → Django, WS → Channels)
  apps/                  one Django app per concern — see "Django apps" below
frontend/                React app (Vite+)
  src/routes/            TanStack file routes; _app.tsx = authenticated layout with nav drawer
  src/features/<area>/   feature code (chat, system-design, …)
  src/lib/               api.ts (fetch + JWT refresh), auth.ts, socket.ts (event contract types)
  src/features/system-design/content.ts   ← System Design page content (keep in sync!)
specs/                   one executable spec per feature (*.feature.md, Markdown with Gherkin)
acceptance/              Cucumber.js step definitions, page objects, API/socket clients, fake LLM
infra/                   docker init scripts
docker-compose.yml       Postgres+pgvector, Redis, hatchet-lite (infra only)
```

## Commands

```bash
make up            # postgres, redis, hatchet-lite
make api           # Django + Channels on :8000
make worker        # Hatchet worker
make web           # Vite+ dev server on :5173
make test          # backend pytest
make check         # ruff + vp check
```

Frontend: always `vp` (`vp add <pkg>`, `vp check --fix`, `vp build`). The local binary is
`frontend/node_modules/.bin/vp` if `vp` isn't installed globally. shadcn components:
`vpx shadcn@latest add <name>`.
Backend: always `uv` (`uv add <pkg>`, `uv run python manage.py …`, `uv run pytest`).

## Django apps (layered — enforced by `apps/core/test_architecture.py`)

| App | Layer | Owns | May import |
|---|---|---|---|
| `core` | platform | health, pgvector extension, shared base code | — |
| `accounts` | platform | users, JWT endpoints | core |
| `realtime` | platform | websocket gateway, `send_to_user`, ws handler registry | core |
| `jobs` | platform | Hatchet client, worker, task discovery, demo tasks | core, realtime |
| `providers` | domain | LLM provider config + OpenAI-compatible client factory (0004) | platform |
| `library` | domain | folders, documents, uploads (0003) | platform |
| `rag` | domain | parse/chunk/embed, `Chunk` + vectors, retrieval, rerank, generation (0003–0005) | providers, library |
| `agents` | domain | agent config, agent loop (`runner.py`), `agent-run` task (0005) | providers, library, rag |
| `chat` | domain | conversations, messages, `agent.ask`/`agent.cancel` ws handlers (0005) | providers, agents |
| `scoring` | domain | metric maths, LLM-judge rubrics, aggregation, boundary checks — no models (0006) | providers |
| `evals` | domain | suites, cases, boundaries, judge settings, JSONL import/export (0006) | library, providers, scoring |
| `benchmarks` | domain | runs, case results, `benchmark-run`/`-case` tasks, progress, comparisons (0006) | providers, library, rag, agents, evals, scoring |

Rules:
- **Never import upward.** If a lower app needs to trigger a higher one, emit a Hatchet event
  (e.g. library pushes `document.uploaded`; a rag task has `on_events=["document.uploaded"]`)
  or a Django signal. Adding a new app means adding it to `INSTALLED_APPS` *and*
  `ALLOWED_DEPENDENCIES`.
- Platform apps never import domain apps. Domain apps plug into the platform:
  websocket messages via `@ws_handler("type")` (registered in `AppConfig.ready()`),
  Hatchet tasks via `TASKS = [...]` in `<app>/tasks.py` (auto-discovered by the worker).
- Inside each app: `models.py`; `services.py` (writes + business logic, the only place that
  mutates models); `selectors.py` (read queries); `serializers.py`; thin `views.py`;
  `urls.py` (mounted at `/api/<app>/`); `tasks.py`; `admin.py`; tests next to the code
  (`test_*.py`).
- Other apps call `services` / `selectors`, never another app's models or views directly
  (FK relations to a lower app's models are fine).
- Every model with user data has `owner` and every queryset in selectors filters by it.

## Conventions

- **Hatchet tasks**: live in the owning app's `tasks.py` with `TASKS = [...]`; the worker
  auto-discovers them (`apps/jobs/registry.py`).
  Inputs are Pydantic models with IDs only (JSON-serialisable). Enqueue from views inside
  `transaction.on_commit(...)` once a task depends on rows written in the same request.
  Declare retries / concurrency / rate limits on the task, not in callers.
- **Hatchet event keys** (lower app → higher app): `document.uploaded`,
  `document.reindex_requested` (library → rag `index-document`), `provider.embedding_changed`
  (providers → rag `reindex-user-documents`). Listed in `apps/jobs/events.py`.
- **Embeddings always use the default provider** (every vector must come from one model);
  agents may answer with any connection/model. Agent runs must keep working for models without
  tool calling (pipeline fallback).
- **Benchmarks never let a missing score pass**: n/a only for metrics that don't apply (retrieval
  on a bare model); an unreadable judge verdict fails the case (retryable).
- **Sync Hatchet tasks** that use the ORM call `close_old_connections()` at start and end.
- **Pushing to the browser**: jobs use `apps.realtime.events.asend_to_user(user_id, payload)`.
  Agent runs publish JSON with `ctx.aio_put_stream()`; the consumer relays the run's stream.
- **Websocket messages from the client** are handled by `@ws_handler("<type>")` functions in
  the owning app; the consumer only does auth, ping and dispatch.
- **Websocket event contract**: every payload has a `type`. Defined in
  `frontend/src/lib/socket.ts` (`ServerEvent`, `ClientMessage`) — that file is the contract.
  Add a type there *and* in the backend emitter in the same change. Current types:
  `auth.ok|auth.error|pong|error`, `job.progress|job.completed`, `document.status`,
  `agent.started{conversation_id}|thinking|tool_call|retrieval|token|done{model,mode}|cancelled|error`.
  `benchmark.progress|case|completed` (ids are BenchmarkRun ids).
  Citations in answers are `[document#chunk]`.
  Planned (0006): `eval.progress|eval.case_result|eval.completed`.
- **Auth**: REST uses `Authorization: Bearer`. Websocket auth is the first message
  `{type:"auth", token}` — never put tokens in URLs.
- **React Query** owns server state; websocket events update it via `invalidateQueries` /
  `setQueryData`, or feed local UI state for ephemeral streams (chat).
- Tests: see "Testing" below. pytest tests that back a specific acceptance test are named
  `test_at_<spec>_<nn>_<what>`.
- Ports: Postgres 5432, Redis 6379, Hatchet 8888 (UI) / 7077 (gRPC), API 8000, web 5173.

## Testing (Specification by Example — mandatory)

Specs are executable. `specs/NNNN-name.feature.md` is Markdown with Gherkin: prose for humans,
then `# Feature:` with `## Scenario: AT-NNNN-nn — …` and `* Given / When / Then` bullets that
Cucumber.js runs against the live app (`make acceptance`).

Layers:
1. **Executable specs** — `acceptance/`: `steps/*.steps.ts` (thin, read like the spec) →
   `pages/*` (Playwright page objects, accessible locators only), `support/app.ts` (ApiClient,
   test users), `support/socket.ts` (SocketClient), `support/fake-llm.ts` (OpenAI-compatible fake).
2. **pytest** — services, serializers, permissions, consumers; fakes for Hatchet and the LLM.
3. **Architecture guard** — `apps/core/test_architecture.py`.
4. **Static** — ruff, `vp check`, `tsc` for acceptance.

Rules:
- No feature without scenarios. Every acceptance test is a scenario; a spec is Done only when
  its scenarios pass, plus `make test` and `make check`.
- Steps are phrased from the user's point of view and reused across specs (check
  `steps/common.steps.ts` first). No selectors or HTTP in step files.
- Locate UI by role/label. If something can't be found accessibly, fix the UI (add a role or
  aria-label), don't add test ids.
- Never call a real LLM from specs; use the fake provider. Real-model quality = Benchmarks.
- Each scenario gets a fresh user, browser context and sockets — no shared state.
- Drafts aren't run by default (cucumber.mjs filters by Status); Approved specs are, and stay
  red until built.
- When a scenario turns out ambiguous while implementing, fix the wording in the spec (and tell
  the user) rather than bending the step definition.

## Spec-driven workflow

Specs live in `specs/` (see `specs/README.md`). The user writes or edits a spec; we implement it.

**Definition of done for a spec** — all of these, in the same change:
1. Every scenario in the spec passes (`make acceptance`), and `make test` + `make check` pass.
   Step definitions and page objects added for new wording.
2. Spec status → `Done`, "Implementation notes" filled in.
3. **System Design page** updated: `frontend/src/features/system-design/content.ts`
   (component / app / RAG step statuses, flows, `LAST_UPDATED`) and the diagram in
   `architecture-diagram.tsx` if boxes/arrows changed. The spec list updates itself.
4. **ARCHITECTURE.md** updated if any technology, component, data flow or port changed.
5. `specs/CHANGELOG.md` gets an entry; `specs/README.md` index updated.
6. **Commit to memory**: update the Claude memory file for this project with what changed and
   any decision made (and why), so future sessions keep the same architecture.
7. Offer a git commit: `spec <id>: <title>`.

If a spec conflicts with the architecture table above, stop and raise it before coding.
