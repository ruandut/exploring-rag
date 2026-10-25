// Steps for specs/0002-system-design-page.feature.md
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";

import { type DataTable, Then, When } from "@cucumber/cucumber";

import type { AppWorld } from "../support/world.ts";

const REPO = new URL("../../", import.meta.url).pathname;

When("I open the {string} tab", async function (this: AppWorld, name: string) {
  await this.page.getByRole("tab", { name, exact: true }).click();
});

Then("I see the architecture diagram", async function (this: AppWorld) {
  await this.page.getByRole("img", { name: /^Architecture:/ }).waitFor();
});

Then("the health strip shows:", async function (this: AppWorld, table: DataTable) {
  for (const [name, value] of table.raw()) {
    const tile = this.page.locator("div.rounded-lg.border", { hasText: name }).filter({
      has: this.page.getByText(value, { exact: true }),
    });
    await tile.first().waitFor();
  }
});

Then(
  "the Django apps table lists every app in backend\\/apps",
  async function (this: AppWorld) {
    const apps = readdirSync(`${REPO}backend/apps`).filter((d) =>
      existsSync(`${REPO}backend/apps/${d}/apps.py`),
    );
    assert.ok(apps.length > 0);
    for (const app of apps) {
      await this.page.getByText(`apps.${app}`, { exact: true }).waitFor();
    }
  },
);

Then(
  "the {string} list has {int} steps",
  async function (this: AppWorld, label: string, count: number) {
    const list = this.page.getByRole("list", { name: label });
    await list.waitFor();
    assert.equal(await list.locator(":scope > li").count(), count);
  },
);

Then(
  "the {string} table lists {string}",
  async function (this: AppWorld, label: string, row: string) {
    await this.page.getByRole("table", { name: label }).getByText(row, { exact: true }).waitFor();
  },
);

Then(
  "every spec in the specs folder is listed with its status",
  async function (this: AppWorld) {
    const list = this.page.getByRole("list", { name: "Specs" });
    await list.waitFor();
    const specs = readdirSync(`${REPO}specs`).filter((f) => /^\d{4}-.*\.md$/.test(f));
    for (const file of specs) {
      const text = readFileSync(`${REPO}specs/${file}`, "utf8");
      const status = text.match(/^- \*\*Status:\*\*\s*([A-Za-z ]+?)\s*(?:←|$)/m)?.[1];
      assert.ok(status, `${file} has no Status line`);
      const item = list.getByRole("listitem").filter({ hasText: file.slice(0, 4) });
      await item.getByText(status, { exact: true }).waitFor();
    }
  },
);
