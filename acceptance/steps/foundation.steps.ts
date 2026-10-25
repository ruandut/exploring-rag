// Steps for specs/0001-foundation.feature.md
import assert from "node:assert/strict";

import { type DataTable, Given, Then, When } from "@cucumber/cucumber";

import { AppShell } from "../pages/app-shell.ts";
import { ChatPage } from "../pages/chat-page.ts";
import { LoginPage } from "../pages/login-page.ts";
import { ApiClient, createTestUser, runDjango } from "../support/app.ts";
import { APP_URL } from "../support/env.ts";
import { SocketClient } from "../support/socket.ts";
import type { AppWorld } from "../support/world.ts";

// --- sign-in ---------------------------------------------------------------------------

Given("I go to the sign-in page", async function (this: AppWorld) {
  await this.page.goto(`${APP_URL}/login`);
});

When("I sign in with my username and password", async function (this: AppWorld) {
  await new LoginPage(this.page).signIn(this.user);
});

When(
  "I sign in with my username and the password {string}",
  async function (this: AppWorld, password: string) {
    await this.page.getByLabel("Username").fill(this.user.username);
    await this.page.getByLabel("Password").fill(password);
    await this.page.getByRole("button", { name: "Sign in" }).click();
  },
);

When("I visit {string} without signing in", async function (this: AppWorld, path: string) {
  await this.page.goto(`${APP_URL}${path}`);
});

Then("I am on the sign-in page", async function (this: AppWorld) {
  await this.page.waitForURL("**/login");
  await this.page.getByRole("button", { name: "Sign in" }).waitFor();
});

Then("I am on the {string} page", async function (this: AppWorld, title: string) {
  await this.page.getByRole("heading", { level: 1, name: title }).waitFor();
});

Then("the user menu shows {string}", async function (this: AppWorld, text: string) {
  await new AppShell(this.page).userMenu.getByText(text).waitFor();
});

Then(
  "the API answers {int} for {string} without a token",
  async function (this: AppWorld, status: number, path: string) {
    assert.equal((await new ApiClient().get(path)).status, status);
  },
);

When("I exchange my refresh token", async function (this: AppWorld) {
  this.lastApiResponse = await this.api.post("/api/auth/token/refresh/", {
    refresh: this.api.refreshToken,
  });
});

Then(
  "I get a new access token that works for {string}",
  async function (this: AppWorld, path: string) {
    assert.equal(this.lastApiResponse?.status, 200);
    const fresh = new ApiClient();
    fresh.accessToken = this.lastApiResponse!.body.access;
    const me = await fresh.get(path);
    assert.equal(me.status, 200);
    assert.equal(me.body.username, this.user.username);
  },
);

// --- websocket -------------------------------------------------------------------------

When("I open a websocket and authenticate with my token", async function (this: AppWorld) {
  this.sockets.mine = await SocketClient.open();
  this.sockets.mine.send({ type: "auth", token: this.api.accessToken });
});

When(
  "I open a websocket and authenticate with the token {string}",
  async function (this: AppWorld, token: string) {
    this.sockets.that = await SocketClient.open();
    this.sockets.that.send({ type: "auth", token });
  },
);

Then("my websocket receives {string}", async function (this: AppWorld, type: string) {
  await this.sockets.mine.waitFor((e) => e.type === type);
});

Then(
  "that websocket receives {string} and is closed with code {int}",
  async function (this: AppWorld, type: string, code: number) {
    await this.sockets.that.waitFor((e) => e.type === type);
    assert.equal(await this.sockets.that.waitForClose(), code);
  },
);

Given("my websocket is connected", async function (this: AppWorld) {
  this.sockets.mine = await SocketClient.open();
  this.sockets.mine.send({ type: "auth", token: this.api.accessToken });
  await this.sockets.mine.waitFor((e) => e.type === "auth.ok");
});

Given("another user's websocket is connected", async function (this: AppWorld) {
  this.otherUser = createTestUser("other");
  await this.otherApi.login(this.otherUser);
  this.sockets.other = await SocketClient.open();
  this.sockets.other.send({ type: "auth", token: this.otherApi.accessToken });
  await this.sockets.other.waitFor((e) => e.type === "auth.ok");
});

When(
  "I start the demo indexing job with {int} steps",
  async function (this: AppWorld, steps: number) {
    const res = await this.api.post("/api/jobs/demo-index/", { steps });
    assert.equal(res.status, 202, res.text);
  },
);

Then(
  "my websocket receives {int} {string} events and then {string}",
  async function (this: AppWorld, count: number, progress: string, done: string) {
    await this.sockets.mine.waitFor((e) => e.type === done);
    const types = this.sockets.mine.events.map((e) => e.type);
    assert.equal(types.filter((t) => t === progress).length, count);
    assert.ok(types.lastIndexOf(progress) < types.indexOf(done), "progress must come first");
  },
);

Then(
  "the other user's websocket receives no {string} events",
  async function (this: AppWorld, type: string) {
    assert.equal(this.sockets.other.events.filter((e) => e.type === type).length, 0);
  },
);

// --- pages -----------------------------------------------------------------------------

Given("I open the {string} page", async function (this: AppWorld, label: string) {
  await new AppShell(this.page).navItem(label).click();
  await this.page.getByRole("heading", { level: 1, name: label }).waitFor();
});

When("I open the {string} page from the drawer", async function (this: AppWorld, label: string) {
  await new AppShell(this.page).navItem(label).click();
  await this.page.getByRole("heading", { level: 1, name: label }).waitFor();
});

// --- chat ------------------------------------------------------------------------------

When("I ask the agent {string}", async function (this: AppWorld, question: string) {
  await new ChatPage(this.page).ask(question);
});

When("I stop the agent while it is answering", async function (this: AppWorld) {
  const chat = new ChatPage(this.page);
  await chat.waitForAnswerText(); // tokens are streaming
  await chat.stop();
});

Then("I see the agent's thinking", async function (this: AppWorld) {
  await new ChatPage(this.page).latestAnswer.getByText("I should search their documents").waitFor();
});

Then("I see the tool call {string}", async function (this: AppWorld, tool: string) {
  await new ChatPage(this.page).latestAnswer.getByText(`${tool}(`).waitFor();
});

Then("I see {int} retrieved chunks", async function (this: AppWorld, count: number) {
  const list = new ChatPage(this.page).latestAnswer.getByRole("list", { name: "Retrieved chunks" });
  await list.waitFor();
  assert.equal(await list.getByRole("listitem").count(), count);
});

Then("the agent finishes its answer", async function (this: AppWorld) {
  const answer = new ChatPage(this.page).latestAnswer;
  await answer.and(this.page.locator('[aria-busy="false"]')).waitFor({ timeout: 20_000 });
  await answer.getByText("this stream comes from your configured LLM").waitFor();
  assert.equal(await answer.getByText("Stopped.").count(), 0);
});

// --- drawer ----------------------------------------------------------------------------

Then("the navigation drawer lists:", async function (this: AppWorld, table: DataTable) {
  const shell = new AppShell(this.page);
  for (const [label] of table.raw()) {
    await shell.navItem(label).waitFor();
  }
});

Then("{string} is highlighted in the drawer", async function (this: AppWorld, label: string) {
  assert.equal(await new AppShell(this.page).navItem(label).getAttribute("data-active"), "true");
});

When("I collapse the drawer", async function (this: AppWorld) {
  await new AppShell(this.page).collapse();
});

Then("the drawer only shows icons", async function (this: AppWorld) {
  const shell = new AppShell(this.page);
  await this.page.locator('[data-slot="sidebar"][data-state="collapsed"]').waitFor();
  await this.page.waitForTimeout(300); // width transition
  const box = await shell.navItem("Library").boundingBox();
  assert.ok(box && box.width < 60, `Collapsed item should be icon-sized, was ${box?.width}px`);
});

// --- Hatchet ---------------------------------------------------------------------------

Then(
  "Hatchet has the cron {string} for {string}",
  async function (this: AppWorld, cron: string, task: string) {
    const out = runDjango(
      "from apps.jobs.hatchet import get_hatchet\n" +
        "print('\\n'.join(f'{c.workflow_name}|{c.cron}' for c in get_hatchet().cron.list().rows or []))",
    );
    assert.ok(out.split("\n").includes(`${task}|${cron}`), `Crons found:\n${out}`);
  },
);
