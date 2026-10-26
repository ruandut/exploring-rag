import type { Locator, Page } from "playwright";

import { APP_URL } from "../support/env.ts";
import { FIXTURES } from "./library-page.ts";
import { ModelPicker } from "./model-picker.ts";

export type CaseRow = {
  kind: string;
  question: string;
  reference: string;
  document: string;
  evidence: string;
};

const RUN_TIMEOUT = 60_000;

export class BenchmarksPage {
  page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async createSuite(name: string): Promise<void> {
    await this.page.goto(`${APP_URL}/benchmarks`);
    await this.page.getByRole("button", { name: "New suite" }).click();
    await this.page.getByLabel("Suite name").fill(name);
    await this.page.getByRole("button", { name: "Create suite" }).click();
    await this.page.waitForURL(/\/benchmarks\/\d+$/);
  }

  async openSuite(id: number): Promise<void> {
    await this.page.goto(`${APP_URL}/benchmarks/${id}`);
    await this.page.getByRole("button", { name: "Save suite" }).waitFor();
  }

  async addCase(row: CaseRow): Promise<void> {
    await this.page.getByRole("button", { name: "Add case" }).click();
    const n = await this.page.getByRole("group", { name: /^Case \d+$/ }).count();
    await this.page.getByLabel(`Kind ${n}`).selectOption(row.kind);
    await this.page.getByLabel(`Question ${n}`).fill(row.question);
    if (row.kind === "qa") {
      await this.page.getByLabel(`Reference answer ${n}`).fill(row.reference);
      await this.page.getByLabel(`Relevant document ${n}`).fill(row.document);
      await this.page.getByLabel(`Evidence ${n}`).fill(row.evidence);
    }
  }

  async checkMetric(label: string): Promise<void> {
    await this.page.getByRole("checkbox", { name: new RegExp(`^${label}$`, "i") }).check();
  }

  async save(): Promise<void> {
    await this.page.getByRole("button", { name: "Save suite" }).click();
    await this.page.getByText(/^Saved .* \(version \d+\)$/).waitFor();
  }

  get summary(): Locator {
    return this.page.getByLabel("Suite summary");
  }

  async importJsonl(file: string): Promise<void> {
    await this.page.getByLabel("Choose a JSONL file of cases").setInputFiles(`${FIXTURES}${file}`);
    await this.page.getByText(/^Imported \d+ cases$/).waitFor();
  }

  async exportJsonl(): Promise<string> {
    const download = this.page.waitForEvent("download");
    await this.page.getByRole("button", { name: "Export JSONL" }).click();
    const stream = await (await download).createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream) chunks.push(chunk as Buffer);
    return Buffer.concat(chunks).toString("utf8");
  }

  /** Pick a target ("Docs helper", or "Bare model · Default provider" + model) and run. An
   *  agent target may also name the embedding it searches. */
  async run(
    target: string,
    model?: string,
    second?: { target: string; model?: string },
    embedding?: string,
  ): Promise<number> {
    await this.page.getByLabel("Target", { exact: true }).selectOption({ label: target });
    if (embedding !== undefined) {
      await this.page.getByLabel("Target embedding").selectOption({ label: `Embedding: ${embedding}` });
    }
    if (model !== undefined) await new ModelPicker(this.page, "Target model").pick(model);
    if (second) {
      await this.page.getByRole("checkbox", { name: "Compare with a second target" }).check();
      await this.page.getByLabel("Second target", { exact: true }).selectOption({ label: second.target });
      if (second.model !== undefined) await new ModelPicker(this.page, "Second target model").pick(second.model);
      await this.page.getByRole("button", { name: "Run both" }).click();
    } else {
      await this.page.getByRole("button", { name: "Run", exact: true }).click();
    }
    await this.page.waitForURL(/\/benchmarks\/runs\/\d+$/);
    return Number(this.page.url().split("/").at(-1));
  }

  /** Run one agent twice, searching a different embedding each time (spec 0010). */
  async compareEmbeddings(agent: string, first: string, second: string): Promise<number> {
    await this.page.getByLabel("Target", { exact: true }).selectOption({ label: agent });
    await this.page.getByLabel("Target embedding").selectOption({ label: `Embedding: ${first}` });
    await this.page.getByRole("checkbox", { name: "Compare with a second target" }).check();
    await this.page.getByLabel("Second target", { exact: true }).selectOption({ label: agent });
    await this.page
      .getByLabel("Second target embedding")
      .selectOption({ label: `Embedding: ${second}` });
    await this.page.getByRole("button", { name: "Run both" }).click();
    await this.page.waitForURL(/\/benchmarks\/runs\/\d+$/);
    return Number(this.page.url().split("/").at(-1));
  }

  /** A run's panel on the results page; `label` defaults to the only/first one. */
  run$(label?: string): Locator {
    return label
      ? this.page.getByRole("region", { name: `Run ${label}` })
      : this.page.getByRole("region", { name: /^Run / }).first();
  }

  /** Finished = passed, failed or stopped (spec 0012). */
  async waitFinished(region: Locator, statuses: RegExp = /^(Passed|Failed|Stopped)$/): Promise<void> {
    await region.getByLabel("Run status").filter({ hasText: statuses }).waitFor({ timeout: RUN_TIMEOUT });
  }

  /** Open a suite and press "Delete suite"; returns the confirmation dialog (spec 0014). */
  async startDeletingSuite(id: number): Promise<Locator> {
    await this.openSuite(id);
    await this.page.getByRole("button", { name: "Delete suite", exact: true }).click();
    const dialog = this.page.getByRole("alertdialog");
    await dialog.waitFor();
    return dialog;
  }

  get deletedSuiteRuns(): Locator {
    return this.page.getByRole("list", { name: "Runs of deleted suites" });
  }

  /** Press a button in one run's panel (e.g. "Stop run", "Resume"). */
  async pressInRun(region: Locator, name: string): Promise<void> {
    await region.getByRole("button", { name, exact: true }).click();
  }

  caseRow(region: Locator, question: string): Locator {
    return region.getByRole("listitem", { name: question, exact: true });
  }

  async openCase(region: Locator, question: string): Promise<Locator> {
    const row = this.caseRow(region, question);
    const button = row.getByRole("button").first();
    if ((await button.getAttribute("aria-expanded")) !== "true") await button.click();
    return row;
  }
}
