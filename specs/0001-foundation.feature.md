# 0001 — Foundation: auth, app shell, websocket, Hatchet

- **Status:** Done
- **Depends on:** —
- **Django apps:** `core`, `accounts`, `realtime`, `jobs`
- **Touches:** frontend, backend, jobs, infra

## Why
Prove every moving part works together before building features: browser ↔ API ↔ Hatchet ↔
worker ↔ Redis ↔ websocket ↔ browser.

## Scope
- In: JWT login, navigation drawer, authenticated websocket, Hatchet worker with a progress job,
  a streamed + cancellable demo agent, a cron task.
- Out: real documents, LLM calls, agent configuration (specs 0003–0005).

## Design notes
- `POST /api/auth/token/`, `POST /api/auth/token/refresh/`, `GET /api/auth/me/`, `GET /api/health/`,
  `POST /api/jobs/demo-index/`.
- Websocket `/ws/events/`; the first message must be `{type:"auth", token}` within 10 s, else close 4401.
- Hatchet tasks: `demo-index` (retries 2, backoff, 2 concurrent per user), `demo-agent`
  (streams), `nightly-housekeeping` (cron `0 3 * * *`).

# Feature: Foundation — sign-in, live connection and background work

## Scenario: AT-0001-01 — Signing in lands on Chat
* Given I go to the sign-in page
* When I sign in with my username and password
* Then I am on the "Chat" page
* And the user menu shows "Websocket: Live"

## Scenario: AT-0001-01 — A wrong password is rejected
* Given I go to the sign-in page
* When I sign in with my username and the password "not-my-password"
* Then I see "Wrong username or password"

## Scenario: AT-0001-02 — Pages need a signed-in user
* When I visit "/library" without signing in
* Then I am on the sign-in page
* And the API answers 401 for "/api/auth/me/" without a token

## Scenario: AT-0001-03 — A refresh token gets a new access token
* When I exchange my refresh token
* Then I get a new access token that works for "/api/auth/me/"

## Scenario: AT-0001-04 — The websocket needs a valid token first
* When I open a websocket and authenticate with my token
* Then my websocket receives "auth.ok"
* When I open a websocket and authenticate with the token "garbage"
* Then that websocket receives "auth.error" and is closed with code 4401

## Scenario: AT-0001-05 — Job progress reaches only the user who started it
* Given my websocket is connected
* And another user's websocket is connected
* When I start the demo indexing job with 3 steps
* Then my websocket receives 3 "job.progress" events and then "job.completed"
* And the other user's websocket receives no "job.progress" events

## Scenario: AT-0001-06 — The demo job's progress bar fills live
* Given I am signed in
* And I open the "System design" page
* And I open the "Realtime & jobs" tab
* When I press "Run demo job"
* Then I see "Done"

## Scenario: AT-0001-07 — The agent streams thinking, a tool call, chunks and an answer
* Given I am signed in
* When I ask the agent "What is RAG?"
* Then I see the agent's thinking
* And I see the tool call "search_documents"
* And I see 2 retrieved chunks
* And the agent finishes its answer

## Scenario: AT-0001-07 — Stop cancels the agent mid-answer
* Given I am signed in
* When I ask the agent "Please stop halfway"
* And I stop the agent while it is answering
* Then I see "Stopped."

## Scenario: AT-0001-08 — The navigation drawer
* Given I am signed in
* Then the navigation drawer lists:
  | Chat          |
  | Agents        |
  | Library       |
  | Benchmarks    |
  | Settings      |
  | System design |
* When I open the "Settings" page from the drawer
* Then "Settings" is highlighted in the drawer
* When I collapse the drawer
* Then the drawer only shows icons

## Scenario: AT-0001-09 — The nightly cron is registered with Hatchet
* Then Hatchet has the cron "0 3 * * *" for "nightly-housekeeping"

## Implementation notes
- Executable via `make acceptance`. Unit/integration tests: `apps/accounts/test_auth.py`,
  `apps/realtime/test_consumer.py`.
- Found and fixed: redis-py 8 defaults `socket_timeout` to 5 s, the same as channels-redis'
  blocking pop, which randomly dropped websockets → `socket_timeout: 15` in `CHANNEL_LAYERS`.
- Found and fixed: the authenticated layout is pinned to the viewport height and pages scroll
  inside it; before that, long chats pushed the composer off screen.
- The demo agent streams slowly on purpose (~5 s) so you can watch it and try Stop.
