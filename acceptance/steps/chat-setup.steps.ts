// Steps for specs/0013-chat-setup-card.feature.md
import { Then } from "@cucumber/cucumber";

import { ChatPage } from "../pages/chat-page.ts";
import type { AppWorld } from "../support/world.ts";

const PICKERS = ["Agent", "Embedding", "Model"];

Then(
  "I see the chat setup card with the Agent, Embedding and Model pickers",
  async function (this: AppWorld) {
    const chat = new ChatPage(this.page);
    await chat.setupCard.waitFor();
    for (const name of PICKERS) {
      await chat.setupCard.getByRole("combobox", { name, exact: true }).waitFor();
    }
  },
);

Then("there is no message bar yet", async function (this: AppWorld) {
  await new ChatPage(this.page).messageBox.waitFor({ state: "detached" });
});

Then("the setup card is gone and the message bar is shown", async function (this: AppWorld) {
  const chat = new ChatPage(this.page);
  await chat.messageBox.waitFor();
  await chat.setupCard.waitFor({ state: "detached" });
});

Then("I see the Agent, Embedding and Model pickers", async function (this: AppWorld) {
  for (const name of PICKERS) {
    await this.page.getByRole("combobox", { name, exact: true }).waitFor();
  }
});
