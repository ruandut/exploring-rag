# 0013 — Chat setup card and a one-row message bar

- **Status:** Done
- **Depends on:** 0010
- **Django apps:** none (frontend only)
- **Touches:** frontend

## Why
The message bar held three pickers (embedding, model, agent) next to the send button. On a
normal-width window they wrapped onto two rows, which looked messy and pushed the hint text
around. The choices matter most when a chat *starts*, so ask for them up front, and keep the
bar to one tidy row afterwards.

What you learn building it: deriving UI state from the URL (a chat with `?c=` never needs
setup), React's "adjust state when a prop changes" pattern instead of `setState` in an effect,
and nesting Radix popovers (the model picker inside the options popover).

## Scope
- In: a new chat opens on a **Set up this chat** card with the Agent, Embedding and Model
  pickers (pre-filled with the last chat's choices) and a **Start chat** button; pressing it
  swaps the card for the message bar. The bar has an info button (**Chat options**) that opens
  the same three pickers. An existing conversation opens straight on the message bar.
- Out: remembering per-agent defaults, saving the settings before the first message.

## Design notes
- Frontend only: `features/chat/chat-options.tsx` (`ChatOptionsForm`, `ChatSetupCard`,
  `ChatOptionsButton`), `AgentPicker` moved into `chat-pickers.tsx`; `Composer` takes an
  `options` slot instead of the pickers. No API or websocket change.

# Feature: Chat setup card

## Background:
* Given I am signed in
* And my provider is the fake LLM provider

## Scenario: AT-0013-01 — A new chat asks for its settings before the message bar
* Given the agent "Docs helper" exists
* When I start a new chat
* Then I see the chat setup card with the Agent, Embedding and Model pickers
* And there is no message bar yet
* When I press "Start chat"
* Then the setup card is gone and the message bar is shown

## Scenario: AT-0013-02 — The message bar keeps the settings behind its info button
* Given the agent "Docs helper" exists
* When I start a new chat
* And I press "Start chat"
* And I press "Chat options"
* Then I see the Agent, Embedding and Model pickers

## Scenario: AT-0013-03 — An existing conversation opens straight on the message bar
* Given I had a conversation with "Docs helper"
* And I have the conversation "Hello there" open
* Then the setup card is gone and the message bar is shown

## Implementation notes
- `ChatSetupCard` shows when there is no `?c=`, no turns and "Start chat" hasn't been pressed
  for this chat; the flag resets during render whenever `?c=` changes, so every new chat asks
  again. The pickers fill their row as form fields (outline triggers) in both places.
- Acceptance: `ChatPage` exposes `setupCard`, `startChat()` and `showOptions()`; `ask()`
  presses "Start chat" first on a new chat, and the `select*` helpers open "Chat options" when
  the card is gone, so earlier chat specs read the same. Steps in `steps/chat-setup.steps.ts`.
- The empty chat after deleting the open one (AT-0009-04/05) now shows the setup card.
