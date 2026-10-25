# 0003 — Library: folders, uploads, indexing

- **Status:** Done
- **Depends on:** 0001, 0004 (needs an embeddings endpoint)
- **Django apps:** `library` (folders, documents) + `rag` (indexing task, `Chunk`)
- **Touches:** frontend, backend, jobs

## Why
Get real documents into the system and turn them into searchable vectors.

## Scope
- In: nested folders; multi-file upload (PDF, DOCX, MD, TXT); per-document indexing status;
  delete / move / re-index; the `index-document` Hatchet task.
- Out: OCR of scanned PDFs, sharing between users, cloud storage.

## User experience
_(You left this as a TODO — this is what was built; change it and the scenarios if you want it different.)_
- Left: folder tree ("All documents" + nested folders with document counts). Each folder's ⋯ menu:
  New folder inside, Rename, Delete (confirms; deletes subfolders and their documents).
- Right: the selected folder (kept in the URL as `?folder=…`), an **Upload documents** button and
  drag-and-drop anywhere on the card. Table columns: Name (with the error under it when failed),
  Folder (in "All documents"), Status badge, Chunks, Size, and an actions menu:
  View chunks, Re-index, Move to…, Delete.
- **View chunks** opens a side sheet listing every chunk: heading path, token count, dimensions,
  text, the first numbers of its embedding, and the parent context (parent-document strategy).

## Design notes
- Models: `Folder(owner, parent, name)`, `Document(owner, folder, file, status, error, …)`,
  `Chunk(document, index, text, tokens, embedding vector(N), tsv tsvector)` + HNSW index.
- Upload → `Document(status=queued)` → on commit, `library` pushes Hatchet event
  `document.uploaded`; `rag`'s `index-document` task has `on_events=["document.uploaded"]`
  (library sits below rag, so it must not import it).
- `index-document`: parse → chunk → embed (batched, rate limited per provider key) → upsert;
  emits `document.status` events (new websocket type) and updates React Query caches.
- A batch upload could fan out as child runs of an `index-batch` parent.

# Feature: Library — folders, uploads and indexing

## Background:
* Given I am signed in
* And my provider is the fake LLM provider

## Scenario: AT-0003-01 — Nested folders are private
* Given I have the folder "Projects"
* When I create the folder "Research" inside "Projects"
* Then the folder tree shows "Research" inside "Projects"
* And another user does not see the folder "Research"

## Scenario: AT-0003-02 — Uploads show their indexing status live
* Given I have the folder "Projects"
* When I upload "a.pdf", "b.md" and "c.txt" into "Projects"
* Then each document goes from "Queued" to "Indexing" to "Ready" without reloading the page

## Scenario: AT-0003-03 — Indexed chunks carry embeddings of the configured size
* When I upload "handbook.md" and it finishes indexing
* Then its chunks are stored with 8-dimensional embeddings

## Scenario: AT-0003-04 — A failed embedding can be retried after fixing the key
* Given my provider's API key is "bad-key"
* When I upload "a.md"
* Then "a.md" shows "Failed" with "Incorrect API key provided"
* When I change my provider's API key to "sk-good-key"
* And I re-index "a.md"
* Then "a.md" shows "Ready"

## Scenario: AT-0003-05 — Deleting a document removes its chunks
* Given "a.md" is indexed
* When I delete "a.md"
* Then none of its chunks remain

## Implementation notes
- `apps/library`: `Folder` (unique name per parent, cycle-safe moves), `Document` (status, error,
  chunk_count), services emit Hatchet events `document.uploaded` / `document.reindex_requested`
  and websocket `document.status`. DRF viewsets at `/api/library/folders|documents/`.
- `apps/rag`: `parsing.py` (pypdf, python-docx), `chunking.py` (all five strategies, pure),
  `embedding.py` (batches of 64), `indexing.py` (pipeline; user errors → `IndexingFailed`),
  `tasks.py` (`index-document`: events, 3 per user, retries 2, `NonRetryableException` for user
  errors). `Chunk` has an unsized `vector` + `dimensions`, a generated `tsvector` (GIN), and partial
  HNSW indexes for 384/768/1024/1536. `GET /api/rag/documents/<id>/chunks/`.
- `reindex-user-documents` now re-queues every document (one `index-document` run each).
- Frontend: `features/library/*` (accessible tree/table, uploads, live status via
  `useDocumentStatusSync`, chunks sheet). The demo job moved to System Design → Realtime & jobs;
  spec 0001's AT-0001-06 wording was updated to match.
- Spec wording changes while implementing: added `Given I have the folder "Projects"` to AT-01/02.
- Tests: 5 scenarios here, 42 new pytest tests (chunking edge cases, parsers incl. real PDF/DOCX,
  library permissions/validation, pipeline with a fake client).
- Not done (by scope): OCR, rate limits per provider key (Hatchet rate limits — later), true
  parent/child runs for batch uploads.
