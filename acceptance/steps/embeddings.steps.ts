// Steps for specs/0010-embeddings.feature.md
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { Given, Then, When } from "@cucumber/cucumber";

import { EmbeddingsPage } from "../pages/embeddings-page.ts";
import { FIXTURES } from "../pages/library-page.ts";
import { createFolder } from "../support/documents.ts";
import {
  chunksIn,
  coveredDocuments,
  EMBEDDING_TIMEOUT,
  ensureDefaultEmbedding,
  ensureEmbedding,
  waitUntilCovered,
  waitUntilNotCovered,
} from "../support/embeddings.ts";
import type { AppWorld } from "../support/world.ts";

/** What a folder holds when a scenario only names the folder. */
const FOLDER_FIXTURES: Record<string, string> = { Policies: "handbook.md", Support: "faq.md" };

async function folderWithItsDocument(world: AppWorld, folder: string): Promise<number> {
  if (world.folders[folder]) return world.folders[folder];
  const id = await createFolder(world, folder);
  const fixture = FOLDER_FIXTURES[folder];
  if (fixture) await upload(world, fixture, id);
  return id;
}

/** Upload through the API without waiting: what gets indexed depends on the embeddings. */
async function upload(world: AppWorld, name: string, folder?: number) {
  const res = await world.api.upload([name], folder);
  assert.equal(res.status, 201, res.text);
  world.documents[name] = res.body[0].id;
}

async function createInUi(
  world: AppWorld,
  name: string,
  fields: Parameters<EmbeddingsPage["fill"]>[0],
) {
  const page = new EmbeddingsPage(world.page);
  await page.open();
  await page.startNew();
  await page.fill({ name, ...fields });
  await page.save("Create embedding");
  await page.card(name).waitFor();
  world.lastEmbedding = name;
}

async function editInUi(
  world: AppWorld,
  name: string,
  change: (page: EmbeddingsPage) => Promise<void>,
) {
  const page = new EmbeddingsPage(world.page);
  await page.open();
  await page.action(name, "Edit");
  await change(page);
  await page.save("Save embedding");
  world.lastEmbedding = name;
}

// --- setup ------------------------------------------------------------------------------

Given(
  "the embedding {string} covers all my documents",
  async function (this: AppWorld, name: string) {
    if (name === "My documents") await ensureDefaultEmbedding(this);
    else await ensureEmbedding(this, name, { allDocuments: true });
  },
);

Given(
  "I upload {string} to {string}",
  async function (this: AppWorld, name: string, folder: string) {
    await upload(this, name, this.folders[folder] ?? (await createFolder(this, folder)));
  },
);

Given(
  "I have the folder {string} containing {string}",
  async function (this: AppWorld, folder: string, name: string) {
    await upload(this, name, await createFolder(this, folder));
  },
);

Given(
  "the embedding {string} covers the folder {string}",
  async function (this: AppWorld, name: string, folder: string) {
    await ensureEmbedding(this, name, { folders: [await folderWithItsDocument(this, folder)] });
    const fixture = FOLDER_FIXTURES[folder];
    if (fixture) await waitUntilCovered(this, name, fixture);
  },
);

Given(
  "the embedding {string} covers the folders {string} and {string}",
  async function (this: AppWorld, name: string, a: string, b: string) {
    const folders = [await folderWithItsDocument(this, a), await folderWithItsDocument(this, b)];
    await ensureEmbedding(this, name, { folders });
    for (const f of [a, b])
      if (FOLDER_FIXTURES[f]) await waitUntilCovered(this, name, FOLDER_FIXTURES[f]);
  },
);

Given(
  "the embedding {string} covers the folder {string} with the model {string}",
  async function (this: AppWorld, name: string, folder: string, model: string) {
    await ensureEmbedding(this, name, {
      folders: [await folderWithItsDocument(this, folder)],
      model,
    });
    const fixture = FOLDER_FIXTURES[folder];
    if (fixture) await waitUntilCovered(this, name, fixture);
  },
);

// --- creating and editing in the UI ---------------------------------------------------------

When(
  "I create the embedding {string} with the folder {string} and the model {string}",
  async function (this: AppWorld, name: string, folder: string, model: string) {
    await createInUi(this, name, { folders: [folder], model });
  },
);

When(
  "I create the embedding {string} with the file {string} and the model {string}",
  async function (this: AppWorld, name: string, file: string, model: string) {
    await createInUi(this, name, { files: [file], model });
  },
);

When(
  "I create the embedding {string} with all my folders and the model {string}",
  async function (this: AppWorld, name: string, model: string) {
    await createInUi(this, name, { allDocuments: true, model });
  },
);

When(
  "I create the embedding {string} with all my folders, the model {string} and chunk size {int}",
  async function (this: AppWorld, name: string, model: string, size: number) {
    await createInUi(this, name, { allDocuments: true, model, chunkSize: size });
  },
);

When(
  "I add the folder {string} to the embedding {string}",
  async function (this: AppWorld, folder: string, name: string) {
    this.embeddedMark = this.fakeLlm.embedded.length;
    await editInUi(this, name, (page) => page.setFolder(folder, true));
  },
);

When(
  "I remove the folder {string} from the embedding {string}",
  async function (this: AppWorld, folder: string, name: string) {
    await editInUi(this, name, (page) => page.setFolder(folder, false));
  },
);

When(
  "I change the model of {string} to {string}",
  async function (this: AppWorld, name: string, model: string) {
    await editInUi(this, name, (page) => page.fill({ model }));
  },
);

When("I re-index the embedding {string}", async function (this: AppWorld, name: string) {
  const page = new EmbeddingsPage(this.page);
  await page.open();
  this.pageLoads = 0;
  this.wsMark = this.wsEvents.length;
  await page.action(name, "Re-index");
  this.lastEmbedding = name;
});

When("I delete the embedding {string}", async function (this: AppWorld, name: string) {
  const page = new EmbeddingsPage(this.page);
  await page.open();
  await page.action(name, "Delete");
});

Given("I start a new embedding", async function (this: AppWorld) {
  const page = new EmbeddingsPage(this.page);
  await page.open();
  await page.startNew();
});

// --- checks -----------------------------------------------------------------------------

Then(
  "the embedding {string} shows {string}",
  async function (this: AppWorld, name: string, status: string) {
    const page = new EmbeddingsPage(this.page);
    if (!this.page.url().endsWith("/embeddings")) await page.open();
    const badge = page.status(name).getByText(status, { exact: true });
    if (status === "Indexing" && this.wsMark !== undefined) {
      // The fake model is fast: the badge may flip back before we look. The live event that
      // put it there is just as good evidence.
      const seen = () =>
        this.wsEvents
          .slice(this.wsMark)
          .some((e) => e.type === "embedding.status" && e.status === "indexing");
      await Promise.any([
        badge.waitFor({ timeout: EMBEDDING_TIMEOUT }),
        (async () => {
          const deadline = Date.now() + EMBEDDING_TIMEOUT;
          while (!seen() && Date.now() < deadline) await new Promise((r) => setTimeout(r, 50));
          assert.ok(seen(), `${name} never showed Indexing`);
        })(),
      ]);
      return;
    }
    await badge.waitFor({ timeout: EMBEDDING_TIMEOUT });
  },
);

Then(
  "then shows {string} without reloading the page",
  async function (this: AppWorld, status: string) {
    const name = this.lastEmbedding!;
    await new EmbeddingsPage(this.page)
      .status(name)
      .getByText(status, { exact: true })
      .waitFor({ timeout: EMBEDDING_TIMEOUT });
    assert.equal(this.pageLoads, 0, "The page reloaded");
  },
);

Then(
  "the embedding {string} covers {string}",
  async function (this: AppWorld, name: string, document: string) {
    await waitUntilCovered(this, name, document);
  },
);

Then(
  "the embedding {string} does not cover {string}",
  async function (this: AppWorld, name: string, document: string) {
    await waitUntilNotCovered(this, name, document);
  },
);

Then(
  "the chunks of {string} in {string} have {int}-dimensional embeddings",
  async function (this: AppWorld, document: string, embedding: string, dims: number) {
    const deadline = Date.now() + EMBEDDING_TIMEOUT;
    let chunks = await chunksIn(this, embedding, document);
    // After a re-index the old chunks are gone first; wait for the new ones.
    while (
      !(chunks.length && chunks.every((c) => c.dimensions === dims)) &&
      Date.now() < deadline
    ) {
      await new Promise((r) => setTimeout(r, 250));
      chunks = await chunksIn(this, embedding, document);
    }
    assert.ok(chunks.length > 0, "No chunks");
    assert.ok(
      chunks.every((c) => c.dimensions === dims && c.embedding_name === embedding),
      `Got ${chunks.map((c) => c.dimensions).join(", ")}`,
    );
  },
);

Then(
  "{string} has more chunks than {string}",
  async function (this: AppWorld, fine: string, coarse: string) {
    const count = async (name: string) => {
      const docs = await coveredDocuments(this, name);
      for (const d of docs) await waitUntilCovered(this, name, d.name);
      return (await coveredDocuments(this, name)).reduce((n, d) => n + d.chunk_count, 0);
    };
    const [a, b] = [await count(fine), await count(coarse)];
    assert.ok(a > b, `${fine} has ${a} chunks, ${coarse} has ${b}`);
  },
);

Then("only {string} was sent to be embedded", async function (this: AppWorld, document: string) {
  const text = readFileSync(`${FIXTURES}${document}`, "utf8").replace(/\s+/g, " ");
  const sent = this.fakeLlm.embedded.slice(this.embeddedMark ?? 0);
  assert.ok(sent.length > 0, "Nothing was embedded");
  for (const input of sent) {
    // Each input is "<heading path>\n\n<chunk text>"; the chunk text comes from the file.
    const body = input
      .split("\n\n")
      .at(-1)!
      .replace(/\s+/g, " ")
      .replace(/^#+\s*/, "");
    assert.ok(text.includes(body.slice(0, 40)), `Embedded text not from ${document}: ${body}`);
  }
});

Then("{string} is still in my library", async function (this: AppWorld, name: string) {
  const docs = (await this.api.get("/api/library/documents/")).body as { name: string }[];
  assert.ok(
    docs.some((d) => d.name === name),
    `${name} is gone from the library`,
  );
});
