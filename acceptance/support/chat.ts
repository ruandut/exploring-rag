// Execution layer for chats that don't go through the browser (e.g. another user's).
import type { ApiClient } from "./app.ts";
import { SocketClient } from "./socket.ts";

/** Ask the demo agent (canned stream, no LLM) over a socket; returns the conversation id once
 *  the reply is saved. */
export async function startConversation(api: ApiClient, message: string): Promise<number> {
  const socket = await SocketClient.open();
  try {
    socket.send({ type: "auth", token: api.accessToken });
    await socket.waitFor((e) => e.type === "auth.ok");
    socket.send({ type: "agent.ask", agent_id: "demo", message });
    const started = await socket.waitFor((e) => e.type === "agent.started");
    await socket.waitFor((e) => e.type === "agent.done", 30_000);
    return started.conversation_id as number;
  } finally {
    socket.close();
  }
}

/** Assistant messages saved for a run — straight from the database, because once a chat is
 *  deleted there's no API left to ask. */
export function savedRepliesForRun(runDjango: (code: string) => string, runId: string): number {
  return Number(
    runDjango(
      `from apps.chat.models import Message; print(Message.objects.filter(run_id=${JSON.stringify(runId)}).count())`,
    ),
  );
}
