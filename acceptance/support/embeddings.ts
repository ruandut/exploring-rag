// Setup + checks for embeddings (spec 0010) through the API. Creating an embedding in the UI is
// what AT-0010-01 tests; other scenarios just need one in place.
import assert from "node:assert/strict";

import { FAKE_EMBEDDING_DIMENSIONS } from "./fake-llm.ts";
import type { AppWorld } from "./world.ts";

export const EMBEDDING_TIMEOUT = 25_000;

export type EmbeddingRow = {
  id: number;
  name: string;
  model: string;
  status: "indexing" | "ready" | "failed";
  error: string;
  folders: number[];
};

export type CoveredDocument = {
  document_id: number;
  name: string;
  status: string;
  chunk_count: number;
};

export type EmbeddingSetup = {
  model?: string;
  allDocuments?: boolean;
  folders?: number[];
  documents?: number[];
  strategy?: string;
  chunkSize?: number;
  chunkOverlap?: number;
};

export async function findEmbedding(
  world: AppWorld,
  name: string,
): Promise<EmbeddingRow | undefined> {
  const list = (await world.api.get("/api/rag/embeddings/")).body as EmbeddingRow[];
  return list.find((e) => e.name === name);
}

export async function embeddingId(world: AppWorld, name: string): Promise<number> {
  const found = await findEmbedding(world, name);
  assert.ok(found, `No embedding called ${name}`);
  return found.id;
}

/** Create the embedding, or update it (confirming any re-index) if it already exists. */
export async function ensureEmbedding(world: AppWorld, name: string, setup: EmbeddingSetup) {
  const body = {
    name,
    model: setup.model ?? "fake-embed",
    dimensions: null,
    all_documents: setup.allDocuments ?? false,
    folders: setup.folders ?? [],
    documents: setup.documents ?? [],
    strategy: setup.strategy ?? "recursive",
    chunk_size: setup.chunkSize ?? 512,
    chunk_overlap: setup.chunkOverlap ?? 64,
  };
  const existing = await findEmbedding(world, name);
  const res = existing
    ? await world.api.request("PATCH", `/api/rag/embeddings/${existing.id}/`, {
        ...body,
        confirm_reindex: true,
      })
    : await world.api.post("/api/rag/embeddings/", body);
  assert.ok([200, 201].includes(res.status), res.text);
  return res.body as EmbeddingRow;
}

/** The embedding every "… is indexed" setup step relies on: all documents, the fake model. */
export async function ensureDefaultEmbedding(world: AppWorld, setup: EmbeddingSetup = {}) {
  if (!setup.strategy && (await findEmbedding(world, "My documents"))) return;
  await ensureEmbedding(world, "My documents", { allDocuments: true, ...setup });
}

export async function coveredDocuments(world: AppWorld, name: string): Promise<CoveredDocument[]> {
  const id = await embeddingId(world, name);
  return (await world.api.get(`/api/rag/embeddings/${id}/documents/`)).body as CoveredDocument[];
}

/** Wait until the embedding has finished indexing the document. */
export async function waitUntilCovered(world: AppWorld, embedding: string, document: string) {
  const deadline = Date.now() + EMBEDDING_TIMEOUT;
  let last: CoveredDocument | undefined;
  while (Date.now() < deadline) {
    last = (await coveredDocuments(world, embedding)).find((d) => d.name === document);
    if (last?.status === "ready") return last;
    assert.notEqual(last?.status, "failed", `${document} failed in ${embedding}`);
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`${embedding} never finished indexing ${document} (last: ${last?.status})`);
}

/** Wait until the embedding no longer covers the document. */
export async function waitUntilNotCovered(world: AppWorld, embedding: string, document: string) {
  const deadline = Date.now() + EMBEDDING_TIMEOUT;
  while (Date.now() < deadline) {
    if (!(await coveredDocuments(world, embedding)).some((d) => d.name === document)) return;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`${embedding} still covers ${document}`);
}

export async function waitForEmbeddingStatus(world: AppWorld, name: string, status: string) {
  const deadline = Date.now() + EMBEDDING_TIMEOUT;
  while (Date.now() < deadline) {
    const found = await findEmbedding(world, name);
    if (found?.status === status) return found;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`${name} never became ${status}`);
}

/** The chunks of one document inside one embedding. */
export async function chunksIn(world: AppWorld, embedding: string, document: string) {
  await waitUntilCovered(world, embedding, document);
  const id = await embeddingId(world, embedding);
  const res = await world.api.get(
    `/api/rag/documents/${world.documents[document]}/chunks/?embedding=${id}`,
  );
  assert.equal(res.status, 200, res.text);
  return res.body as { dimensions: number; embedding_name: string }[];
}

export { FAKE_EMBEDDING_DIMENSIONS };
