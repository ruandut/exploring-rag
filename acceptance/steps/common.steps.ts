// Steps shared by every spec. Keep them generic and phrased from the user's point of view.
import assert from "node:assert/strict";

import { Given, Then, When } from "@cucumber/cucumber";

import { LoginPage } from "../pages/login-page.ts";
import type { AppWorld } from "../support/world.ts";

Given("I am signed in", async function (this: AppWorld) {
  await new LoginPage(this.page).signIn(this.user);
});

When("I press {string}", async function (this: AppWorld, name: string) {
  await this.page.getByRole("button", { name, exact: true }).click();
});

Then("I see {string}", async function (this: AppWorld, text: string) {
  await this.page.getByText(text, { exact: false }).first().waitFor();
});

Then("I am asked {string}", async function (this: AppWorld, question: string) {
  await this.page.getByRole("alertdialog").getByText(question).waitFor();
});

Then("the {string} button is disabled", async function (this: AppWorld, name: string) {
  assert.equal(await this.page.getByRole("button", { name, exact: true }).isDisabled(), true);
});

Then(
  "no response the browser received contains {string}",
  async function (this: AppWorld, secret: string) {
    assert.ok(this.responseBodies.length > 0, "No responses were captured");
    const leaks = this.responseBodies.filter((b) => b.includes(secret));
    assert.equal(leaks.length, 0, `Secret appeared in ${leaks.length} response(s)`);
  },
);
