import type { Locator, Page } from "playwright";

import { APP_URL } from "../support/env.ts";
import { ModelPicker } from "./model-picker.ts";

export class ChatPage {
  page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  /** A fresh conversation. */
  async openNew(): Promise<void> {
    await this.page.goto(`${APP_URL}/chat`);
    await this.page.getByRole("textbox", { name: "Message" }).waitFor();
  }

  async selectAgent(name: string): Promise<void> {
    const picker = this.page.getByRole("combobox", { name: "Agent" });
    await picker.click();
    // Options read "<name> <description>", so match the name as a whole-word prefix.
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    await this.page.getByRole("option", { name: new RegExp(`^${escaped}(\\s|$)`) }).click();
    await picker.getByText(name, { exact: true }).waitFor();
  }

  /** Pick what the chat searches (spec 0010); "None" searches nothing. */
  async selectEmbedding(name: string): Promise<void> {
    const picker = this.page.getByRole("combobox", { name: "Embedding" });
    await picker.click();
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    await this.page.getByRole("option", { name: new RegExp(`^${escaped}(\\s|$)`) }).click();
    await picker.getByText(name === "None" ? "No embedding" : name, { exact: true }).waitFor();
  }

  /** Pick which model answers: a model offered by an endpoint ("Default provider" or a
   *  connection's name). */
  async selectModel(model: string, source = "Default provider"): Promise<void> {
    const picker = new ModelPicker(this.page, "Model");
    await picker.open();
    await picker.search(model);
    await picker.option(model, picker.group(source)).click();
    await picker.trigger.getByText(`${source} · ${model}`, { exact: true }).waitFor();
  }

  get settings(): Locator {
    return this.page.getByLabel("Chat settings");
  }

  /** "Agent · Embedding: … · Model" under an answer. */
  answeredWith(answer: Locator): Locator {
    return answer.getByLabel("Answered with");
  }

  async ask(question: string): Promise<void> {
    const box = this.page.getByRole("textbox", { name: "Message" });
    // Wait until the websocket is up (the placeholder says "Connecting…" until then).
    await this.page.getByRole("textbox", { name: "Message" }).and(
      this.page.locator(":not([placeholder='Connecting…'])"),
    ).waitFor();
    await box.fill(question);
    await box.press("Enter");
  }

  /** The newest answer bubble. aria-busy is true while it streams. */
  get latestAnswer(): Locator {
    return this.page.getByRole("article", { name: "Agent answer" }).last();
  }

  async waitForAnswerText(): Promise<void> {
    await this.latestAnswer
      .getByLabel("Answer text")
      .filter({ hasText: /\w{3,}/ })
      .waitFor();
  }

  async waitUntilFinished(timeout = 25_000): Promise<Locator> {
    const answer = this.latestAnswer;
    await answer.and(this.page.locator('[aria-busy="false"]')).waitFor({ timeout });
    return answer;
  }

  /** [document#chunk] tags the answer cites. */
  async citations(): Promise<string[]> {
    return this.latestAnswer.locator("cite").allTextContents();
  }

  /** "document#chunk" for every retrieved chunk card shown with the latest answer. */
  async retrieved(): Promise<{ tag: string; text: string }[]> {
    const items = this.latestAnswer
      .getByRole("list", { name: "Retrieved chunks" })
      .getByRole("listitem");
    const out = [];
    for (const item of await items.all()) {
      out.push({
        tag: (await item.getAttribute("aria-label")) ?? "",
        text: (await item.textContent()) ?? "",
      });
    }
    return out;
  }

  /** The id in ?c= once the server has assigned the conversation one. */
  async openConversationId(): Promise<number> {
    await this.page.waitForURL(/[?&]c=\d+/);
    return Number(new URL(this.page.url()).searchParams.get("c"));
  }

  // --- the conversation list (sidebar) ---------------------------------------------------

  get conversationList(): Locator {
    return this.page.getByRole("navigation", { name: "Conversations" });
  }

  /** Links read "<title> <agent name>", so match the title as a prefix. */
  conversation(title: string): Locator {
    const escaped = title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return this.conversationList.getByRole("link", { name: new RegExp(`^${escaped}`) });
  }

  /** Open /chat (or reload it) and wait until the conversation list has loaded. */
  async loadConversationList(reload = false): Promise<void> {
    const loaded = this.page.waitForResponse(
      (r) => new URL(r.url()).pathname === "/api/chat/conversations/" && r.ok(),
    );
    if (reload) await this.page.reload();
    else await this.page.goto(`${APP_URL}/chat`);
    await loaded;
  }

  async deleteConversation(title: string): Promise<void> {
    await this.conversationList
      .getByRole("button", { name: `Delete "${title}"`, exact: true })
      .click();
  }

  /** The start screen: no ?c=, no messages, the composer ready. */
  async waitForEmptyChat(): Promise<void> {
    await this.page.waitForURL((url) => !url.searchParams.has("c"));
    await this.page.getByRole("textbox", { name: "Message" }).waitFor();
    await this.page.getByRole("article", { name: "Agent answer" }).first().waitFor({
      state: "detached",
    });
  }

  async stop(): Promise<void> {
    await this.page.getByRole("button", { name: "Stop", exact: true }).click();
  }
}
