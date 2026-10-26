// Steps for specs/0008-anthropic-and-google.feature.md — Claude and Gemini through their own
// APIs, against the fake server's Anthropic and Gemini dialects (no real provider is called).
import assert from "node:assert/strict";

import { Given, Then, When } from "@cucumber/cucumber";

import { BenchmarksPage } from "../pages/benchmarks-page.ts";
import { ChatPage } from "../pages/chat-page.ts";
import { EmbeddingsPage } from "../pages/embeddings-page.ts";
import { SettingsPage } from "../pages/settings-page.ts";
import { createAgent } from "../support/documents.ts";
import { ensureEmbedding, waitUntilCovered } from "../support/embeddings.ts";
import type { AppWorld } from "../support/world.ts";

type Kind = "Anthropic" | "Google";
const KIND = { Anthropic: "anthropic", Google: "google" } as const;
const urlOf = (world: AppWorld, kind: Kind) =>
  kind === "Anthropic" ? world.fakeLlm.anthropicUrl : world.fakeLlm.googleUrl;

async function connectionId(world: AppWorld, name: string): Promise<number> {
  const conns = (await world.api.get("/api/providers/connections/")).body as { id: number; name: string }[];
  const found = conns.find((c) => c.name === name);
  assert.ok(found, `No connection "${name}"`);
  return found.id;
}

// --- providers and connections ----------------------------------------------------------

When(
  "I set my chat provider to the fake Anthropic provider with the API key {string} and the model {string}",
  async function (this: AppWorld, apiKey: string, model: string) {
    const settings = new SettingsPage(this.page);
    await settings.open();
    await settings.fillProvider({ kind: "Anthropic", baseUrl: this.fakeLlm.anthropicUrl, apiKey, chatModel: model });
  },
);

Given("my chat provider is the fake Anthropic provider", async function (this: AppWorld) {
  const res = await this.api.put("/api/providers/config/", {
    kind: "anthropic",
    base_url: this.fakeLlm.anthropicUrl,
    api_key: "sk-ant-good",
    chat_model: "claude-opus-5-5",
  });
  assert.equal(res.status, 200, res.text);
});

Given(
  /^I have an? "(Anthropic|Google)" connection "([^"]+)" to the fake (?:Anthropic|Google) provider$/,
  async function (this: AppWorld, kind: Kind, name: string) {
    const res = await this.api.post("/api/providers/connections/", {
      name,
      kind: KIND[kind],
      base_url: urlOf(this, kind),
      api_key: "sk-good",
    });
    assert.equal(res.status, 201, res.text);
  },
);

When("I list the models of {string}", async function (this: AppWorld, name: string) {
  const settings = new SettingsPage(this.page);
  await settings.open();
  await this.page.getByRole("tab", { name: "Connections" }).click();
  await this.page.getByRole("listitem", { name, exact: true }).getByRole("button", { name: "List models" }).click();
});

// --- embeddings -----------------------------------------------------------------------------

When(
  "I create the embedding {string} with the folder {string} and the model {string} from {string}",
  async function (this: AppWorld, name: string, folder: string, model: string, connection: string) {
    const page = new EmbeddingsPage(this.page);
    await page.open();
    await page.startNew();
    await page.form.getByRole("combobox", { name: "Connection" }).click();
    await this.page.getByRole("option", { name: connection, exact: true }).click();
    await page.fill({ name, folders: [folder], model });
    await page.save("Create embedding");
    await page.card(name).waitFor();
  },
);

Then("{string} is not offered as an embedding connection", async function (this: AppWorld, name: string) {
  const form = new EmbeddingsPage(this.page).form;
  await form.getByRole("combobox", { name: "Connection" }).click();
  const options = this.page.getByRole("option");
  await options.first().waitFor();
  assert.equal(await options.filter({ hasText: name }).count(), 0, `${name} is offered`);
  await this.page.keyboard.press("Escape");
});

// The chat's embedding: an OpenAI-compatible fake embedder, so it works whatever the chat
// provider is (Anthropic can't embed).
Given("the embedding {string} is built from {string}", async function (this: AppWorld, name: string, document: string) {
  const upload = await this.api.upload([document]);
  assert.equal(upload.status, 201, upload.text);
  this.documents[document] = upload.body[0].id;
  const conn = await this.api.post("/api/providers/connections/", { name: "Fake embedder", base_url: this.fakeLlm.baseUrl });
  assert.ok([201, 400].includes(conn.status), conn.text); // 400: already there
  const embedder = await connectionId(this, "Fake embedder");
  await ensureEmbedding(this, name, { documents: [upload.body[0].id], connection: embedder });
  await waitUntilCovered(this, name, document);
});

// --- chat -------------------------------------------------------------------------------------

When(
  "I start a chat with the agent {string}, the embedding {string} and the model {string} from {string}",
  async function (this: AppWorld, agent: string, embedding: string, model: string, source: string) {
    await createAgent(this, agent);
    const chat = new ChatPage(this.page);
    await chat.openNew();
    await chat.selectAgent(agent);
    await chat.selectEmbedding(embedding);
    await chat.selectModel(model, source);
  },
);

When(
  "I start a chat with the agent {string}, no embedding and the model {string}",
  async function (this: AppWorld, agent: string, model: string) {
    await createAgent(this, agent);
    const chat = new ChatPage(this.page);
    await chat.openNew();
    await chat.selectAgent(agent);
    await chat.selectEmbedding("None");
    await chat.selectModel(model);
  },
);

Then("the latest answer shows {string}", async function (this: AppWorld, text: string) {
  const answer = await new ChatPage(this.page).waitUntilFinished();
  await answer.getByText(text).waitFor();
});

Then("the latest answer does not show {string}", async function (this: AppWorld, text: string) {
  const answer = await new ChatPage(this.page).waitUntilFinished();
  assert.equal(await answer.getByText(text).count(), 0, `The answer still shows "${text}"`);
});

// --- benchmarks -------------------------------------------------------------------------------

When(
  "I run {string} against the agent {string} with the embedding {string}",
  async function (this: AppWorld, suite: string, agent: string, embedding: string) {
    const page = new BenchmarksPage(this.page);
    assert.ok(this.suites[suite], `No suite called ${suite}`);
    await page.openSuite(this.suites[suite]);
    this.runId = await page.run(agent, undefined, undefined, embedding);
    this.pageLoads = 0;
  },
);
