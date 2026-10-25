// One websocket per tab to /ws/events/. Server-pushed events fan out to subscribers.
// The event contract mirrors CLAUDE.md "Websocket event contract" — keep them in sync.

import { getAccessToken, refreshAccessToken } from "./auth";

export type RetrievedChunk = { document: string; chunk: number; score: number; text: string };

export type ServerEvent =
  | { type: "auth.ok"; user: { id: number; username: string } }
  | { type: "auth.error"; detail: string }
  | { type: "pong" }
  | { type: "error"; detail: string }
  | {
      type: "job.progress";
      run_id: string;
      job: string;
      step: number;
      total: number;
      message: string;
    }
  | { type: "job.completed"; run_id: string; job: string; message?: string }
  | {
      type: "document.status";
      document_id: number;
      folder_id: number | null;
      status: "queued" | "indexing" | "ready" | "failed" | "not_indexed";
      error: string;
      chunk_count: number;
    }
  | {
      // One embedding's indexing progress (spec 0010). done counts ready + failed documents.
      type: "embedding.status";
      embedding_id: number;
      status: "indexing" | "ready" | "failed";
      done: number;
      total: number;
      error?: string;
    }
  | { type: "benchmark.progress"; run_id: number; done: number; total: number }
  | {
      type: "benchmark.case";
      run_id: number;
      result_id: number;
      status: "pending" | "done" | "failed";
      passed: boolean | null;
    }
  | { type: "benchmark.completed"; run_id: number; status: "running" | "passed" | "failed" }
  | { type: "agent.started"; run_id: string; conversation_id?: number }
  | { type: "agent.thinking"; run_id: string; text: string }
  | { type: "agent.tool_call"; run_id: string; tool: string; args: Record<string, unknown> }
  | { type: "agent.retrieval"; run_id: string; chunks: RetrievedChunk[] }
  | { type: "agent.token"; run_id: string; text: string }
  | {
      type: "agent.done";
      run_id: string;
      model?: string;
      // pipeline: the model can't call tools; model: no embedding chosen, nothing searched
      mode?: "agentic" | "pipeline" | "model";
    }
  | { type: "agent.cancelled"; run_id: string }
  | { type: "agent.error"; run_id: string; detail: string };

export type ClientMessage =
  | { type: "ping" }
  | {
      type: "agent.ask";
      agent_id: string;
      message: string;
      conversation_id?: number | null;
      // Spec 0010: what to search (null = nothing) and which model answers (connection null =
      // the default provider, model "" = its chat model). Applies from this message on.
      embedding_id?: number | null;
      connection_id?: number | null;
      model?: string;
    }
  | { type: "agent.cancel"; run_id: string };

export type SocketStatus = "idle" | "connecting" | "open" | "closed";

type Listener = (event: ServerEvent) => void;

const CLOSE_UNAUTHENTICATED = 4401;

class EventSocket {
  private ws: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private statusListeners = new Set<(s: SocketStatus) => void>();
  private retry = 0;
  private stopped = true;
  private refreshedForThisAttempt = false;
  status: SocketStatus = "idle";

  start() {
    if (!this.stopped) return;
    this.stopped = false;
    this.open();
  }

  stop() {
    this.stopped = true;
    this.ws?.close();
    this.ws = null;
    this.setStatus("idle");
  }

  send(message: ClientMessage) {
    if (this.ws?.readyState !== WebSocket.OPEN || this.status !== "open") {
      throw new Error("Socket is not connected");
    }
    this.ws.send(JSON.stringify(message));
  }

  subscribe(listener: Listener) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  onStatus(listener: (s: SocketStatus) => void) {
    this.statusListeners.add(listener);
    return () => {
      this.statusListeners.delete(listener);
    };
  }

  private setStatus(status: SocketStatus) {
    this.status = status;
    this.statusListeners.forEach((l) => l(status));
  }

  private open() {
    this.setStatus("connecting");
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${scheme}://${location.host}/ws/events/`);
    this.ws = ws;

    // Browsers can't set an Authorization header on websockets, so the JWT goes in the
    // first message (never the URL, which ends up in logs).
    ws.onopen = () => ws.send(JSON.stringify({ type: "auth", token: getAccessToken() }));

    ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data as string) as ServerEvent;
      if (event.type === "auth.ok") {
        this.retry = 0;
        this.refreshedForThisAttempt = false;
        this.setStatus("open");
      }
      this.listeners.forEach((l) => l(event));
    };

    ws.onclose = async (e) => {
      if (this.ws !== ws) return;
      this.setStatus("closed");
      if (this.stopped) return;
      // Expired access token: refresh once, then reconnect immediately.
      if (e.code === CLOSE_UNAUTHENTICATED && !this.refreshedForThisAttempt) {
        this.refreshedForThisAttempt = true;
        if (await refreshAccessToken()) return this.open();
        return;
      }
      const delay = Math.min(1000 * 2 ** this.retry++, 15000);
      setTimeout(() => !this.stopped && this.open(), delay);
    };
  }
}

export const socket = new EventSocket();
