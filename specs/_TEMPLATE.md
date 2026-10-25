# NNNN — Title

- **Status:** Draft
- **Depends on:** 
- **Django apps:** 
- **Touches:** frontend / backend / jobs / infra

<!-- Save as specs/NNNN-short-name.feature.md. Everything above "# Feature:" is prose for
     humans. Everything under it is executed by Cucumber (make acceptance) once the status is
     Approved, In progress or Done. -->

## Why
What problem this solves for the user, and what you want to learn from building it.

## Scope
- In:
- Out (later specs):

## Design notes
Data model, endpoints, Hatchet tasks, websocket events, RAG choices. Call out anything that
changes ARCHITECTURE.md.

# Feature: One line saying what the user gets

Optional free text describing the feature.

## Background:
* Given I am signed in

## Scenario: AT-NNNN-01 — Short name of the behaviour
* Given some starting state
* When I do something
* Then I see "the result"
* And another observable outcome

## Scenario: AT-NNNN-02 — A rule with a data table
* When I fill in:
  | Field | Value |
  | Name  | Alice |
* Then I see "Saved"

## Scenario Outline: AT-NNNN-03 — The same check for several inputs
* When I enter <input>
* Then I see <message>

### Examples:
| input | message  |
| 0     | "Too low" |
| 11    | "Too high" |

## Implementation notes
_Filled in when Done: what was built, key files, deviations from the spec and why._
