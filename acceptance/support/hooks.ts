import {
  After,
  AfterAll,
  Before,
  BeforeAll,
  setDefaultTimeout,
  Status,
} from "@cucumber/cucumber";
import { chromium, type Browser } from "playwright";

import { createTestUser } from "./app.ts";
import { HEADLESS } from "./env.ts";
import { type FakeLlm, startFakeLlm } from "./fake-llm.ts";
import type { AppWorld } from "./world.ts";

// UI steps wait on a real browser, websockets and Hatchet runs.
setDefaultTimeout(30_000);

let browser: Browser;
let fakeLlm: FakeLlm;

BeforeAll(async function () {
  browser = await chromium.launch({ headless: HEADLESS });
  fakeLlm = await startFakeLlm();
});

AfterAll(async function () {
  await browser?.close();
  await fakeLlm?.close();
});

Before(async function (this: AppWorld) {
  this.user = createTestUser();
  await this.api.login(this.user);
  this.fakeLlm = fakeLlm;
  fakeLlm.down = false; // an outage from a previous scenario must not leak
  this.context = await browser.newContext();
  this.page = await this.context.newPage();
  this.page.on("load", () => this.pageLoads++);
  this.page.on("websocket", (ws) => {
    ws.on("framereceived", ({ payload }) => {
      try {
        this.wsEvents.push(JSON.parse(String(payload)));
      } catch {
        // not JSON — ignore
      }
    });
  });
  this.page.on("response", async (response) => {
    const type = response.headers()["content-type"] ?? "";
    if (type.includes("json") || type.includes("text")) {
      this.responseBodies.push(await response.text().catch(() => ""));
    }
  });
});

After(async function (this: AppWorld, { result }) {
  if (result?.status === Status.FAILED && this.page) {
    // Attached to the HTML report (reports/acceptance.html).
    this.attach(await this.page.screenshot({ fullPage: true }), "image/png");
  }
  Object.values(this.sockets).forEach((s) => s.close());
  await this.context?.close();
});
