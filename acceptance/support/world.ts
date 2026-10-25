// Per-scenario state shared by step definitions (Cucumber's "World").
import { setWorldConstructor, World, type IWorldOptions } from "@cucumber/cucumber";
import type { BrowserContext, Page } from "playwright";

import { ApiClient, type TestUser } from "./app.ts";
import type { SocketClient } from "./socket.ts";
import type { FakeLlm } from "./fake-llm.ts";

export class AppWorld extends World {
  api = new ApiClient();
  user!: TestUser;
  context!: BrowserContext;
  page!: Page;
  /** Every JSON/text body the browser received — lets specs assert what never leaks. */
  responseBodies: string[] = [];
  fakeLlm!: FakeLlm;
  lastApiResponse: { status: number; body: any } | null = null;
  /** Websocket clients opened by steps, by name ("mine", "other"). Closed after each scenario. */
  sockets: Record<string, SocketClient> = {};
  otherUser?: TestUser;
  /** Every JSON frame the app's own websocket received, in order. */
  wsEvents: { type: string; [key: string]: unknown }[] = [];
  /** Full page loads so far — lets specs prove something happened "without reloading". */
  pageLoads = 0;
  folders: Record<string, number> = {};
  documents: Record<string, number> = {};
  suites: Record<string, number> = {};
  /** Id of the benchmark run a scenario is looking at. */
  runId?: number;
  /** Retrieved chunks shown per agent, for scenarios that compare agents. */
  retrievedBy: Record<string, { tag: string; text: string }[]> = {};
  otherApi = new ApiClient();
  /** The conversation a chat scenario is looking at (from the ?c= in the URL). */
  conversationId?: number;
  /** The agent run a scenario cancelled. */
  cancelledRunId?: string;
  /** Embedding / model to pick in the chat when asking an agent (older "agent uses model"). */
  agentChoices: Record<string, { embedding?: string; model?: string; source?: string }> = {};
  /** The model picker a scenario has open, and the endpoint group it's looking at. */
  picker?: string;
  pickerGroup?: string;
  /** The embeddings a benchmark comparison ran with. */
  comparedEmbeddings?: string[];
  /** The embedding a scenario last created or acted on. */
  lastEmbedding?: string;
  /** fakeLlm.embedded / wsEvents lengths before an action, to check only what came after. */
  embeddedMark?: number;
  wsMark?: number;

  constructor(options: IWorldOptions) {
    super(options);
  }
}

setWorldConstructor(AppWorld);
