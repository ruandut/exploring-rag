# 0006 — Benchmarks: suites, metrics, boundaries, runs

- **Status:** Done
- **Depends on:** 0003 (indexed documents), 0004 (providers), 0005 (agents, connections)
- **Django apps:** `scoring` (metrics + judge), `evals` (suites), `benchmarks` (runs + results)
- **Touches:** frontend, backend, jobs
- **Split:** test-set generation, `injection`/`format` cases, repeats, CSV and cost are in
  **0007**.

## Why
"Does it work?" needs a number, not a feeling. Write test cases, pick industry-standard metrics,
set pass/fail **boundaries**, run them against an agent or a bare model, and compare runs, to see
whether HyDE, hybrid search, a reranker or a different (e.g. local) model actually made answers
better, or just slower.

## Scope
- In: suites with `qa` and `refusal` cases; retrieval, judge and operational metrics; boundaries;
  runs against an agent or a bare model (any connection); a judge model of your choice; live
  progress; per-case drill-down that shows how each score was reached; side-by-side comparison;
  retrying failed cases; JSONL import/export.
- Out (0007): synthetic test-set generation, `injection` and `format` cases, repeats (mean ±
  stdev), CSV import, cost estimates and a price table.

## Decisions (from review, 2026-10-24)
1. **Suites are reusable** across any target — they describe questions, not an agent.
2. **Your own documents only.** Public datasets are out of scope (decided 2026-10-24).
3. **No cost estimates yet** — runs record tokens; a price table (local models = free) is 0007.
4. **Relevance by document + optional evidence snippet**, never by chunk number: chunk numbers
   change on every re-index. A retrieved chunk is relevant if it belongs to a relevant document
   and, when an evidence snippet is given, contains it.
5. **Retrieval metrics are "n/a" for a bare model** (it retrieves nothing). Boundaries on n/a
   metrics are skipped, not failed.
6. **Agents may search several times**; retrieval metrics use the de-duplicated chunks in the
   order they were first retrieved.
7. **One judge call per metric per case** with a fixed rubric returning JSON
   `{score 0–1, reasoning}` at temperature 0 — cheap enough for local judges. (Not RAGAS-style
   claim splitting; noted on the System Design page.)
8. **Retry in the app**: a "Retry failed cases" button (Hatchet replays them underneath).
9. Pure metric maths is tested in pytest; scenarios check what you see.

## Concepts

**Suite** — cases + selected metrics + boundaries + judge (connection + model).

**Case kinds (this spec)**
| Kind | Input | Gold data | Passes when |
|---|---|---|---|
| `qa` | question | reference answer; relevant documents (+ optional evidence snippet) | its per-case metric thresholds hold |
| `refusal` | question the documents can't answer | — | the target says it doesn't know |

**Target** — an **agent** (full RAG pipeline, snapshot of its config frozen at run time) or a
**bare model** (connection + model, no retrieval: the baseline that shows what RAG adds).

## Metrics
| Group | Metric | How |
|---|---|---|
| Retrieval | hit rate@k, recall@k, precision@k, MRR, nDCG@k | exact maths vs. relevant documents/evidence (`scoring.retrieval`) |
| Generation | faithfulness, answer relevancy, answer correctness, context precision, context recall, citation accuracy | LLM judge, one rubric each (`scoring.judge`) |
| Behaviour | refusal rate | LLM judge on `refusal` cases |
| Operational | time to first token, total latency (p50/p95), tokens, error rate | measured |

## Boundaries
`metric · aggregate · comparator · value`, e.g. `faithfulness · mean · ≥ · 0.85`,
`recall@5 · mean · ≥ · 0.8`, `latency_total · p95 · ≤ · 8s`. A run **passes** only if every
applicable boundary holds; results show each one ✓/✗ with its margin.

## User experience
1. **Benchmarks** — suites with their latest run (pass/fail, headline metrics).
2. **Suite editor** — cases table (add/edit/delete, JSONL import/export), metric picker by group,
   boundaries, judge (connection + model).
3. **Run** — pick a target (agent, or bare model from any connection), optionally a second one
   to compare → Run. Progress streams live: cases done, running means, boundaries going ✓/✗.
4. **Results** — boundaries ✓/✗ with margins, metric table, per-case drill-down (question,
   answer, retrieved chunks, each score with the judge's reasoning or the maths, latency,
   tokens), "Retry failed cases", and side-by-side comparison with per-metric deltas.

## Design notes
**Django apps** (layering enforced by `apps/core/test_architecture.py`):
- `scoring` — no models. `scoring/retrieval.py` (hit/recall/precision/MRR/nDCG + an
  explanation string), `scoring/judge.py` (rubrics, JSON parsing), `scoring/aggregate.py`
  (mean, p50/p95), `scoring/boundaries.py` (check + margin), a metric registry with one
  interface `score(case, output, retrieved) -> MetricResult(value | None, explanation)`.
  May import: platform, `providers`.
- `evals` — `EvalSuite(owner, name, description, metrics[], judge_connection?, judge_model,
  version)`, `EvalCase(suite, kind, question, reference_answer, relevant_documents[], evidence)`,
  `Boundary(suite, metric, aggregate, comparator, value)`; services for CRUD and JSONL
  import/export; bumps `version` on every change. May import: platform, `library`, `providers`
  (the judge's connection), `scoring` (the metric vocabulary it validates against).
- `benchmarks` — `BenchmarkRun(owner, suite, suite_version, suite_snapshot, target_kind,
  target_snapshot, status, summary, passed, hatchet_run_id, compare_with?)`,
  `CaseResult(run, case, answer, retrieved, scores, explanations, latency_ms, ttft_ms, tokens,
  passed, error)`. Hatchet: `benchmark-run` (parent) fans out one `benchmark-case` child per
  case (2 at a time per user), then aggregates and checks boundaries. Websocket events:
  `benchmark.progress {run_id, done, total, means}`, `benchmark.case {run_id, case_id, passed}`,
  `benchmark.completed {run_id, passed}`. May import: platform, `providers`, `library`, `rag`,
  `agents`, `evals`, `scoring`.
- Running an agent for a case reuses `agents.runner.run()` without streaming to a socket;
  a bare model is one completion through `providers.services.chat_target()`.
- Frontend: `features/benchmarks/*`; the metric catalog already on the page becomes the picker.

# Feature: Benchmarks — suites, metrics, boundaries and runs

## Background:
* Given I am signed in
* And my provider is the fake LLM provider
* And "handbook.md" is indexed
* And the agent "Docs helper" can search all my folders

## Scenario: AT-0006-01 — Create a suite with cases and metrics
* When I create the suite "Basics" with the cases:
  | kind    | question                     | reference answer | relevant document | evidence             |
  | qa      | What is the refund window?   | 30 days          | handbook.md       | refund window is 30  |
  | qa      | How many days of leave?      | 25 days          | handbook.md       | 25 days of paid      |
  | refusal | Who won the 2030 World Cup?  |                  |                   |                      |
* And I select the metrics "faithfulness", "answer relevancy" and "recall@5"
* Then "Basics" shows 3 cases and 3 metrics

## Scenario: AT-0006-02 — A run scores every case
* Given the suite "Basics" exists
* When I run "Basics" against the agent "Docs helper"
* Then each case shows its answer, retrieved chunks, scores and latency
* And the run summary shows the mean of each metric

## Scenario: AT-0006-03 — Retrieval scores show their working
* Given the suite "Basics" exists
* When I run "Basics" against the agent "Docs helper"
* And I open the case "What is the refund window?"
* Then I see how recall@5 was calculated, e.g. "1 of 1 relevant documents retrieved"

## Scenario: AT-0006-04 — A boundary fails the run and shows its margin
* Given the suite "Basics" exists with the boundary "faithfulness mean ≥ 0.9"
* And "Basics" is judged by the model "fake-judge-0.8" from my default provider
* When I run "Basics" against the agent "Docs helper"
* Then the run is marked "Failed"
* And the boundary "faithfulness mean ≥ 0.9" shows ✗ with margin "-0.10"

## Scenario: AT-0006-05 — Refusal cases pass only when the target doesn't invent
* Given the suite "Basics" exists
* When I run "Basics" against the agent "Docs helper"
* Then the case "Who won the 2030 World Cup?" passes
* When I run "Basics" against the bare model "fake-inventor" from my default provider
* Then the case "Who won the 2030 World Cup?" fails

## Scenario: AT-0006-06 — Bare model vs agent, side by side
* Given the suite "Basics" exists
* When I compare "Basics" on the bare model "fake-chat" with the agent "Docs helper"
* Then I see both runs side by side with per-metric deltas
* And recall@5 shows "n/a" for the bare model

## Scenario: AT-0006-07 — Live progress
* Given the suite "Basics" exists
* When I run "Basics" against the agent "Docs helper"
* Then the progress counter moves from "0 / 3" to "3 / 3" without reloading the page
* And the final result appears without reloading the page

## Scenario: AT-0006-08 — Runs keep a snapshot of the target
* Given a finished run of "Basics" against "Docs helper"
* When I change the system message of "Docs helper" to "Something else"
* Then that run still shows the original system message

## Scenario: AT-0006-09 — Import and export cases as JSONL
* Given the suite "Basics" exists
* When I import "cases.jsonl" into "Basics"
* Then "Basics" shows 8 cases
* And exporting "Basics" returns 8 cases including those from "cases.jsonl"

## Scenario: AT-0006-10 — Suites and runs are private
* Given another user has a suite "Theirs"
* Then I don't see "Theirs" and can't run it

## Scenario: AT-0006-11 — Retry failed cases
* Given the suite "Basics" exists
* And my provider is unreachable
* When I run "Basics" against the agent "Docs helper"
* Then the run shows 3 failed cases
* When my provider is the fake LLM provider again
* And I press "Retry failed cases"
* Then the run shows 0 failed cases and the summary is updated

## Scenario: AT-0006-12 — The judge can be a different (e.g. local) model
* Given the suite "Basics" exists
* And I have a model connection "Local" to the fake LLM provider
* And "Basics" is judged by the model "fake-local" from "Local"
* When I run "Basics" against the agent "Docs helper"
* Then the judge's requests went to "fake-local"

## Implementation notes
- `apps/scoring` (no models): `metrics.py` (registry shared with the frontend catalog),
  `retrieval.py` (hit rate / recall / precision / MRR / nDCG, each returning its working),
  `judge.py` (rubrics, JSON parsing with salvage of cut-off replies), `aggregate.py`
  (mean / p50 / p95, boundary checks with margins; n/a → skipped).
- `apps/evals`: `EvalSuite` / `EvalCase` / `Boundary`; the editor saves a suite with its cases
  and boundaries in one request and bumps `version`; JSONL import (line-numbered errors, nothing
  half-imported) and export. `/api/evals/suites/`.
- `apps/benchmarks`: `BenchmarkRun` (suite + target snapshots, compare group, summary) and
  `CaseResult`; `execution.py` runs the agent loop from a snapshot (or a bare streamed
  completion) and scores; `benchmark-run` fans out `benchmark-case` children via `run_many`,
  then `finalize()` aggregates. Websocket `benchmark.progress|case|completed`.
  `/api/benchmarks/runs/` (+ `/retry/`).
- `apps/agents`: `snapshot()` / `from_snapshot()`; the runner accepts `folder_ids` so unsaved
  snapshot agents work.
- Frontend: Benchmarks list → suite editor (cases, metrics, judge, boundaries, JSONL) + run
  panel (agent or bare model on any connection, optional compare) → results (live progress,
  boundaries ✓/✗ with margins, metrics, per-case drill-down with the maths or the judge's
  reasoning, snapshot, retry, side-by-side Δ).
- Layering change during build: `evals` may also import `scoring` (to validate metric ids) and
  `providers` (judge connection). Enforced by the architecture test.
- **Found with a real local judge (Ollama `gemma4:e4b`):** reasoning models spend `max_tokens`
  thinking, so a 300-token judge returned cut-off or empty JSON and the run wrongly *passed*
  with n/a scores. Fixed: 2000-token budget, score salvage from cut-off JSON, and an unreadable
  verdict now fails the case (retryable). Re-run: every score judged, run passed.
- Tests: 12 scenarios here; 33 new pytest tests across the three apps.
