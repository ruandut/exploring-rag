// Setup helpers shared by specs that need indexed documents. These go through the API —
// uploading via the UI is what spec 0003 tests; other specs just need the data in place.
import assert from "node:assert/strict";

import type { AppWorld } from "./world.ts";

export const INDEXING_TIMEOUT = 25_000;

/** Upload a fixture (optionally into a folder) and wait until it's Ready. Returns its id. */
export async function indexDocument(world: AppWorld, name: string, folder?: number): Promise<number> {
  const res = await world.api.upload([name], folder);
  assert.equal(res.status, 201, res.text);
  const id: number = res.body[0].id;
  world.documents[name] = id;
  const deadline = Date.now() + INDEXING_TIMEOUT;
  while (Date.now() < deadline) {
    const doc = (await world.api.get(`/api/library/documents/${id}/`)).body;
    if (doc.status === "ready") return id;
    assert.notEqual(doc.status, "failed", doc.error);
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`${name} did not finish indexing`);
}

export async function createFolder(world: AppWorld, name: string): Promise<number> {
  const res = await world.api.post("/api/library/folders/", { name, parent: null });
  assert.equal(res.status, 201, res.text);
  world.folders[name] = res.body.id;
  return res.body.id;
}

/** Create an agent through the API (setup — the Agents UI is tested by its own scenarios). */
export async function createAgent(
  world: AppWorld,
  name: string,
  extra: Record<string, unknown> = {},
): Promise<number> {
  const existing = (await world.api.get("/api/agents/")).body as { id: number; name: string }[];
  const found = existing.find((a) => a.name === name);
  if (found) return found.id;
  const res = await world.api.post("/api/agents/", { name, system_message: "", ...extra });
  assert.equal(res.status, 201, res.text);
  return res.body.id;
}
