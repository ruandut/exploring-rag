// Steps for specs/0004-settings.feature.md
import assert from "node:assert/strict";

import { Given, Then, When } from "@cucumber/cucumber";

import { EmbeddingsPage } from "../pages/embeddings-page.ts";
import { SettingsPage } from "../pages/settings-page.ts";
import type { AppWorld } from "../support/world.ts";

const FAKE_CHAT_MODEL = "fake-chat";

Given(
  "I have saved a provider with API key {string}",
  async function (this: AppWorld, apiKey: string) {
    const res = await this.api.put("/api/providers/config/", {
      base_url: this.fakeLlm.baseUrl,
      api_key: apiKey,
      chat_model: FAKE_CHAT_MODEL,
    });
    assert.equal(res.status, 200, res.text);
  },
);

Given("I open the Settings page", async function (this: AppWorld) {
  await new SettingsPage(this.page).open();
});

When(
  "I fill in the provider form for the fake provider with API key {string}",
  async function (this: AppWorld, apiKey: string) {
    await new SettingsPage(this.page).fillProvider({
      baseUrl: this.fakeLlm.baseUrl,
      apiKey,
      chatModel: FAKE_CHAT_MODEL,
    });
  },
);

// Chunking is set per embedding since spec 0010.
When(
  "I set the chunk size to {int} and the overlap to {int}",
  async function (this: AppWorld, size: number, overlap: number) {
    await new EmbeddingsPage(this.page).setChunking(size, overlap);
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
    const res = await this.api.post("/api/rag/embeddings/", {
      name: "Too much overlap",
      model: "fake-embed",
      all_documents: true,
      strategy: "recursive",
      chunk_size: size,
      chunk_overlap: overlap,
    });
    assert.equal(res.status, 400);
    assert.deepEqual(res.body.chunk_overlap, ["Overlap must be smaller than the chunk size."]);
  },
);
