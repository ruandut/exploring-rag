// Steps for specs/0004-settings.feature.md
import assert from "node:assert/strict";

import { Given, Then, When } from "@cucumber/cucumber";

import { SettingsPage } from "../pages/settings-page.ts";
import type { AppWorld } from "../support/world.ts";

const FAKE_CHAT_MODEL = "fake-chat";
const FAKE_EMBED_MODEL = "fake-embed";

Given(
  "I have saved a provider with API key {string}",
  async function (this: AppWorld, apiKey: string) {
    const res = await this.api.put("/api/providers/config/", {
      base_url: this.fakeLlm.baseUrl,
      api_key: apiKey,
      chat_model: FAKE_CHAT_MODEL,
      embedding_model: FAKE_EMBED_MODEL,
      embedding_dimensions: 8,
    });
    assert.equal(res.status, 200, res.text);
  },
);

Given("I open the Settings page", async function (this: AppWorld) {
  await new SettingsPage(this.page).open();
});

Given("I open the Indexing settings", async function (this: AppWorld) {
  const settings = new SettingsPage(this.page);
  await settings.open();
  await settings.openIndexingTab();
});

When(
  "I fill in the provider form for the fake provider with API key {string}",
  async function (this: AppWorld, apiKey: string) {
    await new SettingsPage(this.page).fillProvider({
      baseUrl: this.fakeLlm.baseUrl,
      apiKey,
      chatModel: FAKE_CHAT_MODEL,
      embeddingModel: FAKE_EMBED_MODEL,
    });
  },
);

When("I change the embedding model to {string}", async function (this: AppWorld, model: string) {
  await new SettingsPage(this.page).fillProvider({ embeddingModel: model });
});

When(
  "I set the chunk size to {int} and the overlap to {int}",
  async function (this: AppWorld, size: number, overlap: number) {
    await new SettingsPage(this.page).setChunking(size, overlap);
  },
);

Then("the connection results show {string}", async function (this: AppWorld, text: string) {
  await new SettingsPage(this.page).connectionResults.getByText(text).waitFor();
});

Then(
  "the {string} check fails with {string}",
  async function (this: AppWorld, check: string, message: string) {
    const row = new SettingsPage(this.page).connectionResults.getByRole("group", { name: check });
    await row.getByText(message).waitFor();
    assert.equal(await row.locator(".text-emerald-500").count(), 0, `${check} should have failed`);
  },
);

Then(
  "the API key field says a key ending in {string} is saved",
  async function (this: AppWorld, last4: string) {
    const field = new SettingsPage(this.page).apiKeyField;
    assert.equal(await field.inputValue(), "", "The key must never be pre-filled");
    assert.equal(await field.getAttribute("placeholder"), `•••• ${last4}`);
  },
);

Then(
  "the API rejects chunk size {int} with overlap {int}",
  async function (this: AppWorld, size: number, overlap: number) {
    const res = await this.api.put("/api/rag/indexing-config/", {
      strategy: "recursive",
      chunk_size: size,
      chunk_overlap: overlap,
    });
    assert.equal(res.status, 400);
    assert.deepEqual(res.body.chunk_overlap, ["Overlap must be smaller than the chunk size."]);
  },
);

Then("my saved embedding model is {string}", async function (this: AppWorld, model: string) {
  // Give an in-flight save a moment, then check the server — the source of truth.
  await this.page.waitForLoadState("networkidle");
  const res = await this.api.get("/api/providers/config/");
  assert.equal(res.body.embedding_model, model);
});
