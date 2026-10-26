// ─────────────────────────────────────────────────────────────────────────────
// SINGLE SOURCE OF TRUTH for the System Design page.
// CLAUDE.md rule: any change to architecture, RAG pipeline, event contract or specs
// MUST update this file in the same change. Bump LAST_UPDATED when you do.
// ─────────────────────────────────────────────────────────────────────────────

export const LAST_UPDATED = "2026-10-26 · spec 0013 Chat setup card";

/** live = works end-to-end today · demo = wired up with fake data · planned = spec drafted */
export type Status = "live" | "demo" | "planned";

export type Component = {
  name: string;
  tech: string;
  role: string;
  runs: string;
  status: Status;
};

export const COMPONENTS: Component[] = [
  {
    name: "Web app",
    tech: "React 19 · Vite+ · TanStack Router · React Query · shadcn · Tailwind v4",
    role: "UI. React Query caches REST data; one websocket per tab receives live events.",
    runs: "vp dev → localhost:5173 (proxies /api and /ws to Django)",
    status: "live",
  },
  {
    name: "API",
    tech: "Django 6 · DRF · SimpleJWT",
    role: "REST endpoints, auth (JWT access 15 min / refresh 7 days), starts Hatchet runs.",
    runs: "uv run manage.py runserver → Daphne (ASGI) on :8000",
    status: "live",
  },
  {
    name: "Realtime gateway",
    tech: "Django Channels (same Daphne process)",
    role: "Holds websockets. Authenticates with the first message, joins group user.<id>, relays events.",
    runs: "ws://localhost:8000/ws/events/",
    status: "live",
  },
  {
    name: "Channel layer",
    tech: "Redis 8",
    role: "Pub/sub pipe so any process (e.g. a worker) can reach a user's sockets. Nothing else uses Redis.",
    runs: "docker compose → :6379",
    status: "live",
  },
  {
    name: "Orchestrator",
    tech: "Hatchet (hatchet-lite)",
    role: "Durable task queue: retries, per-user concurrency, rate limits, cron, streaming, replay/cancel UI.",
    runs: "docker compose → dashboard :8888, gRPC :7077",
    status: "live",
  },
  {
    name: "Worker",
    tech: "Hatchet Python SDK inside Django (management command)",
    role: "Executes tasks: indexing, agent runs, cron jobs. Can use the Django ORM.",
    runs: "uv run manage.py hatchet_worker",
    status: "live",
  },
  {
    name: "Database + vector store",
    tech: "Postgres 18 · pgvector 0.8",
    role: "App data, document chunks and their embeddings (HNSW index). Hatchet uses its own DB here too.",
    runs: "docker compose → :5432 (databases: rag, hatchet)",
    status: "live",
  },
  {
    name: "LLM provider",
    tech: "Any OpenAI-compatible API",
    role: "Embeddings and chat with tool calling, through the default provider or extra connections such as a local Ollama, Claude (Anthropic) or Gemini (Google) — each spoken in its own API by an adapter, behind one neutral interface. Each embedding names its own endpoint + model (one model per index, so its vectors are comparable); each chat picks the model that answers. Keys are Fernet-encrypted at rest.",
    runs: "External or local — Settings → LLM provider / Connections; apps.providers.chat_target()",
    status: "live",
  },
  {
    name: "Benchmarks",
    tech: "Django apps scoring + evals + benchmarks · Hatchet fan-out",
    role: "Eval suites, metrics and pass/fail boundaries; runs a suite against an agent or a bare model (any connection) and stores per-case scores, where the time went, and each model's speed across runs.",
    runs: "benchmark-run parent task → one benchmark-case child per case (2 at a time per user)",
    status: "live",
  },
];

export type DjangoApp = {
  name: string;
  layer: "platform" | "domain";
  owns: string;
  dependsOn: string;
  status: Status;
  spec?: string;
};

// Mirrors ALLOWED_DEPENDENCIES in backend/apps/core/test_architecture.py (the test enforces it).
export const DJANGO_APPS: DjangoApp[] = [
  {
    name: "core",
    layer: "platform",
    owns: "Health check, pgvector extension, shared base code",
    dependsOn: "—",
    status: "live",
  },
  {
    name: "accounts",
    layer: "platform",
    owns: "Users, JWT login / refresh, /me",
    dependsOn: "core",
    status: "live",
  },
  {
    name: "realtime",
    layer: "platform",
    owns: "Websocket gateway, send_to_user(), message-handler registry",
    dependsOn: "core",
    status: "live",
  },
  {
    name: "jobs",
    layer: "platform",
    owns: "Hatchet client, worker, task discovery, Hatchet events, demo tasks",
    dependsOn: "core, realtime",
    status: "live",
  },
  {
    name: "providers",
    layer: "domain",
    owns: "Default provider + connections, each with a kind (OpenAI-compatible, Anthropic, Google); the adapter layer (the only code that imports a provider SDK); the model catalogue",
    dependsOn: "platform",
    status: "live",
    spec: "0004, 0008, 0010",
  },
  {
    name: "library",
    layer: "domain",
    owns: "Folders, documents, uploads, statuses; emits document.uploaded / document.moved / document.reindex_requested",
    dependsOn: "platform",
    status: "live",
    spec: "0003",
  },
  {
    name: "rag",
    layer: "domain",
    owns: "Embeddings (named indexes: what they cover, model, chunking), indexing per embedding (parse once, chunk + embed per index) and answering (query transforms, dense/keyword/hybrid/MMR search in one index, rerank, generation strategies)",
    dependsOn: "providers, library",
    status: "live",
    spec: "0003–0005, 0010",
  },
  {
    name: "agents",
    layer: "domain",
    owns: "Agent config (system message + RAG options), the agent loop, agent-run task (searches the embedding and answers with the model the chat picked)",
    dependsOn: "providers, library, rag",
    status: "live",
    spec: "0005, 0010",
  },
  {
    name: "chat",
    layer: "domain",
    owns: "Conversations (agent + embedding + model, and the run answering right now), messages (each records what produced it), delete, agent.ask / agent.cancel websocket handlers",
    dependsOn: "providers, agents, rag",
    status: "live",
    spec: "0005, 0009, 0010",
  },
  {
    name: "scoring",
    layer: "domain",
    owns: "How to score: retrieval metrics, LLM-judge rubrics, aggregation, boundary checks (no models)",
    dependsOn: "providers",
    status: "live",
    spec: "0006",
  },
  {
    name: "evals",
    layer: "domain",
    owns: "What to test: suites, cases (relevant documents + evidence), metrics, boundaries, judge",
    dependsOn: "library, providers, scoring",
    status: "live",
    spec: "0006",
  },
  {
    name: "benchmarks",
    layer: "domain",
    owns: "Running tests: runs, case results, timings, Hatchet fan-out, live progress, comparisons, model speed",
    dependsOn: "providers, library, rag, agents, evals, scoring",
    status: "live",
    spec: "0006",
  },
];

export const EVAL_FLOW = [
  "Pick a suite (evals) and a target — an agent, or a bare model from any connection as the no-RAG baseline — and press Run.",
  "benchmarks freezes snapshots of the suite and the target's config, creates a run and starts the benchmark-run Hatchet task.",
  "benchmark-run fans out one benchmark-case child per case (2 at a time per user).",
  "Each child asks the target (the agent loop, without a socket) and records the answer, retrieved chunks, latency and tokens.",
  "Timings come from the agent.* events the loop already emits: each moment belongs to the phase of the latest event — waiting (before any output), searching (tool_call → retrieval), reasoning (thinking), writing (tokens). The phases add up to the total exactly; tokens per second = answer tokens ÷ writing time; the judge is timed separately (spec 0011).",
  "scoring computes the metrics: retrieval ones exactly (relevance = right document + evidence snippet, not chunk numbers), judge ones with one rubric call each at temperature 0, storing the reasoning.",
  "Every finished case sends benchmark.case + benchmark.progress over the websocket — the page updates live.",
  "The parent aggregates (mean, p95), checks every applicable boundary (n/a metrics are skipped), and marks the run passed or failed.",
  "Retry failed cases replays them on Hatchet; compare two runs side by side with per-metric deltas, coloured by each metric's direction (lower latency is better).",
  "Model speed pools every finished case by the model that answered (agent and bare runs together) — typical first token, slow-case total and typical tokens per second.",
];

export type Step = {
  n: number;
  title: string;
  what: string; // the concept, in plain words
  here: string; // how THIS system does it
  options?: string[]; // choices the user will be able to make in the UI
  code?: string; // a small illustrative snippet
  status: Status;
  spec?: string;
};

export const INDEXING_STEPS: Step[] = [
  {
    n: 1,
    title: "Upload & store",
    what: "Get the raw files into the system and remember which user and folder they belong to.",
    here: 'Library page → DRF multipart upload (PDF, DOCX, MD, TXT, ≤25 MB). library saves the file and a Document(status=queued), and after the transaction commits pushes the Hatchet event document.uploaded. rag\'s route-document task subscribes to it — library never imports rag — works out which embeddings cover the document, and queues one index-document run per embedding. No embedding covering it = "Not indexed".',
    status: "live",
    spec: "0003",
  },
  {
    n: 2,
    title: "Parse (extract text)",
    what: "LLMs and embedding models only understand text, so PDFs, Word docs etc. are converted to plain text (keeping page numbers / headings where possible).",
    here: "rag/parsing.py: pypdf for PDF (pages joined by blank lines), python-docx for DOCX (Heading styles become Markdown #), UTF-8 for MD/TXT. Unreadable or empty files fail the document with a reason — no retries for user errors.",
    status: "live",
    spec: "0003",
  },
  {
    n: 3,
    title: "Chunk",
    what: "Split text into pieces small enough to embed and to fit several into a prompt, but big enough to carry meaning. Overlap stops ideas being cut in half.",
    here: "rag/chunking.py — pure functions per strategy, sizes from Settings → Indexing. Tokens are approximated (words + punctuation) so no tokenizer download is needed. Library → View chunks shows exactly what was produced.",
    options: [
      "Fixed size — every N tokens",
      "Recursive — split on paragraphs → sentences → words until it fits",
      "Markdown/heading-aware — keep sections together",
      "Semantic — split where embedding similarity between sentences drops",
      "Parent-document — search small chunks, hand the LLM the bigger parent",
    ],
    status: "live",
    spec: "0004",
  },
  {
    n: 4,
    title: "Embed",
    what: "Turn each chunk into a vector (a list of ~1 000+ numbers). Texts with similar meaning get vectors that point in similar directions.",
    here: 'rag/embedding.py: batches of 64 texts per request to the embedding\'s own endpoint + model (heading path prepended for context). Each embedding chunks with its own settings, so "small chunks + model A" and "large chunks + model B" can index the same documents side by side; the parsed text is cached per document. Per-user concurrency (3 documents at once) keeps one big upload from starving others; transient errors retry with backoff, bad keys fail immediately.',
    code: `client.embeddings.create(model="text-embedding-3-small", input=[chunk.text for chunk in batch])`,
    status: "live",
    spec: "0003",
  },
  {
    n: 5,
    title: "Store vectors",
    what: "Save chunk text + vector + metadata so we can search by meaning later.",
    here: "rag.Chunk: its embedding (EmbeddingIndex FK), text, token count, an unsized pgvector `vector` + its `dimensions` (every embedding picks its own model), and a generated tsvector with a GIN index for keyword search. HNSW needs a fixed size, so there's one partial expression index per common size (384/768/1024/1536). Re-indexing replaces a document's chunks in that one embedding, in one transaction; a version number makes a slow run with an old model throw its vectors away instead of overwriting newer ones.",
    code: `CREATE INDEX rag_chunk_hnsw_1536 ON rag_chunk\n  USING hnsw ((embedding::vector(1536)) vector_cosine_ops)\n  WHERE dimensions = 1536;`,
    status: "live",
    spec: "0003",
  },
];

export const QUERY_STEPS: Step[] = [
  {
    n: 6,
    title: "Transform the query (optional)",
    what: "User questions are often short or vague. Rewriting them first can find better chunks.",
    here: "rag/retrieval.py, per agent (Agents → RAG pipeline). Each transform is one small LLM call before searching; results from several queries are merged with RRF.",
    options: [
      "None — embed the question as-is",
      "Multi-query — LLM writes 3 variants, retrieve for each, merge with RRF",
      "HyDE — LLM writes a hypothetical answer; embed that instead (keywords still use the question)",
      "Step-back — also search a broader version of the question",
    ],
    status: "live",
    spec: "0005",
  },
  {
    n: 7,
    title: "Retrieve",
    what: "Find the chunks closest in meaning to the question.",
    here: "rag/retrieval.py with raw SQL so you can read it: pgvector cosine distance cast to vector(N) to hit the HNSW index; Postgres full-text with the question's words OR-ed together; Reciprocal Rank Fusion to merge. Scoped to one embedding (the one the chat picked) and the user's own chunks — the question is embedded with that embedding's model, so vectors from different models never meet.",
    options: [
      "Dense — vector similarity only (finds paraphrases, misses exact codes like E-4012)",
      "Keyword — Postgres full-text (finds exact terms, no synonyms)",
      "Hybrid — both, merged with Reciprocal Rank Fusion (default)",
      "MMR — dense candidates, re-picked for diversity",
      "top-k — how many chunks the agent sees per search",
    ],
    code: `SELECT id, 1 - (embedding::vector(1536) <=> %s::vector(1536)) AS score\nFROM rag_chunk\nWHERE owner_id = %s AND embedding_index_id = %s AND dimensions = 1536\nORDER BY embedding::vector(1536) <=> %s::vector(1536)\nLIMIT %s;  -- same cast as the index, or it's a full scan`,
    status: "live",
    spec: "0005",
  },
  {
    n: 8,
    title: "Rerank (optional)",
    what: "Vector search is fast but rough. A second, smarter pass re-orders the candidates.",
    here: "LLM rerank: fetch 3× top-k, ask the model for a JSON list of passage numbers by relevance, keep the best top-k (falls back to search order if the reply isn't valid).",
    options: [
      "LLM rerank — ask the LLM to rank candidates (live)",
      "Cross-encoder — scores (question, chunk) pairs with a small local model (later: needs a model download)",
    ],
    status: "live",
    spec: "0005",
  },
  {
    n: 9,
    title: "Augment the prompt",
    what: "Put the retrieved chunks into the prompt alongside the system message and the question, each labelled so the model can cite it.",
    here: "The agent's system message + RAG instructions, the last 20 messages of the conversation, and — as the search tool's result — passages tagged [document#chunk] (the parent text for parent-document chunks).",
    status: "live",
    spec: "0005",
  },
  {
    n: 10,
    title: "Generate",
    what: "The LLM writes the answer grounded in the supplied chunks.",
    here: "rag/generation.py decides what the search tool hands back; the answer streams from the agent's model — your default provider or a connection such as a local Ollama.",
    options: [
      "Cited — answer from the chunks with [document#chunk] citations (default)",
      "Stuff — the chunks, no citation rule",
      "Map-reduce — summarise each chunk first, answer from the notes",
      "Refine — draft from the first chunk, improve it chunk by chunk",
      "Corrective — grade the chunks; if none help, rewrite the query and search again",
    ],
    status: "live",
    spec: "0005",
  },
  {
    n: 11,
    title: "Agent loop",
    what: "Instead of always retrieving once, the LLM gets a search_documents tool and decides when (and how often) to call it.",
    here: "agents/runner.py inside the agent-run Hatchet task: up to 4 tool rounds, then it must answer. Models that can't call tools (many small local ones) fall back automatically to classic retrieve-then-answer.",
    status: "live",
    spec: "0005",
  },
  {
    n: 12,
    title: "Stream to the UI",
    what: "Show progress as it happens instead of waiting for the full answer.",
    here: "Task → ctx.put_stream() → Hatchet → the chat app's websocket handler, subscribed to the run → Chat page renders thinking (incl. a model's own reasoning), tool calls, chunks and tokens. The finished (or stopped) reply is saved to the conversation.",
    status: "live",
    spec: "0001",
  },
];

export const CHAT_FLOW = [
  'You pick three things — an agent (how to retrieve and answer), an embedding (what to search, or None) and a model (what answers) — and press Send. The Chat page sends {type: "agent.ask", agent_id, message, conversation_id, embedding_id, connection_id, model} on the already-authenticated websocket.',
  "chat's handler stores your message and the picks on the conversation (they apply from this message on), then asks agents to start an agent-run on Hatchet with the last 20 messages. Hatchet returns a run_id at once.",
  'It replies {type: "agent.started", run_id, conversation_id} and starts relaying that run\'s stream to your socket.',
  "On the worker, the agent loop streams a completion from the chosen model — your default provider or e.g. Ollama — with the search_documents tool attached (no tool when the embedding is None: the model answers alone).",
  "When the model calls the tool, rag retrieves chunks (transform → search → rerank) and the generation strategy shapes the result; you see agent.tool_call and agent.retrieval.",
  "The model's reasoning (if it shares any) arrives as agent.thinking; its answer as agent.token… then agent.done with the model's name.",
  "The Chat page folds each event into the conversation with a reducer — that's the live typing effect. Citations like [handbook.md#2] become chips. The saved reply records the agent, embedding and model that produced it, so switching mid-chat never relabels old answers.",
  'Stop sends {type: "agent.cancel"}: the run is cancelled on Hatchet, the worker stops streaming at the next token, and the partial answer is saved as stopped.',
  "Delete (trash icon → confirm) is REST: DELETE /api/chat/conversations/<id>/. If the chat is still answering, chat cancels its run on Hatchet (Conversation.active_run_id) and pushes agent.cancelled with cancel_background=<run_id> to user.<id>, so whichever socket relays that run stops it. Then the conversation is deleted and its messages cascade; the relay's save finds nothing to save into.",
];

export const JOB_FLOW = [
  "Library → Upload: React Query posts the files (multipart) to /api/library/documents/ with your JWT.",
  "library saves each file and a Document(status=queued), answers 201 straight away, and — once the transaction commits — pushes the Hatchet event document.uploaded.",
  "Hatchet starts rag's route-document task, which queues index-document once per embedding that covers the document (max 3 at once per user, retried with backoff on network errors). Creating or editing an embedding runs sync-embedding instead, which queues only the documents it gained.",
  "Each run sets that embedding's entry to indexing, parses (once per document), chunks and embeds with the embedding's own settings, stores the Chunks, then ready (or failed with a reason).",
  "Every change calls send_to_user(owner, …) — embedding.status for the embedding's progress, document.status for the document's worst state across its embeddings — a group_send to user.<id> through Redis.",
  "Every Daphne process holding one of your sockets forwards it; the Library page patches its React Query cache, so badges change with no polling and no reload.",
  "Try the same loop by hand with the demo job below.",
];

export const HATCHET_FEATURES = [
  {
    name: "Retries + backoff",
    where: "@hatchet.task(retries=2, backoff_factor=2.0)",
    status: "live" as Status,
  },
  {
    name: "Per-user concurrency",
    where: "ConcurrencyExpression('string(input.user_id)', max_runs=2)",
    status: "live" as Status,
  },
  {
    name: "Cron",
    where: "@hatchet.task(on_crons=['0 3 * * *']) — nightly-housekeeping",
    status: "live" as Status,
  },
  {
    name: "Streaming",
    where: "ctx.aio_put_stream() ↔ hatchet.runs.subscribe_to_stream()",
    status: "live" as Status,
  },
  {
    name: "Cancel / replay",
    where: "Hatchet UI or hatchet.runs.cancel() / .replay()",
    status: "live" as Status,
  },
  {
    name: "Non-retryable failures",
    where: "index-document raises NonRetryableException for user errors (bad key, unreadable file)",
    status: "live" as Status,
  },
  {
    name: "Event triggers",
    where:
      "document.uploaded / document.moved / document.reindex_requested → route-document (→ index-document per covering embedding)",
    status: "live" as Status,
  },
  {
    name: "Cancel older duplicate runs",
    where: "reindex: ConcurrencyExpression(max_runs=1, CANCEL_IN_PROGRESS)",
    status: "live" as Status,
  },
  {
    name: "Child runs (fan-out)",
    where:
      "benchmark-run → benchmark_case.run_many(...) — one child per case, shown under the parent in the Hatchet UI",
    status: "live" as Status,
  },
  {
    name: "Rate limits",
    where: "Per provider key for embeddings + chat calls",
    status: "planned" as Status,
  },
  {
    name: "Fan-out (child runs)",
    where: "Today reindex queues one index-document run per doc; true parent/child runs later",
    status: "planned" as Status,
  },
];

export const GOTCHAS = [
  "Websockets can't send an Authorization header from the browser, so the JWT is the first message — never put it in the URL (URLs end up in logs).",
  "Hatchet stream chunks published before anyone subscribes are not replayed; the demo agent waits 300 ms before streaming. Real agents should persist the final answer too.",
  "Enqueue Hatchet runs inside transaction.on_commit(): otherwise the worker can start before the Document row exists.",
  "Task inputs must be JSON-serialisable — pass IDs, not model instances.",
  "A lower Django app can't import a higher one, so it announces changes with a Hatchet event (library → document.uploaded / document.moved) and the higher app's task subscribes.",
  "pgvector's HNSW index needs a fixed vector size, but every user picks their own embedding model — so the column is unsized and we keep partial expression indexes per common size. Queries must cast the same way to use them.",
  "Hatchet runs sync tasks in worker threads: call close_old_connections() around ORM work so threads don't hold dead DB connections.",
  "Chunk sizes use approximate tokens (words + punctuation). Good enough for sizing; never for billing.",
  "Every vector in one embedding must come from one model, so retrieval searches one embedding at a time and embeds the question with that embedding's model — the answering model can be anything (e.g. local Gemma). Want to compare models or chunk sizes? Make two embeddings of the same documents and compare them in Benchmarks.",
  "Every provider is used through one small interface (providers/llm): stream_chat yields Thinking / Text / ToolCall / Done, plus complete, embed and list_models. The agent loop, retrieval, judges and indexing are written once against it — adding a provider means writing an adapter, not touching callers. Claude's signed thinking blocks and Gemini's thought signatures ride along as the adapter's opaque 'raw' turn and are sent back unchanged.",
  "Claude may decline a request (stop_reason: refusal), even after it has started answering. The adapter reports it as Done('refusal'); the loop turns that into the same agent.error any failure uses, and the chat drops the half-answer.",
  "OpenAI's /models lists ids only, so the model picker asks Ollama's /api/show, then a built-in table, then the name (\"guessed from the name\") — and lists anything it can't classify as Unknown, because a wrong guess must never hide a model.",
  'Not every model can call tools. When a provider says so (Ollama: "does not support tools"), the agent falls back to classic RAG: search once with the question, put the passages in the prompt, answer.',
  "Reasoning isn't part of the OpenAI schema; providers add it as an extra field (reasoning_content or reasoning). The agent reads both, which is how Gemma's thinking shows up live.",
  "Reasoning models (Gemma, DeepSeek-R1…) spend part of max_tokens thinking before they answer. A judge with a small budget returns cut-off or empty JSON — so judges get 2000 tokens, cut-off replies are salvaged, and an unreadable verdict fails the case instead of counting as n/a.",
  "Never let a missing score pass: n/a is only for metrics that genuinely don't apply (retrieval on a bare model); an evaluation that broke is a failure you can retry.",
  "Changing an embedding's model or chunking invalidates its stored vectors (different models' vectors aren't comparable), so it triggers a re-index of that embedding — hence the confirmation dialog. Adding or removing folders only indexes the difference.",
  "A reply is only saved when its stream ends, so a REST request (deleting the chat) can't see that a run is in flight unless you store it — hence Conversation.active_run_id. And the relay lives in whichever Daphne process holds the socket, so the delete reaches it through the user.<id> group (cancel_background), not directly.",
  "Tokens live in localStorage for simplicity. Production apps usually prefer httpOnly cookies to limit XSS damage.",
];

export const GLOSSARY = [
  [
    "Eval suite",
    "A set of test cases + the metrics that score them + optional boundaries. A run passes only if every case passes and every boundary holds.",
  ],
  [
    "LLM-as-judge",
    "Using an LLM with a fixed rubric to score answers (e.g. faithfulness) where exact maths can't.",
  ],
  ["Boundary", "A pass/fail rule on an aggregated metric, e.g. faithfulness mean ≥ 0.85."],
  ["nDCG", "Normalised Discounted Cumulative Gain — rewards relevant results ranked near the top."],
  ["MRR", "Mean Reciprocal Rank — average of 1/rank of the first relevant result."],
  [
    "RAG",
    "Retrieval-Augmented Generation: fetch relevant text first, then let the LLM answer using it.",
  ],
  ["Embedding", "A vector representing the meaning of a piece of text."],
  [
    "Embedding (the page)",
    "In this app also a named, searchable index: some documents + one embedding model + one chunking setting. Chat searches one at a time.",
  ],
  ["Cosine distance", "1 − cosine similarity; smaller means more similar. pgvector operator <=>."],
  [
    "HNSW",
    "Hierarchical Navigable Small World — a graph index for fast approximate nearest-neighbour search.",
  ],
  ["Chunk", "A slice of a document small enough to embed and to fit into a prompt."],
  ["top-k", "How many of the best-matching chunks to keep."],
  [
    "RRF",
    "Reciprocal Rank Fusion — merges ranked lists (e.g. vector + keyword) by summing 1/(k + rank).",
  ],
  ["Channel layer", "Channels' pub/sub abstraction; here backed by Redis."],
  ["Run", "One execution of a Hatchet task, with its own id, status, logs and stream."],
  [
    "Layered apps",
    "Django apps ordered so lower layers never import higher ones; cross-app calls go through services.py.",
  ],
];

// The spec list itself is read from the specs/ folder — see ./specs.ts.

export type TestLayer = {
  name: string;
  tool: string;
  proves: string;
  runs: string;
  where: string;
};

export const TEST_LAYERS: TestLayer[] = [
  {
    name: "Executable specs (acceptance)",
    tool: "Cucumber.js · Markdown with Gherkin · Playwright · ws · fetch",
    proves: "The user-visible behaviour in each spec works end to end on the real running stack.",
    runs: "make acceptance",
    where: "specs/*.feature.md + acceptance/",
  },
  {
    name: "Backend unit & integration",
    tool: "pytest · pytest-django · Channels communicator",
    proves:
      "Services, serializers, permissions, websocket protocol — fast, with fakes for Hatchet and the LLM.",
    runs: "make test",
    where: "backend/apps/*/test_*.py",
  },
  {
    name: "Architecture guard",
    tool: "pytest + ast",
    proves: "Django apps only import the apps they're allowed to (layering never drifts).",
    runs: "make test",
    where: "backend/apps/core/test_architecture.py",
  },
  {
    name: "Static checks",
    tool: "ruff · Oxlint (type-aware) · TypeScript",
    proves: "Formatting, lint rules and types across backend, frontend and step definitions.",
    runs: "make check",
    where: "pyproject.toml · frontend/vite.config.ts · acceptance/tsconfig.json",
  },
];

export const SPEC_TO_TEST = [
  {
    title: "Write the spec in Markdown",
    detail:
      "specs/NNNN-name.feature.md. Prose sections (Why, Scope, Design notes) are for humans. Under `# Feature:`, each `## Scenario:` heading with `* Given / When / Then` bullets is an executable acceptance test. Markdown tables become data tables.",
  },
  {
    title: "Cucumber parses it",
    detail:
      "Cucumber.js reads Markdown with Gherkin natively: it ignores the prose and turns each scenario into a list of step texts. acceptance/cucumber.mjs runs every spec whose Status is Approved, In progress or Done.",
  },
  {
    title: "Step definitions match the text",
    detail:
      "acceptance/steps/*.steps.ts map each sentence (with {string}/{int} parameters) to code. Steps stay thin: they read like the spec and delegate everything.",
  },
  {
    title: "The execution layer does the work",
    detail:
      "Page objects (acceptance/pages/) drive a real Chromium with Playwright using accessible roles and labels; ApiClient calls REST with a JWT; SocketClient talks to the websocket; a fake OpenAI-compatible server stands in for the LLM.",
  },
  {
    title: "Run it against the live app",
    detail:
      "make acceptance — each scenario gets a fresh user, a fresh browser context and its own sockets. Strict mode: an undefined step fails the run. Failures attach a screenshot to reports/acceptance.html.",
  },
  {
    title: "CI keeps docs honest (when git is set up)",
    detail:
      "The same command runs on every pull request, so a spec can never say something the app doesn't do.",
  },
];

export const TEST_RULES = [
  "Every acceptance test in a spec is a `## Scenario:` named `AT-NNNN-nn — …`. No scenario, no feature.",
  'Write steps from the user\'s point of view ("I press Save"), never about implementation ("POST /api/x") — except where the API is the user, e.g. security checks.',
  "A spec is Done only when `make acceptance` passes for it, plus `make test` and `make check`.",
  "Step definitions contain no selectors or HTTP details — those live in page objects and the API/socket clients, so a UI change touches one file.",
  "Locate elements by role and label (getByRole / getByLabel). If a test can't find something accessibly, fix the UI.",
  "Never call real LLMs from specs — use the fake provider so runs are free and deterministic. Real-model quality is what Benchmarks (spec 0006) measure.",
  "Fast logic tests (pytest) cover edge cases; scenarios cover the behaviour promised in the spec. Don't duplicate every edge case as a scenario.",
];
