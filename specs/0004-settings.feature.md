# 0004 — Settings: LLM provider + indexing configuration

> **Changed by 0010:** the embedding model, dimensions and chunking moved from Settings into
> each embedding (Embeddings page). Settings keeps the chat provider and connections; Test
> connection checks chat only.

- **Status:** Done
- **Depends on:** 0001
- **Django apps:** `providers` (LLM config) + `rag` (indexing defaults)
- **Touches:** frontend, backend, jobs

## Why
Each user brings their own OpenAI-compatible endpoint and chooses how documents are indexed.

## Scope
- In: provider config (base URL, API key, chat model, embedding model, embedding dimensions);
  a "Test connection" button; indexing defaults (chunking strategy, size, overlap).
- Out: multiple providers per user, usage/cost tracking.

## Design notes
- `providers.ProviderConfig(owner, base_url, api_key_encrypted, api_key_last4, chat_model,
  embedding_model, embedding_dimensions)`. The key is encrypted at rest with Fernet
  (`FIELD_ENCRYPTION_KEY`) and is write-only in the API.
- `rag.IndexingConfig(owner, strategy, chunk_size, chunk_overlap)` with a DB check constraint
  `overlap < size`.
- Changing the endpoint / embedding model / dimensions, or any chunking setting, answers
  `409 reindex_required` until the user confirms. On confirm:
  - providers pushes the Hatchet event `provider.embedding_changed` (it may not import rag);
  - rag starts `reindex-user-documents` directly for chunking changes.
  The task listens to that event too, and reports `job.completed {job: "reindex"}` over the
  websocket. Until spec 0003 adds documents it re-indexes 0 documents.

# Feature: Settings for the LLM provider and indexing

Users configure their own OpenAI-compatible provider and how documents are chunked.
The scenarios run against the real app with a fake OpenAI-compatible provider.

## Background:
* Given I am signed in

## Scenario: AT-0004-01 — The API key never comes back from the server
* Given I have saved a provider with API key "sk-acceptance-1234abcd"
* When I open the Settings page
* Then the API key field says a key ending in "abcd" is saved
* And no response the browser received contains "sk-acceptance-1234abcd"

## Scenario: AT-0004-02 — Test connection reports success
* Given I open the Settings page
* When I fill in the provider form for the fake provider with API key "sk-good-key"
* And I press "Test connection"
* Then the connection results show "Chat: Replied “OK”"

## Scenario: AT-0004-02 — Test connection shows the provider's error message
* Given I open the Settings page
* When I fill in the provider form for the fake provider with API key "bad-key"
* And I press "Test connection"
* Then the "Chat" check fails with "Incorrect API key provided"

## Scenario: AT-0004-03 — Overlap must be smaller than the chunk size
* Given my provider is the fake LLM provider
* And I start a new embedding
* When I set the chunk size to 256 and the overlap to 256
* Then I see "Overlap must be smaller than the chunk size."
* And the "Create embedding" button is disabled
* And the API rejects chunk size 256 with overlap 256

_AT-0004-04 (changing the embedding model or chunking asks to re-index, and Cancel keeps the old
settings) moved to spec 0010: the model and chunking now belong to each embedding (AT-0010-08;
Cancel and chunking changes are covered by pytest in `apps/rag/test_embeddings.py`)._

## Implementation notes
- Backend: `apps/providers` (model, Fernet `crypto.py`, `services.py` incl. `client_for(user)` and
  `test_connection`, write-only serializer, admin hides the key) and `apps/rag` (`IndexingConfig`
  with a DB check constraint, `reindex-user-documents` task). New platform helper
  `apps/jobs/events.py` (`push_event_on_commit`).
- Frontend: `features/settings/` (React Query hooks, provider + indexing forms, re-index
  confirmation dialog, presets for OpenAI / OpenRouter / Ollama).
- Tests: 7 scenarios here (`make acceptance`, against a fake OpenAI-compatible server) plus
  pytest in `apps/providers/test_providers.py` and `apps/rag/test_indexing_config.py`.
- The re-index task re-indexes 0 documents until spec 0003; the confirm → event → Hatchet →
  websocket → toast path is fully exercised.
- First spec built under the executable-specs rule; the BDD toolchain (`acceptance/`) was
  introduced alongside it.
