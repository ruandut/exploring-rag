// The authenticated layout: navigation drawer + user menu.
import type { Locator, Page } from "playwright";

export class AppShell {
  page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  get drawer(): Locator {
    return this.page.locator('[data-slot="sidebar"]');
  }

  navItem(label: string): Locator {
    return this.drawer.locator('[data-slot="sidebar-menu-button"]', { hasText: label });
  }

  async collapse(): Promise<void> {
    await this.page.getByRole("button", { name: "Toggle Sidebar" }).first().click();
  }

  get userMenu(): Locator {
    return this.drawer.locator('[data-slot="sidebar-footer"]');
  }
}
