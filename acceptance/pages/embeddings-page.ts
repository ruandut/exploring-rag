import type { Locator, Page } from "playwright";

import { APP_URL } from "../support/env.ts";

export type EmbeddingFields = {
  name?: string;
  allDocuments?: boolean;
  folders?: string[];
  files?: string[];
  model?: string;
  chunkSize?: number;
};

/** The Embeddings section (spec 0010): a list of embeddings, each with an actions menu. */
export class EmbeddingsPage {
  page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async open(): Promise<void> {
    await this.page.goto(`${APP_URL}/embeddings`);
    await this.page.getByRole("button", { name: "New embedding" }).waitFor();
  }

  card(name: string): Locator {
    return this.page.getByRole("list", { name: "Embeddings" }).getByRole("listitem", {
      name,
      exact: true,
    });
  }

  status(name: string): Locator {
    return this.card(name).getByRole("status", { name: `Status of ${name}` });
  }

  async action(name: string, action: string): Promise<void> {
    await this.card(name)
      .getByRole("button", { name: `Actions for ${name}` })
      .click();
    await this.page.getByRole("menuitem", { name: action }).click();
  }

  async startNew(): Promise<void> {
    await this.page.getByRole("button", { name: "New embedding" }).click();
    await this.form.getByLabel("Name", { exact: true }).waitFor();
  }

  get form(): Locator {
    return this.page.getByRole("dialog");
  }

  async fill(fields: EmbeddingFields): Promise<void> {
    const form = this.form;
    if (fields.name !== undefined) await form.getByLabel("Name", { exact: true }).fill(fields.name);
    if (fields.allDocuments !== undefined) {
      await form.getByLabel("All documents").setChecked(fields.allDocuments);
    }
    for (const folder of fields.folders ?? []) {
      await form
        .getByRole("group", { name: "Folders" })
        .getByLabel(folder, { exact: true })
        .check();
    }
    for (const file of fields.files ?? []) {
      await form.getByRole("group", { name: "Files" }).getByLabel(file, { exact: true }).check();
    }
    if (fields.model !== undefined) {
      await form.getByLabel("Embedding model", { exact: true }).fill(fields.model);
    }
    if (fields.chunkSize !== undefined) {
      await form.getByLabel("Chunk size (tokens)").fill(String(fields.chunkSize));
      // Keep the overlap valid for small chunks.
      const overlap = form.getByLabel("Overlap (tokens)");
      if (Number(await overlap.inputValue()) >= fields.chunkSize) {
        await overlap.fill(String(Math.floor(fields.chunkSize / 8)));
      }
    }
  }

  async setFolder(folder: string, checked: boolean): Promise<void> {
    await this.form
      .getByRole("group", { name: "Folders" })
      .getByLabel(folder, { exact: true })
      .setChecked(checked);
  }

  async setChunking(size: number, overlap: number): Promise<void> {
    await this.form.getByLabel("Chunk size (tokens)").fill(String(size));
    await this.form.getByLabel("Overlap (tokens)").fill(String(overlap));
  }

  async save(label: "Create embedding" | "Save embedding"): Promise<void> {
    await this.form.getByRole("button", { name: label }).click();
  }
}
