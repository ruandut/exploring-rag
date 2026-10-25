# 0009 — Delete a chat

- **Status:** Done
- **Depends on:** 0005
- **Django apps:** `chat` (uses `agents` / `jobs` to cancel a run)
- **Touches:** frontend, backend

## Why
Conversations pile up in the Chat sidebar and there is no way to get rid of one. Deleting a
chat should be safe (confirmed first, only ever your own) and clean (its messages go with it,
and an answer that is still streaming is stopped rather than left running with nowhere to save).

What you learn building it: a confirmed destructive action with a shadcn `AlertDialog`, a React
Query mutation that invalidates a list, and how a REST request can stop a Hatchet run that a
websocket started.

## Scope
- In: delete one conversation from the chat list (with confirmation); its messages are
  deleted with it; owner-only; deleting the conversation you have open returns you to an empty
  chat; a reply still streaming in that conversation is cancelled first.
- Out (later specs): bulk delete, undo / trash, renaming, archiving.

## Design notes
- **REST:** `DELETE /api/chat/conversations/<id>/` → `204`. The viewset already mixes in
  `DestroyModelMixin`; `perform_destroy` will call `services.delete_conversation(user, id)`
  instead of deleting directly, so the business rule lives in `services.py`.
  Another user's id (or an unknown id) → `404`, never `403`, so ids don't leak whether they
  exist — the queryset is `selectors.conversations_for(user)`.
- **Messages:** `Message.conversation` is `on_delete=CASCADE`, so deleting the conversation
  deletes its messages in the same transaction. No orphan rows.
- **Active run:** the reply is only saved when its stream ends, so today nothing in the
  database knows a run is in flight. Add `Conversation.active_run_id` (blank when idle): set
  by `agent.ask` right after the run starts, cleared by `save_reply`.
  `delete_conversation` cancels that run in Hatchet (`runs.cancel`) *before* deleting.
  The relay then ends; `save_reply` must tolerate the conversation being gone (save nothing,
  don't crash on the foreign key).
  The socket that started the run gets `agent.cancelled{run_id}` (an existing event type —
  no change to the contract in `socket.ts`), so the UI stops showing it as streaming.
- **Frontend (`src/features/chat`):** each conversation in the `Conversations` list gets a
  "Delete chat" button (accessible name `Delete "<title>"`). It opens a shadcn `AlertDialog`
  asking *Delete this chat?* with *Cancel* and *Delete*. A `useDeleteConversation` mutation
  calls the endpoint and invalidates `["conversations"]`; if the deleted chat was open
  (`?c=<id>`), it navigates to `/chat` with no `c` and clears the open turns.
- **Agents:** deleting a conversation never deletes its agent (the FK is on the conversation).

# Feature: Delete a chat

## Background:
* Given I am signed in
* And my provider is the fake LLM provider

## Scenario: AT-0009-01 — Deleting a chat asks for confirmation first
* Given I had a conversation with "Docs helper"
* When I delete the conversation "Hello there"
* Then I am asked "Delete this chat?"
* When I press "Cancel"
* Then the conversation "Hello there" is still in my chat list

## Scenario: AT-0009-02 — A deleted chat disappears with its messages
* Given I had a conversation with "Docs helper"
* When I delete the conversation "Hello there"
* And I press "Delete"
* Then the conversation "Hello there" is not in my chat list
* And after reloading the page it is still gone
* And its messages can no longer be opened

## Scenario: AT-0009-03 — You can't delete another user's chat
* Given another user has a conversation "Their secret plans"
* Then I don't see "Their secret plans" in my chat list
* And deleting it through the API returns 404
* And the other user still has the conversation "Their secret plans"

## Scenario: AT-0009-04 — Deleting the open chat takes you to an empty chat
* Given I had a conversation with "Docs helper"
* And I have the conversation "Hello there" open
* When I delete the conversation "Hello there"
* And I press "Delete"
* Then I am in a new, empty chat

## Scenario: AT-0009-05 — Deleting a chat that is still answering stops the agent first
* Given the agent "Docs helper" can search all my folders
* When I ask "Docs helper" a long question
* And I delete that conversation while the agent is answering
* And I press "Delete"
* Then I am in a new, empty chat
* And the agent run is cancelled
* And no reply is saved for the deleted conversation

## Implementation notes
- `apps/chat`: `Conversation.active_run_id` (migration 0002), set by `services.mark_run_started`
  right after `agent.ask` starts the run and cleared by `save_reply`. If the chat was deleted
  while the run was still starting, `agent.ask` cancels the run straight away.
  `services.delete_conversation(user, id)` filters by owner (`DoesNotExist` → 404 in the view's
  `destroy`), cancels an active run in Hatchet (`runs.cancel`; a Hatchet error is logged and
  doesn't block the delete), pushes `agent.cancelled`, then deletes (messages cascade).
  `save_reply` locks the conversation row and returns `None` when it's gone.
- `apps/realtime`: `send_to_user(..., cancel_background=key)`. The consumer cancels that
  background task on whichever of the user's sockets owns it. That's how a REST request stops
  the relay a socket started, which may live in another Daphne process. It's generic platform
  plumbing, not a new event type, so `socket.ts` is unchanged.
- Frontend: `useDeleteConversation` (invalidates `["conversations"]`),
  `features/chat/delete-conversation-dialog.tsx` (shadcn `AlertDialog`), and a trash button
  per list item named `Delete "<title>"`, a sibling of the link rather than nested inside it.
  Deleting the open chat clears its turns and drops `?c=`. Deleted ids are remembered, so a late
  `agent.started` can't navigate back to one. The list now also refreshes on `agent.started`,
  so a chat that is still answering is already listed and can be deleted.
- Tests: `test_at_0009_02/03/05_*` in `apps/chat/test_chat.py`, and
  `test_at_0009_05_a_pushed_event_can_cancel_a_sockets_background_task` in
  `apps/realtime/test_consumer.py`. Acceptance: `steps/chat.steps.ts`, `support/chat.ts`
  (another user's chat via the demo agent over a socket; saved replies by run id), list
  helpers in `pages/chat-page.ts`, and `ApiClient.delete`.
- No wording changes to the approved scenarios.
