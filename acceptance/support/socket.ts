// Execution layer for the websocket: a test client that records every event it receives.
import WebSocket from "ws";

import { APP_URL } from "./env.ts";

export type Received = { type: string; [key: string]: unknown };

export class SocketClient {
  ws: WebSocket;
  events: Received[] = [];
  closeCode: number | null = null;

  private constructor(ws: WebSocket) {
    this.ws = ws;
    ws.on("message", (data) => this.events.push(JSON.parse(String(data))));
    ws.on("close", (code) => (this.closeCode = code));
  }

  static async open(): Promise<SocketClient> {
    const url = new URL("/ws/events/", APP_URL);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    // Channels rejects sockets without an Origin header, like a browser would send.
    const ws = new WebSocket(url, { origin: new URL(APP_URL).origin });
    await new Promise<void>((resolve, reject) => {
      ws.once("open", () => resolve());
      ws.once("error", reject);
    });
    return new SocketClient(ws);
  }

  send(message: object): void {
    this.ws.send(JSON.stringify(message));
  }

  /** Wait until an event matching `predicate` has arrived (or time out). */
  async waitFor(predicate: (e: Received) => boolean, timeoutMs = 15_000): Promise<Received> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const found = this.events.find(predicate);
      if (found) return found;
      await new Promise((r) => setTimeout(r, 50));
    }
    throw new Error(`Timed out; received: ${this.events.map((e) => e.type).join(", ")}`);
  }

  async waitForClose(timeoutMs = 5_000): Promise<number> {
    const deadline = Date.now() + timeoutMs;
    while (this.closeCode === null && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 50));
    }
    if (this.closeCode === null) throw new Error("Socket was not closed");
    return this.closeCode;
  }

  close(): void {
    this.ws.close();
  }
}
