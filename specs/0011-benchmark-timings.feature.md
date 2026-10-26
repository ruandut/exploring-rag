# 0011 — Benchmark timings: where the time goes, and which model is fastest

- **Status:** Done
- **Depends on:** 0006 (benchmarks), 0010 (runs name their model)
- **Django apps:** `benchmarks` (timing capture, summary, model speed selector + endpoint),
  `scoring` (new operational metrics)
- **Touches:** frontend, backend, acceptance (fake LLM gets a slow model)

## Why
Benchmarks already record time to first token, total latency and answer tokens per case, but
they can't answer "how fast is this model?":

- Time to first token mixes network, prompt processing, document search and reasoning — it
  isn't a measure of the model's generation speed.
- An agent's total latency is one number; you can't tell whether search, reasoning or writing
  ate the time.
- Speed can only be compared between the two runs of one side-by-side, never across all runs.
- The side-by-side colours every increase green, so the *slower* model looks better on the
  timing rows.

## Scope
- In: a per-case timing breakdown (waiting, searching, reasoning, writing), tokens per second,
  judge time kept separate, timing metrics in the run summary and in boundaries, how long the
  whole run took, a timing bar per run, a **Model speed** table across runs, and correct
  better/worse colouring in the side-by-side.
- Out (later): provider-reported token counts (spec 0007 — tokens per second switches to real
  completion tokens when it lands), cost in money, charts over time, timing for chat.

## Decisions
1. **Phases are measured from the events the agent already emits** — no change to
   `agents.runner` or the websocket contract. The benchmark's `emit` callback timestamps
   every event; each moment of a case belongs to the phase of the latest event:

   | Phase | From | Until the next event of another phase |
   |---|---|---|
   | Waiting | the question is sent | first model output (network + prompt processing) |
   | Searching | `agent.tool_call` (and the pipeline's search) | `agent.retrieval` |
   | Reasoning | `agent.thinking` | |
   | Writing | `agent.token` | the answer ends |

   The four phases always add up to the case's total latency, so the timing bar is honest.
   An agent may cycle (think → search → think → write); each phase sums all its stretches.
2. **Tokens per second = answer tokens ÷ writing time** — the cleanest measure of raw
   generation speed. No writing time (empty answer) → n/a, never 0 or ∞.
3. **The judge is timed but never mixed in.** `judge_ms` is shown on its own; total latency
   still stops before scoring starts.
4. **Timing metrics are operational metrics** like `ttft`: always recorded, aggregated as
   mean / p50 / p95, usable in boundaries (e.g. `tokens_per_second · p50 · ≥ · 20`).
5. **Each metric has a direction** (`higher_is_better` already exists on `Metric` and in the
   frontend catalog). The side-by-side colours by it: green = better, red = worse, and the
   delta cell's accessible name says "better" or "worse". Answer tokens stay uncoloured —
   more tokens isn't better or worse by itself.
6. **Model speed groups by the model that actually answered** — the resolved
   `connection · model` label (the default provider's chat model is resolved at start, so ""
   never appears). Agent runs and bare runs of the same model pool together; it's the model's
   speed, not the agent's. Only finished cases count; failed cases are left out.
7. **Old runs keep working.** Cases from before this spec show n/a for the new timings; the
   model speed table uses only cases that have them.

## User experience
- **Case drill-down**: "First token 0.42 s · total 1.80 s · 38 tokens · 27.1 tokens/s", then
  "Waiting 0.12 s · Searching 0.25 s · Reasoning 0.05 s · Writing 1.38 s", and separately
  "Judge 2.10 s".
- **Run header**: "Took 1m 12s" (from start to finish, including queueing).
- **Metrics table**: new rows Tokens per second, Waiting, Searching, Reasoning, Writing and
  Judge time, after the existing timing rows.
- **Timing card**: one stacked bar of the mean time per phase (each segment labelled with its
  phase and seconds), so you see at a glance whether search or the model is the bottleneck.
- **Side by side**: timing rows show the faster target as better.
- **Benchmarks page → Model speed**: one row per model — runs, cases, typical first token
  (p50), slow-case total (p95), typical tokens per second (p50) — sorted fastest first by
  tokens per second.

## Design notes
- `benchmarks.models.CaseResult`: `waiting_ms`, `search_ms`, `reasoning_ms`, `writing_ms`,
  `judge_ms` (all nullable ints) and `tokens_per_second` (nullable float). One migration.
- `BenchmarkRun.target_snapshot` gains `model_label` (resolved at `start_runs`) — what Model
  speed groups by. Older runs fall back to `target_label`.
- `benchmarks.execution`: a small `PhaseClock` records `(phase, monotonic())` from the `emit`
  callback (agents) or from `Thinking` / `Text` events (bare model — which also starts
  handling `Thinking`). `judge_ms` wraps `_score`.
- `scoring.metrics`: operational metrics `tokens_per_second` (higher is better),
  `waiting_time`, `search_time`, `reasoning_time`, `writing_time`, `judge_time` (seconds,
  lower is better). `benchmarks.services.OPERATIONAL` maps them to the new fields.
- `benchmarks.selectors.model_speed(owner)` + `GET /api/benchmarks/speed/` — filtered by
  owner, aggregated with `scoring.aggregate`.
- Frontend: `run-view.tsx` (drill-down, header, Timing card), comparison in
  `benchmarks.runs.$runId.tsx` uses `higherIsBetter`, new `model-speed.tsx` on the
  Benchmarks page, `metrics.ts` catalogue entries.
- Fake LLM: a `fake-slow` model that answers like `fake-chat` but drips tokens much more
  slowly, so speed ordering is deterministic.
- No websocket, port or technology changes → ARCHITECTURE.md only gets the new metrics in
  the benchmarks data-flow description.

# Feature: Benchmark timings — where the time goes, and which model is fastest

## Background:
* Given I am signed in
* And my provider is the fake LLM provider
* And "handbook.md" is indexed
* And the agent "Docs helper" exists
* And the suite "Basics" exists

## Scenario: AT-0011-01 — A case shows where its time went
* When I run "Basics" against the agent "Docs helper"
* And I open the case "What is the refund window?"
* Then I see its time to first token, total latency and tokens per second
* And I see how long it spent waiting, searching, reasoning and writing
* And I see the judge's time shown separately

## Scenario: AT-0011-02 — The phases add up to the total
* When I run "Basics" against the agent "Docs helper"
* Then for every case, waiting, searching, reasoning and writing add up to its total latency

## Scenario: AT-0011-03 — A bare model doesn't search
* When I run "Basics" against the bare model "fake-chat" from my default provider
* And I open the case "What is the refund window?"
* Then its searching time shows "n/a"

## Scenario: AT-0011-04 — The run summary shows speed and duration
* When I run "Basics" against the agent "Docs helper"
* Then the run summary shows the mean of "Tokens per second"
* And the run header shows how long the run took
* And the timing bar shows the time spent waiting, searching, reasoning and writing

## Scenario: AT-0011-05 — A speed boundary
* Given "Basics" has the boundary "tokens_per_second p50 ≥ 1"
* When I run "Basics" against the agent "Docs helper"
* Then the boundary "tokens_per_second p50 ≥ 1" shows ✓

## Scenario: AT-0011-06 — Side by side shows the faster model as better
* When I compare "Basics" on the bare model "fake-chat" with the bare model "fake-slow"
* Then the "Total latency" delta is marked "worse"
* And the "Tokens per second" delta is marked "worse"

## Scenario: AT-0011-07 — Model speed across runs
* Given I have run "Basics" against the bare model "fake-chat" from my default provider
* And I have run "Basics" against the bare model "fake-slow" from my default provider
* And I have run "Basics" against the agent "Docs helper" using the model "fake-chat"
* When I open the "Benchmarks" page
* Then the model speed table lists "fake-chat" with 2 runs and "fake-slow" with 1 run
* And "fake-chat" is listed above "fake-slow"

## Implementation notes
- **Capture** — `benchmarks/execution.py`: `PhaseClock` timestamps each `agent.*` event from the
  run's `emit` callback (bare models: `Thinking` / `Text` events). Boundaries are rounded to ms
  once, then subtracted, so `waiting + search + reasoning + writing == latency_ms` exactly.
  `agent.retrieval` switches back to *waiting* (the model then reads the results). The clock is
  read through `execution._now()` so pytest can drive time.
- **Data** — `CaseResult.waiting_ms / search_ms / reasoning_ms / writing_ms / judge_ms /
  tokens_per_second` (migration `0003_case_timings`); `target_snapshot.model_label` is
  resolved at start (an agent's empty model → the default provider's chat model).
- **Metrics** — `tokens_per_second` (higher is better) and `waiting_time`, `search_time`,
  `reasoning_time`, `writing_time`, `judge_time` (seconds) in `scoring.metrics`; aggregated by
  `finalize()` via `OPERATIONAL`; selectable in boundaries (judge time excluded there).
- **Model speed** — `benchmarks/selectors.py: model_speed(owner)`, `GET /api/benchmarks/speed/`,
  `features/benchmarks/model-speed.tsx` on the Benchmarks page; refreshed on
  `benchmark.completed`.
- **UI** — case drill-down speed + phases + judge time, "Took …" in the run header, a Timing
  card (stacked bar + labelled legend), and side-by-side deltas coloured by
  `direction(metric)` with an accessible "Delta, better/worse" name.
- **Fake LLM** — any model containing "slow" (`fake-slow`) streams 10× slower.
- **Wording change** — AT-0011-07 now says `I open the "Benchmarks" page` to reuse the
  existing navigation step.
