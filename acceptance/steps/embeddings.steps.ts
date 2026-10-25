// Steps for specs/0010-embeddings.feature.md
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { Given, Then, When } from "@cucumber/cucumber";

import { BenchmarksPage } from "../pages/benchmarks-page.ts";
import { ChatPage } from "../pages/chat-page.ts";
import { EmbeddingsPage } from "../pages/embeddings-page.ts";
import { ModelPicker } from "../pages/model-picker.ts";
import { FIXTURES } from "../pages/library-page.ts";
import { createAgent, createFolder } from "../support/documents.ts";
import { APP_URL } from "../support/env.ts";
import {
  chunksIn,
  coveredDocuments,
  EMBEDDING_TIMEOUT,
  ensureDefaultEmbedding,
  ensureEmbedding,
  waitForEmbeddingStatus,
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
    await waitForEmbeddingStatus(this, name, "ready");
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

// --- chat with agent + embedding + model (AT-0010-13..15, 18) --------------------------------

When(
  "I start a chat with the agent {string}, the embedding {string} and the model {string}",
  async function (this: AppWorld, agent: string, embedding: string, model: string) {
    const chat = new ChatPage(this.page);
    await chat.openNew();
    await chat.selectAgent(agent);
    await chat.selectEmbedding(embedding);
    await chat.selectModel(model);
  },
);

When("I send {string}", async function (this: AppWorld, message: string) {
  await new ChatPage(this.page).ask(message);
});

Then(
  "the chat settings show {string}, {string} and {string}",
  async function (this: AppWorld, agent: string, embedding: string, model: string) {
    const settings = new ChatPage(this.page).settings;
    for (const part of [agent, `Embedding: ${embedding}`, model]) {
      await settings.filter({ hasText: part }).waitFor();
    }
  },
);

Given("I had a chat with the embedding {string}", async function (this: AppWorld, embedding: string) {
  await createAgent(this, "Docs helper");
  const chat = new ChatPage(this.page);
  await chat.openNew();
  await chat.selectAgent("Docs helper");
  await chat.selectEmbedding(embedding);
  await chat.ask("What is the refund window?");
  await chat.waitUntilFinished();
  this.conversationId = await chat.openConversationId();
});

When("I switch the chat's embedding to {string}", async function (this: AppWorld, embedding: string) {
  await new ChatPage(this.page).selectEmbedding(embedding);
});

async function usedEmbedding(world: AppWorld, which: "latest" | "previous", name: string) {
  const chat = new ChatPage(world.page);
  await chat.waitUntilFinished();
  const answers = world.page.getByRole("article", { name: "Agent answer" });
  const answer = which === "latest" ? answers.last() : answers.nth((await answers.count()) - 2);
  await chat.answeredWith(answer).filter({ hasText: `Embedding: ${name}` }).waitFor();
}

Then("the latest answer shows it used {string}", async function (this: AppWorld, name: string) {
  await usedEmbedding(this, "latest", name);
});

Then(
  "the previous answer still shows it used {string}",
  async function (this: AppWorld, name: string) {
    await usedEmbedding(this, "previous", name);
  },
);

Then("that chat says {string}", async function (this: AppWorld, text: string) {
  await this.page.goto(`${APP_URL}/chat?c=${this.conversationId}`);
  await new ChatPage(this.page).settings.filter({ hasText: text }).waitFor();
});

// --- benchmarks compare embeddings (AT-0010-17) -------------------------------------------

When(
  "I compare {string} on the agent {string} with the embeddings {string} and {string}",
  async function (this: AppWorld, suite: string, agent: string, first: string, second: string) {
    const page = new BenchmarksPage(this.page);
    assert.ok(this.suites[suite], `No suite called ${suite}`);
    await page.openSuite(this.suites[suite]);
    this.runId = await page.compareEmbeddings(agent, first, second);
    this.comparedEmbeddings = [first, second];
  },
);

Then("each run shows its embedding", async function (this: AppWorld) {
  const runs = this.page.getByRole("region", { name: /^Run / });
  const shown = [];
  for (const run of await runs.all()) {
    shown.push((await run.getByLabel("Run embedding").textContent()) ?? "");
  }
  for (const name of this.comparedEmbeddings ?? []) {
    assert.ok(
      shown.some((s) => s.startsWith(`Embedding: ${name} (`)),
      `No run shows ${name}: ${shown.join(" | ")}`,
    );
  }
});

// --- the model picker (AT-0010-10..12, 16) -------------------------------------------------

const FAKE_ENDPOINTS = { Ollama: "ollamaUrl", bare: "bareUrl", "chat-only": "chatOnlyUrl" } as const;

Given(
  /^I have a connection "([^"]+)" to the fake (Ollama|bare|chat-only) provider$/,
  async function (this: AppWorld, name: string, kind: keyof typeof FAKE_ENDPOINTS) {
    const res = await this.api.post("/api/providers/connections/", {
      name,
      base_url: this.fakeLlm[FAKE_ENDPOINTS[kind]],
    });
    assert.equal(res.status, 201, res.text);
  },
);

Given("the fake Ollama provider has no embedding models", function (this: AppWorld) {
  this.fakeLlm.ollamaNoEmbeddings = true;
});

When(
  "I start a new embedding using the connection {string}",
  async function (this: AppWorld, connection: string) {
    const page = new EmbeddingsPage(this.page);
    await page.open();
    await page.startNew();
    await page.form.getByRole("combobox", { name: "Connection" }).click();
    await this.page.getByRole("option", { name: connection, exact: true }).click();
  },
);

When("I open the {string} picker", async function (this: AppWorld, label: string) {
  this.picker = label;
  this.pickerGroup = undefined;
  await new ModelPicker(this.page, label).open();
});

When(
  "I open the {string} picker for the connection {string}",
  async function (this: AppWorld, label: string, connection: string) {
    this.picker = label;
    this.pickerGroup = connection;
    const picker = new ModelPicker(this.page, label);
    await picker.open();
    await picker.group(connection).waitFor();
  },
);

function openPicker(world: AppWorld) {
  const picker = new ModelPicker(world.page, world.picker!);
  const scope = world.pickerGroup ? picker.group(world.pickerGroup) : picker.list;
  return { picker, scope };
}

Then("the picker offers {string}", async function (this: AppWorld, model: string) {
  const { picker, scope } = openPicker(this);
  await picker.option(model, scope).waitFor();
});

Then("the picker does not offer {string}", async function (this: AppWorld, model: string) {
  const { picker } = openPicker(this);
  // Wait for the list to have loaded (something is offered) before checking an absence.
  await picker.list.getByRole("option").first().waitFor();
  assert.equal(await picker.option(model).count(), 0, `${model} is offered`);
});

Then(
  "the picker offers {string} under {string}",
  async function (this: AppWorld, model: string, group: string) {
    const { picker } = openPicker(this);
    await picker.option(model, picker.group(group)).waitFor();
  },
);

Then("{string} is marked {string}", async function (this: AppWorld, model: string, mark: string) {
  const { picker, scope } = openPicker(this);
  await picker.option(model, scope).filter({ hasText: mark }).waitFor();
});

When(
  "I choose {string} in the {string} picker",
  async function (this: AppWorld, model: string, label: string) {
    await new ModelPicker(this.page, label).option(model).click();
  },
);

When(
  "I search the {string} picker for {string}",
  async function (this: AppWorld, label: string, text: string) {
    await new ModelPicker(this.page, label).search(text);
  },
);

Then(
  "the {string} field shows {string}",
  async function (this: AppWorld, label: string, value: string) {
    const picker = new ModelPicker(this.page, label);
    if (await picker.trigger.count()) {
      await picker.trigger.getByText(value, { exact: true }).waitFor();
      return;
    }
    const field = this.page.getByLabel(label, { exact: true });
    await field.waitFor();
    assert.equal(await field.inputValue(), value);
  },
);

When("I start a new chat", async function (this: AppWorld) {
  await new ChatPage(this.page).openNew();
});
