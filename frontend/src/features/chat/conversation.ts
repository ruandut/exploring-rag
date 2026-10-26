import type { RetrievedChunk, ServerEvent } from "@/lib/socket";

export type AssistantTurn = {
  role: "assistant";
  runId: string | null; // null until the server replies with agent.started
  agentId: string;
  thinking: string;
  toolCalls: { tool: string; args: Record<string, unknown> }[];
  retrieved: RetrievedChunk[];
  text: string;
  status: "pending" | "streaming" | "done" | "cancelled" | "error";
  error?: string;
  model?: string; // e.g. "Ollama (local) · gemma4:e4b", set when the run finishes
  agentName?: string;
  embeddingName?: string; // "" = no embedding was searched; undefined = not recorded
};

export type Turn = { role: "user"; text: string } | AssistantTurn;

export type Action =
  | { kind: "ask"; text: string; agentId: string; agentName?: string; embeddingName?: string }
  | { kind: "load"; turns: Turn[] }
  | { kind: "event"; event: ServerEvent };

/** Fold websocket agent.* events into the conversation. */
export function conversationReducer(turns: Turn[], action: Action): Turn[] {
  if (action.kind === "load") return action.turns;
  if (action.kind === "ask") {
    return [
      ...turns,
      { role: "user", text: action.text },
      {
        role: "assistant",
        runId: null,
        agentId: action.agentId,
        agentName: action.agentName,
        embeddingName: action.embeddingName,
        thinking: "",
        toolCalls: [],
        retrieved: [],
        text: "",
        status: "pending",
      },
    ];
  }

  const e = action.event;
  if (!e.type.startsWith("agent.") || !("run_id" in e)) return turns;

  // agent.started binds the run id to the oldest assistant turn still waiting for one.
  const index =
    e.type === "agent.started"
      ? turns.findIndex((t) => t.role === "assistant" && t.runId === null)
      : turns.findIndex((t) => t.role === "assistant" && t.runId === e.run_id);
  if (index === -1) return turns;

  const turn = turns[index] as AssistantTurn;
  const next: AssistantTurn = { ...turn };
  switch (e.type) {
    case "agent.started":
      next.runId = e.run_id;
      next.status = "streaming";
      break;
    case "agent.thinking":
      next.thinking += e.text;
      break;
    case "agent.tool_call":
      next.toolCalls = [...turn.toolCalls, { tool: e.tool, args: e.args }];
      break;
    case "agent.retrieval":
      next.retrieved = [...turn.retrieved, ...e.chunks];
      break;
    case "agent.token":
      next.text += e.text;
      break;
    case "agent.done":
      next.status = "done";
      next.model = e.model;
      break;
    case "agent.cancelled":
      next.status = "cancelled";
      break;
    case "agent.error":
      next.status = "error";
      next.error = e.detail;
      // A failed answer (an outage, or a model that declined part-way) isn't shown as if it
      // were half an answer. Stop is different: agent.cancelled keeps the partial text.
      next.text = "";
      break;
  }
  return turns.with(index, next);
}
