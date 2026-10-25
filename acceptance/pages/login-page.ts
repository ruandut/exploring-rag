// Page objects: the only place that knows how the UI is built (labels, roles, URLs).
// Prefer accessible locators (getByRole / getByLabel) — they double as an a11y check.
import type { Page } from "playwright";

import type { TestUser } from "../support/app.ts";
import { APP_URL } from "../support/env.ts";

export class LoginPage {
  page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async signIn(user: TestUser): Promise<void> {
    await this.page.goto(`${APP_URL}/login`);
    await this.page.getByLabel("Username").fill(user.username);
    await this.page.getByLabel("Password").fill(user.password);
    await this.page.getByRole("button", { name: "Sign in" }).click();
    await this.page.waitForURL("**/chat");
  }
}
