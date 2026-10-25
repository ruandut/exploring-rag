import type { Locator, Page } from "playwright";

import { APP_URL } from "../support/env.ts";

export const FIXTURES = new URL("../fixtures/", import.meta.url).pathname;

export class LibraryPage {
  page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async open(folderId?: number): Promise<void> {
    await this.page.goto(`${APP_URL}/library${folderId ? `?folder=${folderId}` : ""}`);
    await this.tree.waitFor();
  }

  get tree(): Locator {
    return this.page.getByRole("tree", { name: "Folders" });
  }

  folder(name: string): Locator {
    return this.tree.getByRole("treeitem", { name, exact: true });
  }

  async createFolderInside(parent: string, name: string): Promise<void> {
    await this.folder(parent).getByRole("button", { name: `Folder actions for ${parent}` }).first().click();
    await this.page.getByRole("menuitem", { name: "New folder inside" }).click();
    await this.page.getByLabel("Folder name").fill(name);
    await this.page.getByRole("button", { name: "Create folder" }).click();
    await this.page.getByRole("dialog").waitFor({ state: "detached" });
  }

  /** Uploads through the file picker; returns the created documents (id + name). */
  async upload(fileNames: string[]): Promise<{ id: number; name: string; status: string }[]> {
    const response = this.page.waitForResponse(
      (r) => r.url().includes("/api/library/documents/") && r.request().method() === "POST",
    );
    await this.page
      .getByLabel("Choose documents to upload")
      .setInputFiles(fileNames.map((f) => `${FIXTURES}${f}`));
    return (await response).json();
  }

  row(documentName: string): Locator {
    return this.page.getByRole("table", { name: "Documents" }).getByRole("row", { name: documentName });
  }

  async documentAction(documentName: string, action: string): Promise<void> {
    await this.page.getByRole("button", { name: `Actions for ${documentName}` }).click();
    await this.page.getByRole("menuitem", { name: action }).click();
  }

  get chunksSheet(): Locator {
    return this.page.getByRole("dialog").filter({ has: this.page.getByRole("list", { name: "Chunks" }) });
  }
}
