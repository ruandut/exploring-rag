# 0014 — Delete a suite

- **Status:** Done
- **Depends on:** 0006 (benchmarks)
- **Django apps:** `evals` (delete service), `benchmarks` (listing runs of deleted suites)
- **Touches:** frontend, backend

## Why
Suites pile up: experiments, copies, a suite made by accident with **New suite**. There's no
way to remove one from the UI. (The API already accepts `DELETE /api/evals/suites/<id>/` and
the frontend has an unused `useDeleteSuite` hook — but nothing calls it and no spec covers it.)

## Scope
- In: a **Delete suite** button in the suite editor, a confirmation, and a **Runs of deleted
  suites** list on the Benchmarks page so past results stay reachable.
- Out (later): undo / trash, deleting single runs, bulk delete.

## Decisions (reviewed 2026-10-26)
1. **Deleting a suite keeps its runs** (your call). Each run already carries a snapshot of the
   suite it tested (`suite_snapshot`), so it stays fully readable; its `suite` link becomes
   empty (`on_delete=SET_NULL`, unchanged).
2. **Runs of deleted suites are listed on the Benchmarks page** — suite name (from the
   snapshot), target, status, date — each linking to its run page. The section only appears
   when there are such runs.
3. **A running run doesn't block the delete.** It tested a snapshot, so it finishes normally and
   then shows up under Runs of deleted suites. (The earlier draft blocked deleting only because
   cascading would have removed a run mid-write; keeping runs makes that unnecessary.)
4. The confirmation names the suite and says its runs are kept, e.g. "Delete “Bible”? Its 3
   runs are kept under Runs of deleted suites. This can't be undone."
5. Model speed (spec 0011) keeps counting those runs — they're still your runs.
6. Only the owner can delete (404 for anyone else), as for every suite endpoint.
7. **Layering stays intact**: `evals` deletes the suite and knows nothing about runs; the run
   count in the dialog comes from the benchmarks runs endpoint the suite page already uses.

## User experience
- Suite editor: **Delete suite** (destructive outline button, next to Save suite).
- Confirmation dialog (**Delete** / **Cancel**). After deleting you land on the Benchmarks page.
- Benchmarks page: **Runs of deleted suites** card below the suites.
- A run page whose suite was deleted shows "Suite deleted" instead of the back link.

## Design notes
- `evals.services.delete_suite(suite)`; `SuiteViewSet.perform_destroy` calls it.
- `GET /api/benchmarks/runs/?suite=deleted` → the owner's runs whose suite is gone.
- Frontend: button + `AlertDialog` in `suite-editor.tsx` using `useDeleteSuite` and the suite's
  `useRuns` count; `useDeletedSuiteRuns()` + a card on `benchmarks.index.tsx`; "Suite deleted"
  on the run page. Deleting invalidates the suites and deleted-runs queries.

# Feature: Delete a suite

## Background:
* Given I am signed in
* And my provider is the fake LLM provider
* And "handbook.md" is indexed
* And the agent "Docs helper" exists
* And the suite "Basics" exists

## Scenario: AT-0014-01 — Delete a suite and keep its runs
* Given a finished run of "Basics" against "Docs helper"
* When I delete the suite "Basics"
* Then the confirmation says its 1 run is kept
* When I press "Delete"
* Then I'm on the Benchmarks page and "Basics" isn't listed
* And "Basics" is listed under runs of deleted suites
* And that run still opens with its results

## Scenario: AT-0014-02 — Cancel keeps everything
* When I delete the suite "Basics"
* And I press "Cancel"
* Then "Basics" shows 3 cases

## Scenario: AT-0014-03 — A run still going finishes after its suite is deleted
* Given my provider answers very slowly
* And I run "Basics" against the agent "Docs helper"
* When I delete the suite "Basics" and confirm
* And my provider answers at normal speed again
* Then that run finishes
* And "Basics" is listed under runs of deleted suites

## Scenario: AT-0014-04 — Only the owner can delete a suite
* Given another user has a suite "Theirs"
* Then I can't delete "Theirs"

## Implementation notes
- **Backend** — `evals.services.delete_suite()` (called by `SuiteViewSet.perform_destroy`);
  the run's FK stays `SET_NULL`, so nothing in `benchmarks` changes on delete. Runs list
  filter `?suite=deleted`. Execution and scoring already read only `suite_snapshot`, so a
  suite-less run finishes and resumes normally.
- **Frontend** — `delete-suite-dialog.tsx` (AlertDialog, stays open until the delete
  finishes, then navigates to /benchmarks) with the run count from the suite's `useRuns`;
  `deleted-suite-runs.tsx` card on the Benchmarks page (hidden when empty); "Suite deleted"
  on the run page instead of the back link. Deleting invalidates suites + deleted-suite runs.
- **Acceptance** — "another user has a suite" now uses the shared `otherApi`; the fake LLM's
  stuck drip speeds up when `stuck` is switched off, so a run left in flight can finish.
- **Spec change while building** — the earlier draft's "block delete while a run is running"
  was dropped once runs are kept (it only existed to protect cascaded runs).
