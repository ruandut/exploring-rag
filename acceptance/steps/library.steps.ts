// Steps for specs/0003-library.feature.md
import assert from "node:assert/strict";

import { Given, Then, When } from "@cucumber/cucumber";

import { LibraryPage } from "../pages/library-page.ts";
import { runDjango } from "../support/app.ts";
import { createFolder, INDEXING_TIMEOUT, indexDocument } from "../support/documents.ts";
import type { AppWorld } from "../support/world.ts";

async function saveFakeProvider(world: AppWorld, apiKey: string) {
  const res = await world.api.put("/api/providers/config/", {
    base_url: world.fakeLlm.baseUrl,
    api_key: apiKey,
    chat_model: "fake-chat",
  });
  assert.equal(res.status, 200, res.text);
}

async function waitForStatus(world: AppWorld, name: string, status: string) {
  await new LibraryPage(world.page)
    .row(name)
    .getByText(status, { exact: true })
    .waitFor({ timeout: INDEXING_TIMEOUT });
}

// --- setup ------------------------------------------------------------------------------

Given("my provider is the fake LLM provider", async function (this: AppWorld) {
  await saveFakeProvider(this, "sk-good-key");
});

Given("my provider's API key is {string}", async function (this: AppWorld, key: string) {
  await saveFakeProvider(this, key);
});

When("I change my provider's API key to {string}", async function (this: AppWorld, key: string) {
  await saveFakeProvider(this, key);
});

Given("I have the folder {string}", async function (this: AppWorld, name: string) {
  await createFolder(this, name);
});

Given("{string} is indexed", async function (this: AppWorld, name: string) {
  await indexDocument(this, name);
});

// --- folders ----------------------------------------------------------------------------

When(
  "I create the folder {string} inside {string}",
  async function (this: AppWorld, name: string, parent: string) {
    const library = new LibraryPage(this.page);
    await library.open();
    await library.createFolderInside(parent, name);
  },
);

Then(
  "the folder tree shows {string} inside {string}",
  async function (this: AppWorld, child: string, parent: string) {
    await new LibraryPage(this.page)
      .folder(parent)
      .getByRole("group")
      .getByRole("treeitem", { name: child, exact: true })
      .waitFor();
  },
);

Then("another user does not see the folder {string}", async function (this: AppWorld, name: string) {
  const { createTestUser, ApiClient } = await import("../support/app.ts");
  const other = new ApiClient();
  await other.login(createTestUser("other"));
  const folders = (await other.get("/api/library/folders/")).body as { name: string }[];
  assert.equal(folders.filter((f) => f.name === name).length, 0);
  // And not via the documents list of my folders either.
  const mine = (await this.api.get("/api/library/folders/")).body as { id: number; name: string }[];
  const target = mine.find((f) => f.name === name);
  assert.ok(target, `${name} should exist for me`);
  const res = await other.get(`/api/library/documents/?folder=${target.id}`);
  assert.deepEqual(res.body, []);
});

// --- uploads ----------------------------------------------------------------------------

When(
  "I upload {string}, {string} and {string} into {string}",
  async function (this: AppWorld, a: string, b: string, c: string, folder: string) {
    const library = new LibraryPage(this.page);
    await library.open(this.folders[folder]);
    this.pageLoads = 0;
    for (const doc of await library.upload([a, b, c])) {
      assert.equal(doc.status, "queued");
      this.documents[doc.name] = doc.id;
    }
  },
);

When("I upload {string}", async function (this: AppWorld, name: string) {
  const library = new LibraryPage(this.page);
  await library.open();
  const [doc] = await library.upload([name]);
  this.documents[doc.name] = doc.id;
});

When("I upload {string} and it finishes indexing", async function (this: AppWorld, name: string) {
  const library = new LibraryPage(this.page);
  await library.open();
  const [doc] = await library.upload([name]);
  this.documents[doc.name] = doc.id;
  await waitForStatus(this, name, "Ready");
});

Then(
  "each document goes from {string} to {string} to {string} without reloading the page",
  async function (this: AppWorld, first: string, second: string, last: string) {
    const statuses = [first, second, last].map((s) => s.toLowerCase());
    for (const name of Object.keys(this.documents)) {
      await waitForStatus(this, name, last);
    }
    assert.equal(this.pageLoads, 0, "The page reloaded");
    for (const [name, id] of Object.entries(this.documents)) {
      // The first status came back from the upload itself; the rest arrived over the websocket.
      const seen = this.wsEvents
        .filter((e) => e.type === "document.status" && e.document_id === id)
        .map((e) => e.status as string);
      assert.deepEqual(
        [statuses[0], ...seen.filter((s, i) => s !== seen[i - 1])].slice(-3),
        statuses,
        `${name} went through ${seen.join(" → ")}`,
      );
    }
  },
);

Then(
  "its chunks are stored with {int}-dimensional embeddings",
  async function (this: AppWorld, dims: number) {
    const [name, id] = Object.entries(this.documents).at(-1)!;
    const library = new LibraryPage(this.page);
    await library.documentAction(name, "View chunks");
    const sheet = library.chunksSheet;
    await sheet.getByText(`${dims} dimensions · fake-embed`).waitFor();
    const items = sheet.getByRole("list", { name: "Chunks" }).getByRole("listitem");
    assert.ok((await items.count()) > 0, "No chunks shown");
    const chunks = (await this.api.get(`/api/rag/documents/${id}/chunks/`)).body as {
      dimensions: number;
    }[];
    assert.ok(chunks.length > 0);
    assert.ok(chunks.every((c) => c.dimensions === dims));
  },
);

// --- status, re-index, delete -------------------------------------------------------------

Then(
  "{string} shows {string} with {string}",
  async function (this: AppWorld, name: string, status: string, message: string) {
    await waitForStatus(this, name, status);
    await new LibraryPage(this.page).row(name).getByText(message).waitFor();
  },
);

Then("{string} shows {string}", async function (this: AppWorld, name: string, status: string) {
  await waitForStatus(this, name, status);
});

When("I re-index {string}", async function (this: AppWorld, name: string) {
  await new LibraryPage(this.page).documentAction(name, "Re-index");
});

When("I delete {string}", async function (this: AppWorld, name: string) {
  const library = new LibraryPage(this.page);
  await library.open();
  await library.documentAction(name, "Delete");
  await this.page.getByRole("alertdialog").getByRole("button", { name: "Delete" }).click();
  await library.row(name).waitFor({ state: "detached" });
});

Then("none of its chunks remain", async function (this: AppWorld) {
  const id = Object.values(this.documents).at(-1)!;
  assert.equal((await this.api.get(`/api/rag/documents/${id}/chunks/`)).status, 404);
  const count = runDjango(
    `from apps.rag.models import Chunk; print(Chunk.objects.filter(document_id=${id}).count())`,
  );
  assert.equal(count, "0");
});
