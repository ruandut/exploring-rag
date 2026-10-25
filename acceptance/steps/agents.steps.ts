// Steps for specs/0005-agents-and-chat.feature.md
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { Given, Then, When } from "@cucumber/cucumber";

import { ChatPage } from "../pages/chat-page.ts";
import { FIXTURES } from "../pages/library-page.ts";
import { createAgent, createFolder, indexDocument } from "../support/documents.ts";
import { ensureDefaultEmbedding } from "../support/embeddings.ts";
import { APP_URL } from "../support/env.ts";
import type { AppWorld } from "../support/world.ts";

const BOTH_ANSWER = "When are the office plants watered?";

export type ChatChoices = { embedding?: string; model?: string; source?: string };

/** A new chat with the agent (plus, since spec 0010, an embedding and a model if given —
 *  otherwise the chat's defaults: the oldest embedding and the default provider). */
export async function askAgent(
  world: AppWorld,
  agent: string,
  question: string,
  choices: ChatChoices = world.agentChoices[agent] ?? {},
) {
  const chat = new ChatPage(world.page);
  await chat.openNew();
  await chat.selectAgent(agent);
  if (choices.embedding) await chat.selectEmbedding(choices.embedding);
  if (choices.model) await chat.selectModel(choices.model, choices.source);
  await chat.ask(question);
  return chat;
}

// --- agents -----------------------------------------------------------------------------

async function openNewAgentForm(world: AppWorld, name: string) {
  await world.page.goto(`${APP_URL}/agents`);
  await world.page.getByRole("button", { name: "New agent" }).click();
  await world.page.getByLabel("Name", { exact: true }).fill(name);
}

async function saveAgentForm(world: AppWorld, name: string) {
  await world.page.getByRole("button", { name: "Save agent" }).click();
  await world.page.getByRole("list", { name: "Agents" }).getByText(name, { exact: true }).waitFor();
}

When(
  "I create the agent {string} with the system message {string}",
  async function (this: AppWorld, name: string, message: string) {
    await openNewAgentForm(this, name);
    await this.page.getByLabel("System message").fill(message);
    await saveAgentForm(this, name);
  },
);

Then("I can choose {string} in Chat", async function (this: AppWorld, name: string) {
  const chat = new ChatPage(this.page);
  await chat.openNew();
  await chat.selectAgent(name);
});

Given("the agent {string} exists", async function (this: AppWorld, name: string) {
  await createAgent(this, name);
});

// Older wording (drafts 0007, 0008): the chat's default embedding is "all my documents".
Given("the agent {string} can search all my folders", async function (this: AppWorld, name: string) {
  await createAgent(this, name);
});

// Older wording (draft 0007): since spec 0010 the model is picked in the chat, so this
// remembers which model to pick whenever a step asks this agent something.
Given(
  "the agent {string} uses the model {string} from my default provider",
  async function (this: AppWorld, name: string, model: string) {
    await createAgent(this, name);
    this.agentChoices[name] = { ...this.agentChoices[name], model };
  },
);

Given(
  "an agent with dense retrieval and an identical agent with hybrid retrieval",
  async function (this: AppWorld) {
    for (const retrieval of ["dense", "hybrid"]) {
      await createAgent(this, retrieval === "dense" ? "Dense" : "Hybrid", {
        rag_config: { retrieval, top_k: 2 },
      });
    }
  },
);

Given(
  "I have a model connection {string} to the fake LLM provider",
  async function (this: AppWorld, name: string) {
    const res = await this.api.post("/api/providers/connections/", {
      name,
      base_url: this.fakeLlm.baseUrl,
    });
    assert.equal(res.status, 201, res.text);
  },
);

// --- documents --------------------------------------------------------------------------

Given(
  "{string} containing {string} is indexed",
  async function (this: AppWorld, name: string, text: string) {
    assert.ok(readFileSync(`${FIXTURES}${name}`, "utf8").includes(text), `${name} lacks "${text}"`);
    await indexDocument(this, name);
  },
);

Given(
  "{string} is indexed in {string} and {string} in {string}",
  async function (this: AppWorld, a: string, folderA: string, b: string, folderB: string) {
    await indexDocument(this, a, await createFolder(this, folderA));
    await indexDocument(this, b, await createFolder(this, folderB));
  },
);

Given(
  "{string} is indexed with one chunk per heading",
  async function (this: AppWorld, name: string) {
    // Chunking belongs to the embedding since spec 0010.
    await ensureDefaultEmbedding(this, { strategy: "markdown", chunkSize: 512, chunkOverlap: 0 });
    await indexDocument(this, name);
  },
);

// --- asking -------------------------------------------------------------------------------

When("I ask {string} {string}", async function (this: AppWorld, agent: string, question: string) {
  await askAgent(this, agent, question);
});

When("I ask {string} a question both documents answer", async function (this: AppWorld, agent: string) {
  await askAgent(this, agent, BOTH_ANSWER);
});

When(
  "I ask {string} a question both documents answer using the embedding {string}",
  async function (this: AppWorld, agent: string, embedding: string) {
    await askAgent(this, agent, BOTH_ANSWER, { embedding });
  },
);

When(
  "I ask {string} {string} using the model {string} from {string}",
  async function (this: AppWorld, agent: string, question: string, model: string, source: string) {
    await askAgent(this, agent, question, { model, source });
  },
);

When("I ask {string} a long question", async function (this: AppWorld, agent: string) {
  await askAgent(this, agent, "Give me a long answer about our refunds.");
});

When("I ask both {string}", async function (this: AppWorld, question: string) {
  this.retrievedBy = {};
  for (const agent of ["Dense", "Hybrid"]) {
    const chat = await askAgent(this, agent, question);
    await chat.waitUntilFinished();
    this.retrievedBy[agent] = await chat.retrieved();
  }
});

// --- outcomes ----------------------------------------------------------------------------

Then("the answer cites {string}", async function (this: AppWorld, document: string) {
  const chat = new ChatPage(this.page);
  await chat.waitUntilFinished();
  const cited = await chat.citations();
  assert.ok(
    cited.some((c) => c.startsWith(`${document}#`)),
    `Citations: ${cited.join(", ") || "none"}`,
  );
});

Then("every cited chunk is among the retrieved chunks shown", async function (this: AppWorld) {
  const chat = new ChatPage(this.page);
  const cited = await chat.citations();
  const retrieved = (await chat.retrieved()).map((r) => r.tag);
  assert.ok(cited.length > 0, "No citations");
  for (const tag of cited) assert.ok(retrieved.includes(tag), `${tag} not in ${retrieved.join(", ")}`);
});

Then("no retrieved chunk comes from {string}", async function (this: AppWorld, document: string) {
  const chat = new ChatPage(this.page);
  await chat.waitUntilFinished();
  const retrieved = await chat.retrieved();
  assert.ok(retrieved.length > 0, "Nothing was retrieved");
  assert.ok(
    retrieved.every((r) => !r.tag.startsWith(`${document}#`)),
    retrieved.map((r) => r.tag).join(", "),
  );
});

Then(
  "the retrieved chunks differ and the hybrid agent's include the {string} chunk",
  async function (this: AppWorld, term: string) {
    const dense = this.retrievedBy.Dense.map((r) => r.tag);
    const hybrid = this.retrievedBy.Hybrid;
    assert.notDeepEqual(dense, hybrid.map((r) => r.tag), "Both agents retrieved the same chunks");
    assert.ok(hybrid.some((r) => r.text.includes(term)), `Hybrid: ${hybrid.map((r) => r.tag)}`);
    assert.ok(
      !this.retrievedBy.Dense.some((r) => r.text.includes(term)),
      "Dense unexpectedly found it too — the scenario no longer shows the difference",
    );
  },
);

Then("the partial answer stays visible marked {string}", async function (this: AppWorld, mark: string) {
  const chat = new ChatPage(this.page);
  const answer = await chat.waitUntilFinished();
  await answer.getByText(mark).waitFor();
  const text = (await answer.getByLabel("Answer text").textContent()) ?? "";
  assert.ok(text.length > 10, "The partial answer disappeared");
  assert.ok(!text.includes("detail79"), "The answer finished — it wasn't stopped mid-way");
});

Then("the answer comes from {string}", async function (this: AppWorld, label: string) {
  const chat = new ChatPage(this.page);
  const answer = await chat.waitUntilFinished();
  // The footer reads "<agent> · Embedding: … · <source> · <model>".
  await chat.answeredWith(answer).filter({ hasText: label }).waitFor();
  const model = label.split(" · ").at(-1)!;
  assert.ok(
    this.fakeLlm.requests.some((r) => r.includes("/chat/completions") && r.endsWith(` ${model}`)),
    `The provider never received a request for ${model}`,
  );
});

// --- conversations -------------------------------------------------------------------------

Given("I had a conversation with {string}", async function (this: AppWorld, agent: string) {
  await createAgent(this, agent);
  const chat = await askAgent(this, agent, "Hello there");
  await chat.waitUntilFinished();
  this.conversationId = await chat.openConversationId();
});

When("I reload the page", async function (this: AppWorld) {
  await this.page.goto(`${APP_URL}/chat`);
  await this.page.reload();
});

Then("I can open that conversation and see its messages", async function (this: AppWorld) {
  const list = this.page.getByRole("navigation", { name: "Conversations" });
  await list.getByRole("link", { name: /Hello there/ }).click();
  await this.page.getByText("Hello there", { exact: true }).last().waitFor();
  const answer = new ChatPage(this.page).latestAnswer;
  await answer.getByLabel("Answer text").filter({ hasText: /\w{3,}/ }).waitFor();
});
