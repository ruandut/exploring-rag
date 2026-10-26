// A tiny OpenAI-compatible server so specs are deterministic and free. It implements what the
// app calls: models, embeddings and chat completions (plain, streamed, and with tool calls).
//
// - API key "bad-key" → 401 with OpenAI's error shape, like a real provider.
// - Any model with "notools" in its name rejects `tools` the way Ollama does for models
//   without tool support (400 "... does not support tools").
// - Judge prompts ("You are grading…") get JSON scores: model "fake-judge-0.8" always scores 0.8;
//   otherwise refusal_rate is 1 only if the answer admits it doesn't know, and the rest score 1.
// - Bare-model prompts: "fake-inventor" confidently makes things up; others say "I don't know".
// - Any model with "slow" in its name (e.g. "fake-slow", spec 0011) answers like the others but
//   streams its tokens ten times more slowly, so speed comparisons are deterministic.
// - `down = true` makes every request fail with 503, like a provider outage.
// - `stuck = true` makes every streamed answer drip one word every few seconds (spec 0012), so a
//   benchmark run is reliably still in flight when a spec presses Stop.
// - Embeddings are a toy "8 topics" model (see TOPICS): texts about the same topic point the
//   same way. Like real embedding models it ignores exact codes such as "E-4012" — which is
//   precisely the gap keyword/hybrid search fills. A model named "…-<n>" (e.g. fake-embed-16)
//   returns n dimensions (the 8 topics, zero-padded), so specs can compare embedding sizes.
// - `embedded` records every text sent to /embeddings, so specs can check what was indexed.
// - Other personalities for the model picker (spec 0010), on the same port:
//   /ollama/…      an Ollama: /api/version, /api/tags, /api/show say which models embed (and
//                  how big) and which chat (with or without tools); `ollamaNoEmbeddings`
//                  hides its embedding models, like a fresh install.
//   /bare/…        lists acme-embed-small and mystery-7b with no metadata at all.
//   /chat-only/…   lists no embedding models.
import { createServer, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";

export const FAKE_EMBEDDING_DIMENSIONS = 8;
export const FAKE_MODELS = ["fake-chat", "fake-embed", "fake-local", "fake-notools", "fake-slow"];

/** The Ollama personality's models, as `/api/show` describes them. */
const OLLAMA_MODELS: Record<string, { capabilities: string[]; dims?: number }> = {
  "fake-chat": { capabilities: ["completion", "tools"] },
  "fake-embed": { capabilities: ["embedding"], dims: 8 },
  "fake-embed-16": { capabilities: ["embedding"], dims: 16 },
  "fake-notools": { capabilities: ["completion"] },
};
const PERSONALITY_MODELS: Record<string, string[]> = {
  bare: ["acme-embed-small", "mystery-7b"],
  "chat-only": ["fake-chat"],
};

const TOPICS: string[][] = [
  ["refund", "refunds", "payment", "payments", "pay", "price", "cost", "money", "purchase", "credit", "revenue", "billing", "gateway"],
  ["error", "errors", "code", "codes", "failure", "failures", "fault", "faults", "broke", "broken", "crash", "crashes", "bug", "issue", "problem"],
  ["day", "days", "week", "weekdays", "friday", "fridays", "monday", "hour", "hours", "minute", "timed", "time", "year", "morning", "window"],
  ["team", "staff", "employee", "employees", "customer", "customers", "people", "manager", "starters", "support"],
  ["office", "building", "desk", "parking", "room", "facilities"],
  ["plant", "plants", "water", "watered", "waters", "watering", "garden"],
  ["password", "security", "lock", "screen", "suspicious", "email"],
];
const TOPIC_OF = new Map(TOPICS.flatMap((words, dim) => words.map((w) => [w, dim] as const)));

export function dimensionsOf(model: string): number {
  const n = Number(/-(\d+)$/.exec(model)?.[1]);
  return n > 0 ? n : FAKE_EMBEDDING_DIMENSIONS;
}

function embed(text: string, dims = FAKE_EMBEDDING_DIMENSIONS): number[] {
  const v = new Array(Math.max(dims, FAKE_EMBEDDING_DIMENSIONS)).fill(0);
  for (const word of text.toLowerCase().match(/[a-z]+/g) ?? []) {
    const dim = TOPIC_OF.get(word);
    if (dim !== undefined) v[dim] += 1;
    else if (word.length > 2) v[7] += 0.1; // everything else: a faint "other" signal
  }
  const norm = Math.hypot(...v) || 1;
  return v.map((x) => x / norm).slice(0, dims);
}

type Msg = { role: string; content?: string | null; tool_calls?: unknown[] };

const STOPWORDS = new Set(["what", "which", "when", "where", "who", "how", "does", "the", "are", "our", "your", "give", "with", "about", "from", "that", "this", "there", "long", "answer"]);

function words(text: string): Set<string> {
  return new Set(
    (text.toLowerCase().match(/[a-z]{4,}/g) ?? []).filter((w) => !STOPWORDS.has(w)),
  );
}

/** The answer the fake "model" gives: the first sentence of the first passage that shares a
 *  meaningful word with the question — or an honest "I couldn't find that". */
function answerFrom(messages: Msg[]): string {
  const material = messages
    .filter((m) => m.role === "tool" || (m.role === "user" && m.content?.includes("Passages from my documents")))
    .map((m) => m.content ?? "")
    .join("\n");
  const userTurn = [...messages].reverse().find((m) => m.role === "user")?.content ?? "";
  const question = userTurn.split("Question: ").at(-1) ?? userTurn;
  const asked = words(question);
  let answer = "I couldn't find that in your documents.";
  // Each passage is "[doc#n]" followed by its text, up to the next tag.
  const passages = material.matchAll(/\[([^\]\n]+#\d+)\]\n([\s\S]*?)(?=\n\n\[[^\]\n]+#\d+\]\n|$)/g);
  outer: for (const [, tag, text] of passages) {
    for (const sentence of text.split(/(?<=[.!?])\s+|\n+/)) {
      if ([...words(sentence)].some((w) => asked.has(w))) {
        answer = `Based on your documents: ${sentence.replace(/^#+\s*/, "").trim()} [${tag}]`;
        break outer;
      }
    }
  }
  if (/\blong\b/i.test(question)) {
    answer += " " + Array.from({ length: 80 }, (_, i) => `detail${i}`).join(" ");
  }
  return answer;
}

function judgeReply(model: string, prompt: string): string {
  const metric = prompt.match(/^Metric: (\S+)/m)?.[1] ?? "";
  const answer = prompt.split("ANSWER:\n")[1]?.split("\n\nCONTEXT:")[0] ?? "";
  const fixed = model.match(/^fake-judge-([\d.]+)$/)?.[1];
  let score = fixed ? Number(fixed) : 1;
  if (!fixed && metric === "refusal_rate") {
    score = /couldn't find|don't know|do not know/i.test(answer) ? 1 : 0;
  }
  return JSON.stringify({ score, reasoning: `fake judge: ${metric} = ${score}` });
}

export type FakeLlm = {
  baseUrl: string;
  requests: string[];
  /** Every text sent to /embeddings, in order. */
  embedded: string[];
  /** The model of every chat request, in any dialect (OpenAI, Anthropic or Gemini). */
  chats: string[];
  /** Every Anthropic Messages request body, so specs can check what was sent back. */
  anthropicBodies: any[];
  anthropicUrl: string;
  googleUrl: string;
  /** Simulate an outage: every request fails with 503 while true. */
  down: boolean;
  /** Simulate a very slow model: streamed answers drip one word every few seconds. */
  stuck: boolean;
  /** The Ollama personality pretends no embedding model has been pulled. */
  ollamaNoEmbeddings: boolean;
  ollamaUrl: string;
  bareUrl: string;
  chatOnlyUrl: string;
  close: () => Promise<void>;
};

export async function startFakeLlm(): Promise<FakeLlm> {
  const requests: string[] = [];
  const embedded: string[] = [];
  const chats: string[] = [];
  const anthropicBodies: any[] = [];
  const state = { down: false, ollamaNoEmbeddings: false };

  const server = createServer((req, res) => {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      const body = raw ? JSON.parse(raw) : {};
      requests.push(`${req.method} ${req.url} ${body.model ?? ""}`.trim());
      const send = (status: number, payload: unknown) => {
        res.writeHead(status, { "Content-Type": "application/json" });
        res.end(JSON.stringify(payload));
      };

      if (state.down) {
        return send(503, { error: { message: "The fake provider is down (503)" } });
      }
      // Anthropic and Gemini dialects (spec 0008) live under their own prefixes.
      const path = new URL(req.url ?? "/", "http://fake").pathname;
      if (path.startsWith("/anthropic/")) {
        // The SDK sends the key as x-api-key or (anthropic 2.x) as a Bearer token.
        if (req.headers["x-api-key"] === "bad-key" || req.headers.authorization === "Bearer bad-key") {
          return send(401, { type: "error", error: { type: "authentication_error", message: "invalid x-api-key" } });
        }
        if (path.endsWith("/v1/models")) {
          const data = ANTHROPIC_MODELS.map((id) => ({ type: "model", id, display_name: id, created_at: "2026-01-01T00:00:00Z" }));
          return send(200, { data, has_more: false, first_id: data[0].id, last_id: data.at(-1)!.id });
        }
        if (path.endsWith("/v1/messages")) {
          chats.push(String(body.model));
          anthropicBodies.push(body);
          return anthropic(body, res, send);
        }
      }
      if (path.startsWith("/google/")) {
        if (req.headers["x-goog-api-key"] === "bad-key") {
          return send(400, { error: { code: 400, message: "API key not valid. Please pass a valid API key.", status: "INVALID_ARGUMENT" } });
        }
        const call = /\/models\/([^/:]+):(\w+)$/.exec(path);
        if (!call) return send(200, { models: GOOGLE_MODELS });
        const [, model, method] = call;
        requests.push(`POST ${path} ${model}`);
        if (method.endsWith("GenerateContent") || method === "generateContent") chats.push(model);
        return google(model, method, body, res, send, embedded);
      }
      if (req.headers.authorization === "Bearer bad-key") {
        return send(401, {
          error: { message: "Incorrect API key provided", type: "invalid_request_error" },
        });
      }
      const personality = /^\/(ollama|bare|chat-only)\//.exec(req.url ?? "")?.[1];
      const ollamaIds = Object.keys(OLLAMA_MODELS).filter(
        (id) => !(state.ollamaNoEmbeddings && OLLAMA_MODELS[id].capabilities.includes("embedding")),
      );
      if (personality === "ollama" && req.url?.endsWith("/api/version")) {
        return send(200, { version: "0.12.0-fake" });
      }
      if (personality === "ollama" && req.url?.endsWith("/api/tags")) {
        return send(200, { models: ollamaIds.map((name) => ({ name, model: name })) });
      }
      if (personality === "ollama" && req.url?.endsWith("/api/show")) {
        const model = OLLAMA_MODELS[body.model];
        if (!model) return send(404, { error: `model '${body.model}' not found` });
        return send(200, {
          capabilities: model.capabilities,
          model_info: model.dims ? { "bert.embedding_length": model.dims } : {},
        });
      }
      if (req.url?.endsWith("/models")) {
        const ids =
          personality === "ollama"
            ? ollamaIds
            : personality
              ? PERSONALITY_MODELS[personality]
              : FAKE_MODELS;
        return send(200, {
          object: "list",
          data: ids.map((id) => ({ id, object: "model", owned_by: "fake" })),
        });
      }
      if (req.url?.endsWith("/embeddings")) {
        const inputs: string[] = Array.isArray(body.input) ? body.input : [body.input];
        embedded.push(...inputs);
        const dims = dimensionsOf(String(body.model));
        return send(200, {
          object: "list",
          model: body.model,
          data: inputs.map((text, index) => ({ object: "embedding", index, embedding: embed(text, dims) })),
          usage: { prompt_tokens: 1, total_tokens: 1 },
        });
      }
      if (req.url?.endsWith("/chat/completions")) {
        chats.push(String(body.model));
        return chat(body, res, send);
      }
      send(404, { error: { message: `Fake LLM has no route ${req.url}` } });
    });
  });

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  return {
    baseUrl: `http://127.0.0.1:${port}/v1`,
    ollamaUrl: `http://127.0.0.1:${port}/ollama/v1`,
    bareUrl: `http://127.0.0.1:${port}/bare/v1`,
    chatOnlyUrl: `http://127.0.0.1:${port}/chat-only/v1`,
    anthropicUrl: `http://127.0.0.1:${port}/anthropic`,
    googleUrl: `http://127.0.0.1:${port}/google`,
    requests,
    embedded,
    chats,
    anthropicBodies,
    get ollamaNoEmbeddings() {
      return state.ollamaNoEmbeddings;
    },
    set ollamaNoEmbeddings(value: boolean) {
      state.ollamaNoEmbeddings = value;
    },
    get down() {
      return state.down;
    },
    get stuck() {
      return stuck;
    },
    set stuck(value: boolean) {
      stuck = value;
    },
    set down(value: boolean) {
      state.down = value;
    },
    close: () => new Promise((resolve) => server.close(() => resolve())),
  };
}

// --- one decision, three dialects ---------------------------------------------------------
// What the fake "model" does is decided once, from a neutral view of the conversation
// (OpenAI-style roles: system / user / assistant / tool). Each dialect only translates its
// request into that view and renders the decision in its own wire format.

type Reply =
  | { kind: "tool"; query: string }
  | { kind: "text"; text: string; thinking?: string; delayMs: number }
  | { kind: "error"; status: number; message: string };

/** `stuck` mode (one server per test run, so module state is fine). */
let stuck = false;
const STUCK_DELAY_MS = 3000;

function decide(model: string, messages: Msg[], tools: boolean, stream: boolean): Reply {
  const reply = decideFast(model, messages, tools, stream);
  if (stuck && stream && reply.kind === "text") return { ...reply, delayMs: STUCK_DELAY_MS };
  if (model.includes("slow") && reply.kind === "text") {
    return { ...reply, delayMs: Math.max(reply.delayMs * 10, 150) };
  }
  return reply;
}

function decideFast(model: string, messages: Msg[], tools: boolean, stream: boolean): Reply {
  const last = messages.at(-1);
  if (tools && model.includes("notools")) {
    return { kind: "error", status: 400, message: `registry.ollama.ai/library/${model} does not support tools` };
  }
  // 1) The agent hasn't searched yet → ask for a search with the user's question.
  if (tools && last?.role === "user") return { kind: "tool", query: String(last.content ?? "") };

  // 2) It has search results (tool messages, or passages pasted into the prompt) → answer.
  const answering =
    last?.role === "tool" || (last?.role === "user" && last.content?.includes("Passages from my documents"));
  if (answering) {
    return { kind: "text", text: answerFrom(messages), thinking: "Reading the passages I found. ", delayMs: 40 };
  }
  const prompt = String(last?.content ?? "");
  const system = messages.find((m) => m.role === "system")?.content ?? "";

  // 3) Benchmark judge.
  if (prompt.startsWith("You are grading")) return { kind: "text", text: judgeReply(model, prompt), delayMs: 0 };

  // 4) A bare model (no retrieval) answering a benchmark question.
  if (system.startsWith("Answer the user's question")) {
    const text = model.includes("inventor") ? "It was definitely Brazil, by three goals." : "I don't know that.";
    return { kind: "text", text, delayMs: 20 };
  }
  // 5) A streamed chat turn with nothing to search (spec 0010: the chat picked no embedding,
  //    so no tool is offered) → an honest streamed answer, long if asked for a long one.
  if (stream && !tools && last?.role === "user") return { kind: "text", text: answerFrom(messages), delayMs: 40 };

  // 6) Small helper prompts inside the pipeline (rerank, query rewriting) and Test connection.
  return { kind: "text", text: prompt.includes("JSON array") ? "[0,1,2,3,4,5,6,7,8,9]" : "OK", delayMs: 0 };
}

/** A text as streamed tokens: one word at a time, with the space in front. */
const tokens = (text: string) => text.split(" ").map((w, i) => (i ? " " : "") + w);

/** Write `frames` one every `delayMs`, then `end`. Stops if the client went away (Stop). */
function drip(res: ServerResponse, frames: string[], end: string, delayMs: number) {
  let i = 0;
  const tick = () => {
    if (res.destroyed) return;
    if (i < frames.length) {
      res.write(frames[i++]);
      // A stuck answer speeds up as soon as `stuck` is switched off (spec 0014), so a run
      // left in flight finishes without waiting out its 3 s-per-word drip.
      setTimeout(tick, delayMs === STUCK_DELAY_MS && !stuck ? 20 : delayMs);
    } else {
      res.end(end);
    }
  };
  tick();
}

// --- OpenAI-compatible (/v1/chat/completions) ------------------------------------------------

function chat(body: any, res: ServerResponse, send: (s: number, p: unknown) => void) {
  const model = String(body.model);
  const reply = decide(model, body.messages ?? [], Boolean(body.tools), Boolean(body.stream));
  if (reply.kind === "error") return send(reply.status, { error: { message: reply.message } });
  if (reply.kind === "tool") {
    const call = {
      index: 0,
      id: "call_1",
      type: "function",
      function: { name: "search_documents", arguments: JSON.stringify({ query: reply.query }) },
    };
    if (!body.stream) {
      return send(200, completion(model, { role: "assistant", content: null, tool_calls: [call] }, "tool_calls"));
    }
    return sse(res, model, [{ delta: { role: "assistant", tool_calls: [call] } }], "tool_calls", 0);
  }
  if (!body.stream) return send(200, completion(model, { role: "assistant", content: reply.text }, "stop"));
  const deltas = [
    ...(reply.thinking ? [{ delta: { role: "assistant", reasoning_content: reply.thinking } }] : []),
    ...tokens(reply.text).map((w) => ({ delta: { content: w } })),
  ];
  return sse(res, model, deltas, "stop", reply.delayMs);
}

function completion(model: string, message: object, finish: string) {
  return {
    id: "chatcmpl-fake",
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [{ index: 0, finish_reason: finish, message }],
    usage: { prompt_tokens: 5, completion_tokens: 5, total_tokens: 10 },
  };
}

/** Server-sent events in OpenAI's streaming format, one delta every `delayMs`. */
function sse(res: ServerResponse, model: string, deltas: object[], finish: string, delayMs: number) {
  res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" });
  const frame = (choice: object) =>
    `data: ${JSON.stringify({ id: "chatcmpl-fake", object: "chat.completion.chunk", created: 0, model, choices: [{ index: 0, ...choice }] })}\n\n`;
  drip(res, deltas.map((d) => frame({ ...d, finish_reason: null })), frame({ delta: {}, finish_reason: finish }) + "data: [DONE]\n\n", delayMs);
}

// --- Anthropic Messages (/anthropic/v1/messages) ---------------------------------------------
// Claude always streams a signed thinking block first, as adaptive thinking with display
// "summarized" does. "claude-fake-refuses" declines straight away; "claude-fake-refuses-midway"
// streams a little text and then declines.

const ANTHROPIC_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fake-refuses", "claude-fake-refuses-midway"];

function anthropicView(body: any): Msg[] {
  const system = Array.isArray(body.system) ? body.system.map((b: any) => b.text).join("\n") : body.system;
  const out: Msg[] = system ? [{ role: "system", content: system }] : [];
  for (const m of body.messages ?? []) {
    const blocks = typeof m.content === "string" ? [{ type: "text", text: m.content }] : m.content;
    const text = blocks.filter((b: any) => b.type === "text").map((b: any) => b.text).join("");
    for (const b of blocks.filter((b: any) => b.type === "tool_result")) {
      const content = typeof b.content === "string" ? b.content : (b.content ?? []).map((c: any) => c.text).join("");
      out.push({ role: "tool", content });
    }
    if (text || m.role === "assistant") out.push({ role: m.role, content: text });
  }
  return out;
}

function anthropic(body: any, res: ServerResponse, send: (s: number, p: unknown) => void) {
  const model = String(body.model);
  const message = (content: object[], stop: string) => ({
    id: "msg_fake",
    type: "message",
    role: "assistant",
    model,
    content,
    stop_reason: stop,
    stop_sequence: null,
    usage: { input_tokens: 5, output_tokens: 5 },
  });
  const refuses = model.includes("refuses");
  const reply: Reply = refuses
    ? { kind: "text", text: model.includes("midway") ? "Partial answer, which the model then withdraws." : "", delayMs: 30 }
    : decide(model, anthropicView(body), Boolean(body.tools), Boolean(body.stream));
  if (reply.kind === "error") return send(reply.status, { type: "error", error: { type: "invalid_request_error", message: reply.message } });
  const stop = refuses ? "refusal" : reply.kind === "tool" ? "tool_use" : "end_turn";
  if (!body.stream) {
    const content = reply.kind === "text" && reply.text ? [{ type: "text", text: reply.text }] : [];
    return send(200, message(content, stop));
  }

  res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" });
  const ev = (type: string, data: object) => `event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`;
  const frames = [ev("message_start", { message: message([], null as never) })];
  let index = 0;
  const thinking = reply.kind === "tool" ? "I should search their documents for this. " : (reply.thinking ?? "Thinking about the question. ");
  if (!refuses) {
    frames.push(
      ev("content_block_start", { index, content_block: { type: "thinking", thinking: "", signature: "" } }),
      ev("content_block_delta", { index, delta: { type: "thinking_delta", thinking } }),
      ev("content_block_delta", { index, delta: { type: "signature_delta", signature: `fake-sig-${Buffer.from(thinking).toString("base64")}` } }),
      ev("content_block_stop", { index }),
    );
    index++;
  }
  if (reply.kind === "tool") {
    frames.push(
      ev("content_block_start", { index, content_block: { type: "tool_use", id: "toolu_fake1", name: "search_documents", input: {} } }),
      ev("content_block_delta", { index, delta: { type: "input_json_delta", partial_json: JSON.stringify({ query: reply.query }) } }),
      ev("content_block_stop", { index }),
    );
  } else if (reply.text) {
    frames.push(ev("content_block_start", { index, content_block: { type: "text", text: "" } }));
    for (const w of tokens(reply.text)) frames.push(ev("content_block_delta", { index, delta: { type: "text_delta", text: w } }));
    frames.push(ev("content_block_stop", { index }));
  }
  frames.push(ev("message_delta", { delta: { stop_reason: stop, stop_sequence: null }, usage: { output_tokens: 10 } }));
  drip(res, frames, ev("message_stop", {}), reply.kind === "text" ? reply.delayMs : 0);
}

// --- Gemini (/google/v1beta/models/<model>:<method>) -------------------------------------------

const GOOGLE_MODELS = [
  { name: "models/gemini-fake", supportedGenerationMethods: ["generateContent", "countTokens"] },
  { name: "models/gemini-embed-fake", supportedGenerationMethods: ["embedContent"] },
];

function googleView(body: any): Msg[] {
  const out: Msg[] = [];
  const system = (body.systemInstruction?.parts ?? []).map((p: any) => p.text).join("\n");
  if (system) out.push({ role: "system", content: system });
  for (const c of body.contents ?? []) {
    for (const p of c.parts ?? []) {
      if (p.functionResponse) out.push({ role: "tool", content: String(p.functionResponse.response?.result ?? "") });
    }
    const text = (c.parts ?? []).filter((p: any) => p.text && !p.thought).map((p: any) => p.text).join("");
    if (text || c.role === "model") out.push({ role: c.role === "model" ? "assistant" : "user", content: text });
  }
  return out;
}

function google(model: string, method: string, body: any, res: ServerResponse, send: (s: number, p: unknown) => void, embedded: string[]) {
  if (method === "batchEmbedContents" || method === "embedContent") {
    const requests = method === "embedContent" ? [body] : body.requests ?? [];
    const texts = requests.map((r: any) => (r.content?.parts ?? []).map((p: any) => p.text).join(""));
    embedded.push(...texts);
    const values = texts.map((t: string) => ({ values: embed(t, dimensionsOf(model)) }));
    return send(200, method === "embedContent" ? { embedding: values[0] } : { embeddings: values });
  }
  const stream = method === "streamGenerateContent";
  const reply = decide(model, googleView(body), Boolean(body.tools?.length), stream);
  if (reply.kind === "error") return send(reply.status, { error: { code: reply.status, message: reply.message, status: "INVALID_ARGUMENT" } });
  const chunk = (parts: object[], finish?: string) => ({
    candidates: [{ content: { role: "model", parts }, ...(finish ? { finishReason: finish } : {}), index: 0 }],
  });
  const thought = { text: reply.kind === "tool" ? "I should search their documents. " : (reply.thinking ?? "Thinking. "), thought: true };
  if (reply.kind === "tool") {
    const call = { functionCall: { id: "fc_fake1", name: "search_documents", args: { query: reply.query } }, thoughtSignature: "ZmFrZS1zaWc=" };
    const out = chunk([thought, call], "STOP");
    if (!stream) return send(200, out);
    res.writeHead(200, { "Content-Type": "text/event-stream" });
    return res.end(`data: ${JSON.stringify(out)}\r\n\r\n`);
  }
  if (!stream) return send(200, chunk([{ text: reply.text }], "STOP"));
  res.writeHead(200, { "Content-Type": "text/event-stream" });
  const frames = [`data: ${JSON.stringify(chunk([thought]))}\r\n\r\n`, ...tokens(reply.text).map((w) => `data: ${JSON.stringify(chunk([{ text: w }]))}\r\n\r\n`)];
  drip(res, frames, `data: ${JSON.stringify(chunk([{ text: "" }], "STOP"))}\r\n\r\n`, reply.delayMs);
}
