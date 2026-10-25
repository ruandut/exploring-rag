import type { Locator, Page } from "playwright";

import { APP_URL } from "../support/env.ts";

export type ProviderFields = {
  baseUrl?: string;
  apiKey?: string;
  chatModel?: string;
};

export class SettingsPage {
  page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async open(): Promise<void> {
    await this.page.goto(`${APP_URL}/settings`);
    await this.page.getByLabel("Base URL").waitFor();
  }

  async fillProvider(fields: ProviderFields): Promise<void> {
    const set = async (label: string, value?: string) => {
      if (value !== undefined) await this.page.getByLabel(label, { exact: true }).fill(value);
    };
    await set("Base URL", fields.baseUrl);
    await set("API key", fields.apiKey);
    await set("Chat model", fields.chatModel);
  }

  async press(button: string): Promise<void> {
    await this.page.getByRole("button", { name: button }).click();
  }

  get connectionResults(): Locator {
    return this.page.getByRole("status", { name: "Connection test results" });
  }

  get apiKeyField(): Locator {
    return this.page.getByLabel("API key", { exact: true });
  }

  get confirmDialog(): Locator {
    return this.page.getByRole("alertdialog");
  }
}
