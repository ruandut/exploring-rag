# 0002 — System Design learning page

- **Status:** Done
- **Depends on:** 0001
- **Django apps:** — (frontend only; reads `/api/health/`)
- **Touches:** frontend

## Why
The owner is learning. One page should explain the whole architecture and exactly how RAG
works, step by step, mapped to what *this* system uses — and stay current as the system changes.

## Scope
- In: architecture diagram, live health, components and Django app tables, the RAG pipeline step
  by step, realtime/job flows, evaluation, how testing works, glossary, spec index.
- Out: interactive playgrounds (maybe later: "embed two sentences and see their distance").

## Design notes
- Content lives in `frontend/src/features/system-design/content.ts`; the diagram in
  `architecture-diagram.tsx`. Each item has a status: `live` / `demo` / `planned`.
- The spec list is read from `specs/*.md` at build time (`specs.ts`), so it can't drift.
- CLAUDE.md's Definition of Done requires updating this page with every spec; the drift checks
  below fail if the Django apps or specs on disk aren't shown.

# Feature: System Design learning page

## Background:
* Given I am signed in
* And I open the "System design" page

## Scenario: AT-0002-01 — Architecture shows the big picture and live health
* Then I see the architecture diagram
* And the health strip shows:
  | Postgres       | ok |
  | Redis          | ok |
  | Your websocket | ok |
* And the Django apps table lists every app in backend/apps

## Scenario: AT-0002-02 — RAG explained step by step
* When I open the "How RAG works" tab
* Then the "Indexing steps" list has 5 steps
* And the "Answering steps" list has 7 steps

## Scenario: AT-0002-03 — Realtime and jobs walkthroughs
* When I open the "Realtime & jobs" tab
* Then I see "What happens when you send a chat message"
* And I see "What happens when a background job reports progress"
* And I see "Hatchet features in use"

## Scenario: AT-0002-04 — Evaluation explains the benchmark metrics
* When I open the "Evaluation" tab
* Then I see "What happens when you run a benchmark"
* And I see "Faithfulness"
* And I see "nDCG@k"

## Scenario: AT-0002-05 — Testing explains how specs become tests
* When I open the "Testing" tab
* Then I see "Specs are the tests"
* And I see "How specs become tests"
* And the "Test layers" table lists "Executable specs (acceptance)"

## Scenario: AT-0002-06 — Every spec on disk is listed with its status
* When I open the "Glossary & specs" tab
* Then every spec in the specs folder is listed with its status

## Implementation notes
- Executable via `make acceptance`. The drift checks (AT-01 apps table, AT-06 spec list) read the
  repo at test time.
