import type { Locator, Page } from "playwright";

import { APP_URL } from "../support/env.ts";

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

  async stop(): Promise<void> {
    await this.page.getByRole("button", { name: "Stop" }).click();
  }
}
