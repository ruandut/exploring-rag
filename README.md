# RAG Lab

Upload documents, plug in any OpenAI-compatible LLM, pick RAG strategies, configure agents,
and watch them think, search and answer in real time. Built to learn the stack:

**React · Vite+ · TanStack Router · React Query · shadcn · Tailwind** —
**Django 6 · DRF · JWT · Channels** — **Hatchet** — **Postgres + pgvector** — **Redis**

- What is used for what → [ARCHITECTURE.md](ARCHITECTURE.md)
- How we work (rules for Claude) → [CLAUDE.md](CLAUDE.md)
- Features as executable specs → [specs/](specs/README.md)
- In the app → **System design** page (architecture + RAG step by step)

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| Docker | Postgres, Redis, Hatchet | Docker Desktop |
| [uv](https://docs.astral.sh/uv/) | Python + backend deps | `brew install uv` |
| Node 22+ and pnpm | Used under the hood by Vite+ | `brew install node pnpm` |
| [Vite+](https://viteplus.dev) `vp` *(optional global)* | Frontend toolchain | `curl -fsSL https://vite.plus \| bash` |

Without the global `vp`, use `pnpm exec vp …` (or `./node_modules/.bin/vp …`) inside `frontend/`.

## First run

```bash
make setup        # docker up, uv sync, vp install, .env, migrations, Hatchet token
make superuser    # create your login
```

Then, in three terminals:

```bash
make api          # http://localhost:8000  (Django + websockets)
make worker       # Hatchet worker
make web          # http://localhost:5173  ← open this
```

Run the executable specs (in a fourth terminal, with the three above running):

```bash
make acceptance              # all Approved / In progress / Done specs
HEADED=1 make acceptance     # watch the browser do it
```

Hatchet dashboard: http://localhost:8888, login `admin@example.com` / `Admin123!!`
(hatchet-lite's default local account).

## Everyday commands

### Infrastructure (Docker)

```bash
docker compose up -d                 # start postgres, redis, hatchet
docker compose ps                    # what's running
docker compose logs -f hatchet       # follow a service's logs
docker compose down                  # stop (keeps data)
docker compose down -v               # stop AND delete all data
```

### Backend — uv

`uv` manages the Python version, the virtualenv (`backend/.venv`) and dependencies
(`pyproject.toml` + `uv.lock`). You never activate the venv: `uv run` does it for you.

```bash
cd backend

uv sync                                   # install exactly what uv.lock says
uv add httpx                              # add a dependency (updates pyproject + lock)
uv add --dev pytest-cov                   # add a dev-only dependency
uv remove httpx                           # remove one
uv lock --upgrade-package django          # upgrade one package
uv tree                                   # dependency tree

uv run python manage.py runserver 8000    # API + websockets (Daphne)
uv run python manage.py hatchet_worker    # Hatchet worker
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py shell

uv run pytest -q                          # tests
uv run pytest -k at_0001                  # only spec 0001's acceptance tests
uv run ruff check . --fix                 # lint
uv run ruff format .                      # format
uv python list                            # Python versions uv knows about
```

### Frontend — Vite+

`vp` wraps the package manager, dev server, build, lint (Oxlint), format (Oxfmt),
type-check and tests behind one CLI, configured in `frontend/vite.config.ts`.

```bash
cd frontend

vp install                     # install deps
vp add zod                     # add a dependency
vp add -D @types/foo           # add a dev dependency
vp remove zod
vp outdated                    # what can be upgraded

vp dev                         # dev server on :5173 (proxies /api and /ws to :8000)
vp check                       # format + lint + type-check
vp check --fix                 # …and fix what it can
vp test                        # run tests (Vitest)
vp build                       # production build → dist/
vp preview                     # serve the build

vpx shadcn@latest add dialog   # add a shadcn component into src/components/ui
vp toolchain                   # versions of Vite, Rolldown, Oxc… in this Vite+
```

### Executable specs — Cucumber + Playwright

```bash
cd acceptance

vp install                                            # deps (first time)
vp exec playwright install chromium                   # browser (first time)
vp run test                                           # run runnable specs
vp run test -- ../specs/0004-settings.feature.md      # one spec (even a Draft)
vp run test -- --name "AT-0004-03"                    # one scenario by name
vp run test -- --dry-run ../specs/*.feature.md        # list undefined steps + snippets
vp run typecheck                                      # type-check step definitions
open reports/acceptance.html                          # last run's report (screenshots on failure)
```

### Hatchet

```bash
make hatchet-token             # (re)generate HATCHET_CLIENT_TOKEN in backend/.env
```

After changing anything in `backend/apps/jobs/tasks/`, restart the worker. Tasks, runs, logs,
streams, crons, cancel and replay are all in the dashboard.

## Local models with Ollama

Agents can answer with models on your own machine.

```bash
ollama serve                      # if it isn't already running
ollama pull gemma4:e4b            # a chat model (supports tools + thinking)
ollama pull nomic-embed-text      # an embedding model, if you want fully local search too
```

1. **Settings → Connections → Ollama (local) → Add connection.** "List models" shows what's pulled.
2. **Agents → New agent**, pick the *Ollama (local)* connection and a model (e.g. `gemma4:e4b`).
3. Chat with it. Its reasoning streams into the Thinking panel.

Search uses the **default provider's** embedding model (Settings → LLM provider) so that every
document is comparable. For a fully local setup, point the default provider at
`http://localhost:11434/v1` with chat model `gemma4:e4b` and embedding model `nomic-embed-text`
(768 dimensions), then re-index.
Models that can't call tools still work — the agent falls back to search-then-answer.

## Benchmarks

**Benchmarks → New suite**: add cases (question, reference answer, the document that holds
the answer and an optional evidence quote), tick metrics, add boundaries such as
`faithfulness mean ≥ 0.85`, and choose a judge — a local Ollama model judges for free. Then run
the suite against an agent, or against a bare model to see what RAG adds (tick *Compare*).
Cases can be imported/exported as JSONL, one JSON object per line:

```json
{"kind": "qa", "question": "What is the refund window?", "reference_answer": "30 days", "relevant_documents": ["handbook.md"], "evidence": "refund window is 30"}
```

## Ports

| Port | What |
|---|---|
| 5173 | Web app (Vite+) |
| 8000 | Django API + websockets |
| 8888 | Hatchet dashboard |
| 7077 | Hatchet gRPC (workers connect here) |
| 5432 | Postgres (`rag` / `rag`, databases `rag` and `hatchet`) |
| 6379 | Redis |
| 11434 | Ollama (optional, your local models) |

## Building a feature

1. Copy `specs/_TEMPLATE.md` to `specs/000N-name.md`, describe it, and write acceptance tests.
2. Set it to **Approved** and ask Claude: *"implement spec 000N"*.
3. Claude builds it, adds `test_at_000N_*` tests, and updates the System Design page,
   ARCHITECTURE.md, the changelog and its memory (see CLAUDE.md → Definition of done).

## Troubleshooting

- **Websocket shows "Disconnected"** — is `make api` running? Check the user menu at the bottom left.
- **Settings won't load / 500 on save** — `FIELD_ENCRYPTION_KEY` missing in `backend/.env`; `make setup` generates it.
- **Acceptance "Login failed: 502"** — the API isn't running (`make api`).
- **"Couldn't start the job"** — the worker isn't running, or `HATCHET_CLIENT_TOKEN` is empty → `make hatchet-token`.
- **Port already in use** — another project's Postgres/Redis is on 5432/6379; stop it or change the host ports in `docker-compose.yml` and `backend/.env`.
