import type { Locator, Page } from "playwright";

import { APP_URL } from "../support/env.ts";
import { ModelPicker } from "./model-picker.ts";

export type ProviderFields = {
  kind?: "OpenAI-compatible" | "Anthropic" | "Google";
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
    if (fields.kind !== undefined) {
      await this.page.getByRole("combobox", { name: "Provider type" }).click();
      await this.page.getByRole("option", { name: fields.kind, exact: true }).click();
    }
    await set("Base URL", fields.baseUrl);
    await set("API key", fields.apiKey);
    if (fields.chatModel !== undefined) await new ModelPicker(this.page, "Chat model").pick(fields.chatModel);
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
