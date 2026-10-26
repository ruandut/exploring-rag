// Steps for specs/0006-benchmarks.feature.md
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { type DataTable, Given, Then, When } from "@cucumber/cucumber";

import { BenchmarksPage, type CaseRow } from "../pages/benchmarks-page.ts";
import { FIXTURES } from "../pages/library-page.ts";
import { ApiClient, createTestUser } from "../support/app.ts";
import { createAgent } from "../support/documents.ts";
import { APP_URL } from "../support/env.ts";
import type { AppWorld } from "../support/world.ts";

/** The suite every scenario but AT-01 starts from (same as AT-01 builds through the UI). */
const BASICS = {
  metrics: ["faithfulness", "answer_relevancy", "recall"],
  cases: [
    {
      kind: "qa",
      question: "What is the refund window?",
      reference_answer: "30 days",
      relevant_documents: ["handbook.md"],
      evidence: "refund window is 30",
    },
    {
      kind: "qa",
      question: "How many days of leave?",
      reference_answer: "25 days",
      relevant_documents: ["handbook.md"],
      evidence: "25 days of paid",
    },
    { kind: "refusal", question: "Who won the 2030 World Cup?" },
  ],
  boundaries: [] as object[],
};

const METRIC_IDS: Record<string, string> = {
  faithfulness: "faithfulness",
  "answer relevancy": "answer_relevancy",
  "recall@5": "recall",
};

function parseBoundary(text: string) {
  const m = text.match(/^(\w+) (mean|p50|p95) (≥|≤) ([\d.]+)$/);
  assert.ok(m, `Can't read boundary "${text}"`);
  return { metric: m[1], aggregate: m[2], comparator: m[3] === "≥" ? "gte" : "lte", value: Number(m[4]) };
}

async function ensureSuite(world: AppWorld, name: string, boundaries: object[] = []): Promise<number> {
  if (world.suites[name]) return world.suites[name];
  const res = await world.api.post("/api/evals/suites/", { name, ...BASICS, boundaries });
  assert.equal(res.status, 201, res.text);
  world.suites[name] = res.body.id;
  return res.body.id;
}

async function patchSuite(world: AppWorld, name: string, patch: object) {
  const res = await world.api.request("PATCH", `/api/evals/suites/${world.suites[name]}/`, patch);
  assert.equal(res.status, 200, res.text);
}

async function agentId(world: AppWorld, name: string): Promise<number> {
  const agents = (await world.api.get("/api/agents/")).body as { id: number; name: string }[];
  const found = agents.find((a) => a.name === name);
  assert.ok(found, `No agent "${name}"`);
  return found.id;
}

async function runFromUi(world: AppWorld, suite: string, target: string, model?: string) {
  const page = new BenchmarksPage(world.page);
  await page.openSuite(await ensureSuite(world, suite));
  world.runId = await page.run(target, model);
  world.pageLoads = 0;
}

// --- suites -------------------------------------------------------------------------------

When(
  "I create the suite {string} with the cases:",
  async function (this: AppWorld, name: string, table: DataTable) {
    const page = new BenchmarksPage(this.page);
    await page.createSuite(name);
    this.suites[name] = Number(this.page.url().split("/").at(-1));
    for (const row of table.hashes()) {
      const r: CaseRow = {
        kind: row.kind,
        question: row.question,
        reference: row["reference answer"],
        document: row["relevant document"],
        evidence: row.evidence,
      };
      await page.addCase(r);
    }
  },
);

When(
  "I select the metrics {string}, {string} and {string}",
  async function (this: AppWorld, a: string, b: string, c: string) {
    const page = new BenchmarksPage(this.page);
    for (const label of [a, b, c]) await page.checkMetric(label);
    await page.save();
  },
);

Then(
  "{string} shows {int} cases and {int} metrics",
  async function (this: AppWorld, _name: string, cases: number, metrics: number) {
    await new BenchmarksPage(this.page).summary
      .filter({ hasText: `${cases} cases · ${metrics} metrics` })
      .waitFor();
  },
);

Given("the suite {string} exists", async function (this: AppWorld, name: string) {
  await ensureSuite(this, name);
});

Given(
  "the suite {string} exists with the boundary {string}",
  async function (this: AppWorld, name: string, boundary: string) {
    await ensureSuite(this, name, [parseBoundary(boundary)]);
  },
);

Given(
  "{string} is judged by the model {string} from my default provider",
  async function (this: AppWorld, suite: string, model: string) {
    await patchSuite(this, suite, { judge_connection: null, judge_model: model });
  },
);

Given(
  "{string} is judged by the model {string} from {string}",
  async function (this: AppWorld, suite: string, model: string, connection: string) {
    const conns = (await this.api.get("/api/providers/connections/")).body as { id: number; name: string }[];
    const conn = conns.find((c) => c.name === connection);
    assert.ok(conn, `No connection "${connection}"`);
    await patchSuite(this, suite, { judge_connection: conn.id, judge_model: model });
  },
);

// --- running ------------------------------------------------------------------------------

When(
  "I run {string} against the agent {string}",
  async function (this: AppWorld, suite: string, agent: string) {
    await runFromUi(this, suite, agent);
  },
);

When(
  "I run {string} against {string}",
  async function (this: AppWorld, suite: string, agent: string) {
    await runFromUi(this, suite, agent);
  },
);

When(
  "I run {string} against the bare model {string} from my default provider",
  async function (this: AppWorld, suite: string, model: string) {
    await runFromUi(this, suite, "Bare model · Default provider", model);
  },
);

When(
  "I compare {string} on the bare model {string} with the agent {string}",
  async function (this: AppWorld, suite: string, model: string, agent: string) {
    const page = new BenchmarksPage(this.page);
    await page.openSuite(await ensureSuite(this, suite));
    this.runId = await page.run("Bare model · Default provider", model, { target: agent });
  },
);

Given(
  "a finished run of {string} against {string}",
  async function (this: AppWorld, suite: string, agent: string) {
    const id = await agentId(this, agent);
    const res = await this.api.request("PATCH", `/api/agents/${id}/`, {
      system_message: "Answer from the handbook.",
    });
    assert.equal(res.status, 200, res.text);
    const start = await this.api.post("/api/benchmarks/runs/", {
      suite: await ensureSuite(this, suite),
      targets: [{ kind: "agent", agent: id }],
    });
    assert.equal(start.status, 201, start.text);
    this.runId = start.body[0].id;
    const deadline = Date.now() + 60_000;
    while ((await this.api.get(`/api/benchmarks/runs/${this.runId}/`)).body.status === "running") {
      assert.ok(Date.now() < deadline, "The run didn't finish");
      await new Promise((r) => setTimeout(r, 300));
    }
  },
);

When(
  "I change the system message of {string} to {string}",
  async function (this: AppWorld, agent: string, message: string) {
    const res = await this.api.request("PATCH", `/api/agents/${await agentId(this, agent)}/`, {
      system_message: message,
    });
    assert.equal(res.status, 200, res.text);
  },
);

Given("my provider is unreachable", function (this: AppWorld) {
  this.fakeLlm.down = true;
});

When("my provider is the fake LLM provider again", function (this: AppWorld) {
  this.fakeLlm.down = false;
});

// --- results ------------------------------------------------------------------------------

Then(
  "each case shows its answer, retrieved chunks, scores and latency",
  async function (this: AppWorld) {
    const page = new BenchmarksPage(this.page);
    const run = page.run$();
    await page.waitFinished(run);
    for (const c of BASICS.cases) {
      const row = await page.openCase(run, c.question);
      assert.ok(((await row.getByLabel("Case answer").textContent()) ?? "").length > 3, `${c.question}: no answer`);
      assert.match((await row.getByRole("button").first().textContent()) ?? "", /\d+\.\d s/, "no latency");
      assert.ok((await row.getByLabel("Case scores").getByRole("listitem").count()) > 0, "no scores");
      if (c.kind === "qa") {
        assert.ok(
          (await row.getByLabel("Case retrieved chunks").getByRole("listitem").count()) > 0,
          `${c.question}: nothing retrieved`,
        );
      }
    }
  },
);

Then("the run summary shows the mean of each metric", async function (this: AppWorld) {
  const metrics = new BenchmarksPage(this.page).run$().getByRole("table", { name: "Metrics" });
  for (const name of ["Faithfulness", "Answer relevancy", "Recall@5"]) {
    const mean = await metrics.getByRole("row", { name }).getByRole("cell").nth(1).textContent();
    assert.match(mean ?? "", /^\d\.\d\d$/, `${name} mean: ${mean}`);
  }
});

When("I open the case {string}", async function (this: AppWorld, question: string) {
  const page = new BenchmarksPage(this.page);
  const run = page.run$();
  await page.waitFinished(run);
  await page.openCase(run, question);
});

Then(
  "I see how recall@5 was calculated, e.g. {string}",
  async function (this: AppWorld, text: string) {
    await new BenchmarksPage(this.page)
      .run$()
      .getByLabel("Case scores")
      .getByRole("listitem", { name: "Recall@5" })
      .getByText(text)
      .waitFor();
  },
);

Then("the run is marked {string}", async function (this: AppWorld, status: string) {
  const page = new BenchmarksPage(this.page);
  const run = page.run$();
  await page.waitFinished(run);
  assert.equal(await run.getByLabel("Run status").textContent(), status);
});

Then(
  "the boundary {string} shows ✗ with margin {string}",
  async function (this: AppWorld, boundary: string, margin: string) {
    const item = new BenchmarksPage(this.page).run$().getByRole("listitem", { name: boundary });
    await item.getByText("✗").waitFor({ state: "attached" });
    await item.getByText(margin, { exact: true }).waitFor();
  },
);

Then(/^the case "([^"]+)" (passes|fails)$/, async function (this: AppWorld, question: string, verdict: string) {
  const page = new BenchmarksPage(this.page);
  const run = page.run$();
  await page.waitFinished(run);
  const status = await page.caseRow(run, question).getByLabel("Case status").textContent();
  assert.equal(status, verdict === "passes" ? "Passed" : "Failed");
});

Then("I see both runs side by side with per-metric deltas", async function (this: AppWorld) {
  const page = new BenchmarksPage(this.page);
  const runs = this.page.getByRole("region", { name: /^Run / });
  await runs.nth(1).waitFor();
  for (const run of await runs.all()) await page.waitFinished(run);
  const deltas = await this.page.getByRole("table", { name: "Comparison" }).getByLabel("Delta").allTextContents();
  assert.ok(deltas.some((d) => /^[+-]\d\.\d\d$/.test(d)), `Deltas: ${deltas.join(", ")}`);
});

Then(
  "recall@5 shows {string} for the bare model",
  async function (this: AppWorld, value: string) {
    const row = this.page.getByRole("table", { name: "Comparison" }).getByRole("row", { name: "Recall@5" });
    // Column 1 is the bare model (it's always placed first).
    assert.equal(await row.getByRole("cell").nth(1).textContent(), value);
  },
);

Then(
  "the progress counter moves from {string} to {string} without reloading the page",
  async function (this: AppWorld, from: string, to: string) {
    const counter = new BenchmarksPage(this.page).run$().getByLabel("Progress");
    const seen: string[] = [];
    const deadline = Date.now() + 60_000;
    while (Date.now() < deadline) {
      const text = ((await counter.textContent()) ?? "").replace(/\s+/g, " ").trim();
      if (seen.at(-1) !== text) seen.push(text);
      if (text === to) break;
      await new Promise((r) => setTimeout(r, 50));
    }
    assert.equal(seen[0], from, `Progress went ${seen.join(" → ")}`);
    assert.equal(seen.at(-1), to, `Progress went ${seen.join(" → ")}`);
    assert.equal(this.pageLoads, 0, "The page reloaded");
  },
);

Then("the final result appears without reloading the page", async function (this: AppWorld) {
  const page = new BenchmarksPage(this.page);
  await page.waitFinished(page.run$());
  assert.equal(this.pageLoads, 0, "The page reloaded");
});

Then("that run still shows the original system message", async function (this: AppWorld) {
  await this.page.goto(`${APP_URL}/benchmarks/runs/${this.runId}`);
  const run = new BenchmarksPage(this.page).run$();
  await run.getByText("Target configuration (snapshot)").click();
  assert.equal(await run.getByLabel("Snapshot system message").textContent(), "Answer from the handbook.");
});

When("I import {string} into {string}", async function (this: AppWorld, file: string, suite: string) {
  const page = new BenchmarksPage(this.page);
  await page.openSuite(await ensureSuite(this, suite));
  await page.importJsonl(file);
});

Then(/^"([^"]+)" shows (\d+) cases$/, async function (this: AppWorld, _suite: string, cases: string) {
  await new BenchmarksPage(this.page).summary.filter({ hasText: `${cases} cases ·` }).waitFor();
});

Then(
  "exporting {string} returns {int} cases including those from {string}",
  async function (this: AppWorld, _suite: string, count: number, file: string) {
    const exported = await new BenchmarksPage(this.page).exportJsonl();
    const questions = exported.trim().split("\n").map((l) => JSON.parse(l).question as string);
    assert.equal(questions.length, count);
    for (const line of readFileSync(`${FIXTURES}${file}`, "utf8").trim().split("\n")) {
      assert.ok(questions.includes(JSON.parse(line).question), `missing ${line}`);
    }
  },
);

Given("another user has a suite {string}", async function (this: AppWorld, name: string) {
  const other = new ApiClient();
  await other.login(createTestUser("other"));
  const res = await other.post("/api/evals/suites/", { name, ...BASICS });
  assert.equal(res.status, 201, res.text);
  this.suites[name] = res.body.id;
});

Then("I don't see {string} and can't run it", async function (this: AppWorld, name: string) {
  await this.page.goto(`${APP_URL}/benchmarks`);
  await this.page.getByRole("button", { name: "New suite" }).waitFor();
  assert.equal(await this.page.getByRole("listitem", { name, exact: true }).count(), 0);
  await createAgent(this, "Docs helper");
  const res = await this.api.post("/api/benchmarks/runs/", {
    suite: this.suites[name],
    targets: [{ kind: "agent", agent: await agentId(this, "Docs helper") }],
  });
  assert.equal(res.status, 404);
});

Then("the run shows {int} failed cases", async function (this: AppWorld, n: number) {
  const page = new BenchmarksPage(this.page);
  const run = page.run$();
  await page.waitFinished(run);
  await run.getByLabel("Failed cases").filter({ hasText: `${n} failed cases` }).waitFor();
});

Then(
  "the run shows {int} failed cases and the summary is updated",
  async function (this: AppWorld, n: number) {
    const page = new BenchmarksPage(this.page);
    const run = page.run$();
    await run.getByLabel("Failed cases").filter({ hasText: `${n} failed cases` }).waitFor({ timeout: 60_000 });
    await page.waitFinished(run);
    const mean = await run.getByRole("table", { name: "Metrics" }).getByRole("row", { name: "Faithfulness" })
      .getByRole("cell").nth(1).textContent();
    assert.match(mean ?? "", /^\d\.\d\d$/);
  },
);

Then("the judge's requests went to {string}", async function (this: AppWorld, model: string) {
  const page = new BenchmarksPage(this.page);
  await page.waitFinished(page.run$());
  assert.ok(
    this.fakeLlm.chats.includes(model),
    `No chat request for ${model}`,
  );
});
