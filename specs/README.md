# Specs — executable acceptance tests in Markdown

Every feature is one file: `NNNN-short-name.feature.md`, copied from [`_TEMPLATE.md`](_TEMPLATE.md).
It's a document people read **and** a test suite Cucumber runs (Specification by Example / BDD).

```
specs/0004-settings.feature.md   ← you write this
        │  Cucumber.js parses "Markdown with Gherkin"
        ▼
acceptance/steps/*.steps.ts      ← step definitions match each sentence
        │  call
        ▼
acceptance/pages/*, support/*    ← page objects (Playwright), ApiClient, SocketClient, fake LLM
        │  drive
        ▼
the running app (make up / api / worker / web)
```

## Anatomy of a spec

- **Prose** (Why, Scope, Design notes, Implementation notes) is ignored by Cucumber.
- `# Feature: …` starts the executable part.
- `## Background:` steps run before every scenario.
- `## Scenario: AT-NNNN-nn — name` is one acceptance test. Steps are bullets:
  `* Given …`, `* When …`, `* Then …`, `* And …`.
- `"quoted"` words and numbers become step parameters; a Markdown table under a step is a data table.
- `## Scenario Outline:` + `### Examples:` table runs the same steps once per row.

## Lifecycle

`Draft` → `Approved` → `In progress` → `Done`

| Status | Runs in `make acceptance`? | Meaning |
|---|---|---|
| Draft | no | Still being written. Ask Claude to review the scenarios. |
| Approved | **yes** (fails until built) | Ready to build — tell Claude *"implement spec NNNN"*. |
| In progress | yes | Being built; red scenarios show what's left. |
| Done | yes | Every scenario passes, plus `make test` and `make check`. |

Run one spec, even a draft: `cd acceptance && vp run test -- ../specs/0005-agents-and-chat.feature.md`
(or `pnpm exec cucumber-js ../specs/…`). Watch the browser: `HEADED=1 make acceptance`.

## Writing good scenarios

- **User's point of view.** "When I press "Save"", not "When I POST /api/x". Use the API only
  where the API *is* the user (e.g. "no response contains the key").
- **One behaviour per scenario**, named after the rule it proves.
- **Observable outcomes.** "Then I see "Re-index finished"", not "Then the task ran".
- **Reuse steps.** Check `acceptance/steps/common.steps.ts` before inventing new wording.
- **Deterministic.** Never depend on a real LLM — the fake provider stands in. Quality of real
  models is measured by Benchmarks (spec 0006), not by acceptance tests.
- Edge cases of pure logic belong in pytest, not in scenarios.

## Index

| Spec | Title | Status |
|---|---|---|
| [0001](0001-foundation.feature.md) | Foundation: auth, shell, websocket, Hatchet | Done |
| [0002](0002-system-design-page.feature.md) | System Design learning page | Done |
| [0003](0003-library.feature.md) | Library: folders, uploads, indexing | Done |
| [0004](0004-settings.feature.md) | Settings: LLM provider + indexing config | Done |
| [0005](0005-agents-and-chat.feature.md) | Agents + RAG chat (incl. local models) | Done |
| [0006](0006-benchmarks.feature.md) | Benchmarks: suites, metrics, boundaries, runs | Done |
| [0007](0007-benchmarks-extras.feature.md) | Benchmarks II: generated test sets, prompt injection, format rules, repeats, tokens | Draft |
| [0009](0009-delete-chat.feature.md) | Delete a chat | Done |
| [0010](0010-embeddings.feature.md) | Embeddings: named indexes, model picker, chat with agent + embedding + model | Done |

The in-app System Design page reads this folder directly, so its spec list is always current.
