// Steps for specs/0009-delete-chat.feature.md
import assert from "node:assert/strict";

import { Given, Then, When } from "@cucumber/cucumber";

import { ChatPage } from "../pages/chat-page.ts";
import { createTestUser, runDjango } from "../support/app.ts";
import { savedRepliesForRun, startConversation } from "../support/chat.ts";
import type { AppWorld } from "../support/world.ts";

const LONG_QUESTION = "Give me a long answer about our refunds.";

When("I delete the conversation {string}", async function (this: AppWorld, title: string) {
  await new ChatPage(this.page).deleteConversation(title);
});

When("I delete that conversation while the agent is answering", async function (this: AppWorld) {
  const chat = new ChatPage(this.page);
  this.conversationId = await chat.openConversationId();
  await chat.waitForAnswerText();
  assert.equal(
    await chat.latestAnswer.getAttribute("aria-busy"),
    "true",
    "The answer already finished — nothing left to cancel",
  );
  await chat.deleteConversation(LONG_QUESTION);
});

Given("I have the conversation {string} open", async function (this: AppWorld, title: string) {
  const chat = new ChatPage(this.page);
  await chat.loadConversationList();
  await chat.conversation(title).click();
  await this.page.getByText(title, { exact: true }).last().waitFor();
});

Then(
  "the conversation {string} is still in my chat list",
  async function (this: AppWorld, title: string) {
    await this.page.getByRole("alertdialog").waitFor({ state: "detached" });
    await new ChatPage(this.page).conversation(title).waitFor();
  },
);

Then(
  "the conversation {string} is not in my chat list",
  async function (this: AppWorld, title: string) {
    await new ChatPage(this.page).conversation(title).waitFor({ state: "detached" });
  },
);

Then("after reloading the page it is still gone", async function (this: AppWorld) {
  const chat = new ChatPage(this.page);
  await chat.loadConversationList(true);
  assert.equal(await chat.conversation("Hello there").count(), 0);
});

Then("its messages can no longer be opened", async function (this: AppWorld) {
  assert.ok(this.conversationId, "No conversation was recorded");
  const res = await this.api.get(`/api/chat/conversations/${this.conversationId}/`);
  assert.equal(res.status, 404, res.text);
});

Given(
  "another user has a conversation {string}",
  async function (this: AppWorld, title: string) {
    this.otherUser = createTestUser("other");
    await this.otherApi.login(this.otherUser);
    this.conversationId = await startConversation(this.otherApi, title);
  },
);

Then("I don't see {string} in my chat list", async function (this: AppWorld, title: string) {
  const chat = new ChatPage(this.page);
  await chat.loadConversationList();
  assert.equal(await chat.conversation(title).count(), 0);
});

Then("deleting it through the API returns 404", async function (this: AppWorld) {
  const res = await this.api.delete(`/api/chat/conversations/${this.conversationId}/`);
  assert.equal(res.status, 404, res.text);
});

Then(
  "the other user still has the conversation {string}",
  async function (this: AppWorld, title: string) {
    const res = await this.otherApi.get(`/api/chat/conversations/${this.conversationId}/`);
    assert.equal(res.status, 200, res.text);
    assert.equal(res.body.title, title);
  },
);

Then("I am in a new, empty chat", async function (this: AppWorld) {
  await new ChatPage(this.page).waitForEmptyChat();
});

Then("the agent run is cancelled", async function (this: AppWorld) {
  const started = this.wsEvents.find(
    (e) => e.type === "agent.started" && e.conversation_id === this.conversationId,
  );
  assert.ok(started, "The run never started");
  const runId = started.run_id as string;
  await waitUntil(() => this.wsEvents.some((e) => e.type === "agent.cancelled" && e.run_id === runId));
  assert.ok(
    !this.wsEvents.some((e) => e.type === "agent.done" && e.run_id === runId),
    "The run finished instead of being cancelled",
  );
  this.cancelledRunId = runId;
});

Then("no reply is saved for the deleted conversation", async function (this: AppWorld) {
  // Give the relay time to reach its finally-block (where it would save the partial reply).
  await new Promise((r) => setTimeout(r, 1_000));
  assert.equal(savedRepliesForRun(runDjango, this.cancelledRunId!), 0);
  const res = await this.api.get(`/api/chat/conversations/${this.conversationId}/`);
  assert.equal(res.status, 404, res.text);
});

async function waitUntil(check: () => boolean, timeoutMs = 10_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (!check()) {
    if (Date.now() > deadline) throw new Error("Timed out");
    await new Promise((r) => setTimeout(r, 50));
  }
}
