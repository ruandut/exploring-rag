# 0012 — Stop a benchmark run

- **Status:** Done
- **Depends on:** 0006 (benchmarks), 0011 (timings)
- **Django apps:** `benchmarks` (cancel service + endpoint, cancellable cases)
- **Touches:** frontend, backend, jobs, acceptance (fake LLM gets a "stuck" mode)

## Why
Once a run starts, it runs to the end. With a slow local model and a big suite that can be an
hour of waiting (and an hour of a busy GPU) after you've already seen the run is wrong — a bad
system message, the wrong embedding, the wrong model. You need a way to stop it, keep what
already finished, and carry on later if you want.

## Scope
- In: a **Stop run** button on a running run; cases still in flight are interrupted (the
  model stops being called), cases not started never start; finished cases keep their
  results; the run is marked **Stopped**; **Resume** runs only the cases that didn't finish.
- Out (later): stopping both runs of a side-by-side with one button, a "stop all my runs"
  control, stopping from the Hatchet UI being reflected in the app.

## Decisions
1. **The database is the source of truth, Hatchet cancellation is the fast path.** Stopping
   flips the run to `cancelled` and every pending case to `cancelled` in one transaction, then
   cancels the parent Hatchet run (which drops the queued children). Any child that still
   starts sees its case isn't pending and exits at once; a child mid-answer stops through the
   `is_cancelled` hook the agent loop and every provider adapter already have — checked
   against the database, so it works even if Hatchet's cancel arrives late.
2. **A stopped run never passes.** Its status is `cancelled` ("Stopped"), not passed or failed.
   The summary still shows the metrics of the cases that finished, labelled "partial — N of M
   cases", and boundaries show as not checked — a missing score must never let a run pass.
3. **Late results are discarded.** A case that finishes after you pressed Stop (e.g. the judge
   was already answering) doesn't overwrite its "Stopped" status: results are saved only while
   the case is still pending.
4. **Resume = run the rest.** On a stopped run, **Resume** re-runs the stopped cases (and any
   failed ones) on the same snapshot, like "Retry failed cases" does; the run is running again
   and finalizes normally. Finished cases are not re-run.
5. **No new websocket event type.** `benchmark.completed` gains the status `cancelled`; cases
   send `benchmark.case` with status `cancelled`. (Contract change in `frontend/src/lib/socket.ts`.)
6. Stopping is per run. On the side-by-side page each run has its own Stop button.

## User experience
- A running run's header shows **Stop run** next to the progress. Pressing it marks the run
  **Stopped** within a couple of seconds, without reloading the page.
- Stopped cases show a grey **Stopped** badge; finished ones keep their scores.
- A stopped run's header shows **Resume** instead of "Retry failed cases".
- The suite's run list shows Stopped runs with their own badge.

## Design notes
- `BenchmarkRun.Status.CANCELLED = "cancelled"` and `CaseResult.Status.CANCELLED = "cancelled"`
  (choices only — no schema change beyond the choices migration).
- `benchmarks.services.cancel_run(run)`: atomic status flip (no-op for a finished run), then
  `on_commit` → `get_hatchet().runs.cancel(run.hatchet_run_id)` (best effort; errors logged),
  then a partial `finalize`-style summary and `benchmark.completed{status:"cancelled"}`.
  `POST /api/benchmarks/runs/<id>/cancel/` → 202, owner-only (404 otherwise).
- `services.retry_failed` also picks up `cancelled` cases, and `finalize()` leaves a run that's
  already cancelled alone (the parent may race the cancel).
- `execution.execute` takes an `is_cancelled` callable, passed to `runner.run(...)` and to the
  bare model's `stream_chat(...)`; `Cancelled` ends the case without a result. The
  `benchmark-case` task polls the case's status at most once a second.
- `services.record_result` saves with `UPDATE … WHERE status='pending'`.
- Frontend: Stop / Resume buttons in `run-view.tsx`, "Stopped" in `RunStatus` and case badges,
  partial-summary label, socket contract.
- Fake LLM: `stuck = true` makes every streamed answer drip one word every few seconds, so a
  run is reliably still in flight when a spec presses Stop; `stuck = false` restores speed.

# Feature: Stop a benchmark run

## Background:
* Given I am signed in
* And my provider is the fake LLM provider
* And "handbook.md" is indexed
* And the agent "Docs helper" exists
* And the suite "Basics" exists

## Scenario: AT-0012-01 — Stop a running run
* Given my provider answers very slowly
* When I run "Basics" against the bare model "fake-chat" from my default provider
* And I press "Stop run" while it is running
* Then the run is marked "Stopped" without reloading the page
* And every unfinished case shows "Stopped"
* And my provider receives no new requests for that run

## Scenario: AT-0012-02 — A stopped run never passes
* Given my provider answers very slowly
* When I run "Basics" against the agent "Docs helper"
* And I press "Stop run" while it is running
* Then the run is marked "Stopped"
* And the run summary says it is partial
* And I can't press "Stop run" again

## Scenario: AT-0012-03 — Resume runs only what didn't finish
* Given my provider answers very slowly
* When I run "Basics" against the bare model "fake-chat" from my default provider
* And I press "Stop run" while it is running
* And my provider answers at normal speed again
* And I press "Resume"
* Then the run finishes with 0 stopped cases
* And the run is marked "Passed" or "Failed", not "Stopped"

## Scenario: AT-0012-04 — Only the owner can stop a run
* Given another user has a running benchmark run
* Then I can't stop it

## Implementation notes
- **Backend** — `BenchmarkRun.Status.CANCELLED` / `CaseResult.Status.CANCELLED` (migration
  `0005_cancelled_status`). `services.cancel_run()` flips run + pending cases atomically,
  writes a partial summary (boundaries `passed: None`), sends `benchmark.completed`, and
  cancels the Hatchet parent on commit (best effort, logged). `finalize()` leaves a cancelled
  run alone and shares `_summary()` with it. `record_result()` saves with
  `UPDATE … WHERE status='pending'`, so late results are dropped. Resume reuses
  `retry_failed()` (stopped cases aren't passed, so they re-run).
- **Tasks** — `benchmark-case` exits at once if its case isn't pending; otherwise
  `_cancel_check()` gives `execute()` an `is_cancelled` that reads Hatchet's flag every call and
  the database at most once a second; `Cancelled` ends the case without a result.
- **API** — `POST /api/benchmarks/runs/<id>/cancel/` → 202, 409 if finished, 404 for others.
- **Frontend** — Stop run / Resume buttons, "Stopped" run and case badges, "Partial …"
  under Metrics, "not checked (run stopped)" on boundaries; socket contract gains `cancelled`.
- **Fake LLM** — `stuck = true` drips streamed answers one word every 3 s; reset per scenario.
- `BenchmarksPage.waitFinished()` now treats Stopped as finished.
