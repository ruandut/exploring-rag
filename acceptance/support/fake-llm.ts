// A tiny OpenAI-compatible server so specs are deterministic and free. It implements what the
// app calls: models, embeddings and chat completions (plain, streamed, and with tool calls).
//
// - API key "bad-key" → 401 with OpenAI's error shape, like a real provider.
// - Any model with "notools" in its name rejects `tools` the way Ollama does for models
//   without tool support (400 "... does not support tools").
// - Judge prompts ("You are grading…") get JSON scores: model "fake-judge-0.8" always scores 0.8;
//   otherwise refusal_rate is 1 only if the answer admits it doesn't know, and the rest score 1.
// - Bare-model prompts: "fake-inventor" confidently makes things up; others say "I don't know".
// - `down = true` makes every request fail with 503, like a provider outage.
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
export const FAKE_MODELS = ["fake-chat", "fake-embed", "fake-local", "fake-notools"];

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
  /** Simulate an outage: every request fails with 503 while true. */
  down: boolean;
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
    requests,
    embedded,
    get ollamaNoEmbeddings() {
      return state.ollamaNoEmbeddings;
    },
    set ollamaNoEmbeddings(value: boolean) {
      state.ollamaNoEmbeddings = value;
    },
    get down() {
      return state.down;
    },
    set down(value: boolean) {
      state.down = value;
    },
    close: () => new Promise((resolve) => server.close(() => resolve())),
  };
}

function chat(body: any, res: ServerResponse, send: (s: number, p: unknown) => void) {
  const messages: Msg[] = body.messages ?? [];
  const last = messages.at(-1);
  if (body.tools && String(body.model).includes("notools")) {
    return send(400, {
      error: { message: `registry.ollama.ai/library/${body.model} does not support tools` },
    });
  }

  // 1) The agent hasn't searched yet → ask for a search with the user's question.
  if (body.tools && last?.role === "user") {
    const call = {
      index: 0,
      id: "call_1",
      type: "function",
      function: { name: "search_documents", arguments: JSON.stringify({ query: last.content }) },
    };
    if (!body.stream) {
      return send(200, completion(body.model, { role: "assistant", content: null, tool_calls: [call] }, "tool_calls"));
    }
    return sse(res, body.model, [{ delta: { role: "assistant", tool_calls: [call] } }], "tool_calls", 0);
  }

  // 2) It has search results (tool messages, or passages pasted into the prompt) → answer.
  const answering =
    last?.role === "tool" || (last?.role === "user" && last.content?.includes("Passages from my documents"));
  if (answering) {
    const words = answerFrom(messages).split(" ");
    if (!body.stream) {
      return send(200, completion(body.model, { role: "assistant", content: words.join(" ") }, "stop"));
    }
    const deltas = [
      { delta: { role: "assistant", reasoning_content: "Reading the passages I found. " } },
      ...words.map((w, i) => ({ delta: { content: (i ? " " : "") + w } })),
    ];
    return sse(res, body.model, deltas, "stop", 40);
  }

  const prompt = String(last?.content ?? "");
  const system = messages.find((m) => m.role === "system")?.content ?? "";

  // 3) Benchmark judge.
  if (prompt.startsWith("You are grading")) {
    return send(200, completion(body.model, { role: "assistant", content: judgeReply(String(body.model), prompt) }, "stop"));
  }

  // 4) A bare model (no retrieval) answering a benchmark question.
  if (system.startsWith("Answer the user's question")) {
    const reply = String(body.model).includes("inventor")
      ? "It was definitely Brazil, by three goals."
      : "I don't know that.";
    if (!body.stream) return send(200, completion(body.model, { role: "assistant", content: reply }, "stop"));
    return sse(res, body.model, reply.split(" ").map((w, i) => ({ delta: { content: (i ? " " : "") + w } })), "stop", 20);
  }

  // 5) A streamed chat turn with nothing to search (spec 0010: the chat picked no embedding,
  //    so no tool is offered) → an honest streamed answer, long if asked for a long one.
  if (body.stream && !body.tools && last?.role === "user") {
    const words = answerFrom(messages).split(" ");
    return sse(res, body.model, words.map((w, i) => ({ delta: { content: (i ? " " : "") + w } })), "stop", 40);
  }

  // 6) Small helper prompts inside the pipeline (rerank, query rewriting) and Test connection.
  const reply = prompt.includes("JSON array") ? "[0,1,2,3,4,5,6,7,8,9]" : "OK";
  if (body.stream) return sse(res, body.model, [{ delta: { role: "assistant", content: reply } }], "stop", 0);
  send(200, completion(body.model, { role: "assistant", content: reply }, "stop"));
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
  let i = 0;
  const tick = () => {
    if (res.destroyed) return; // client went away (e.g. the user pressed Stop)
    if (i < deltas.length) {
      res.write(frame({ ...deltas[i++], finish_reason: null }));
      setTimeout(tick, delayMs);
    } else {
      res.write(frame({ delta: {}, finish_reason: finish }));
      res.end("data: [DONE]\n\n");
    }
  };
  tick();
}
