import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import { useEffect, useReducer, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { modelLabel, useAgents } from "@/features/agents/api";
import {
  type ConversationSummary,
  fetchConversation,
  toTurns,
  useConversations,
  useDeleteConversation,
} from "@/features/chat/api";
import { AssistantMessage } from "@/features/chat/assistant-message";
import { Composer } from "@/features/chat/composer";
import { DeleteConversationDialog } from "@/features/chat/delete-conversation-dialog";
import { type AssistantTurn, conversationReducer } from "@/features/chat/conversation";
import { useSocketEvents, useSocketStatus } from "@/hooks/use-socket";
import { socket } from "@/lib/socket";
import { cn } from "@/lib/utils";

type Search = { c?: number; agent?: string };

export const Route = createFileRoute("/_app/chat")({
  staticData: { title: "Chat" },
  // ?c=<conversation id> survives reloads; ?agent=<id> preselects an agent (from Agents page).
  validateSearch: (search: Record<string, unknown>): Search => {
    const c = Number(search.c);
    return {
      ...(Number.isInteger(c) && c > 0 ? { c } : {}),
      ...(typeof search.agent === "string" ? { agent: search.agent } : {}),
    };
  },
  component: ChatPage,
});

const DEMO = { id: "demo", name: "Demo agent", description: "Canned stream — no LLM needed" };

function ChatPage() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const queryClient = useQueryClient();
  const agents = useAgents();
  const conversations = useConversations();

  const options = [
    ...(agents.data ?? []).map((a) => ({
      id: String(a.id),
      name: a.name,
      description: modelLabel(a),
    })),
    DEMO,
  ];
  const [agentId, setAgentId] = useState<string | null>(search.agent ?? null);
  const effectiveAgent = agentId ?? options[0]?.id ?? DEMO.id;

  const [turns, dispatch] = useReducer(conversationReducer, []);
  const [draft, setDraft] = useState("");
  const status = useSocketStatus();
  const bottom = useRef<HTMLDivElement>(null);
  // The conversation these turns belong to. Kept in a ref so a URL change we made ourselves
  // (after the server assigns an id) doesn't reload and wipe the live stream.
  const current = useRef<number | null>(null);
  // Conversations deleted in this tab. A run that was still starting can report agent.started
  // for one of them afterwards; following it would navigate back to a chat that's gone.
  const deleted = useRef(new Set<number>());
  const [toDelete, setToDelete] = useState<ConversationSummary | null>(null);
  const deleteConversation = useDeleteConversation();

  useEffect(() => {
    const id = search.c ?? null;
    if (id === current.current) return;
    current.current = id;
    if (id === null) {
      dispatch({ kind: "load", turns: [] });
      return;
    }
    fetchConversation(id)
      .then((detail) => {
        if (current.current !== id) return;
        dispatch({ kind: "load", turns: toTurns(detail) });
        setAgentId(detail.agent_key);
      })
      .catch(() => toast.error("Couldn't open that conversation"));
  }, [search.c]);

  useSocketEvents((event) => {
    if (
      event.type === "agent.started" &&
      event.conversation_id &&
      current.current === null &&
      !deleted.current.has(event.conversation_id)
    ) {
      current.current = event.conversation_id;
      void navigate({ search: { c: event.conversation_id }, replace: true });
    }
    if (
      // started: a new chat appears in the list (and can be deleted) while it is answering
      event.type === "agent.started" ||
      event.type === "agent.done" ||
      event.type === "agent.cancelled" ||
      event.type === "agent.error"
    ) {
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
    }
    dispatch({ kind: "event", event });
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [turns]);

  const active = turns.findLast(
    (t): t is AssistantTurn =>
      t.role === "assistant" && (t.status === "pending" || t.status === "streaming"),
  );

  function ask() {
    const text = draft.trim();
    if (!text || active) return;
    try {
      socket.send({
        type: "agent.ask",
        agent_id: effectiveAgent,
        message: text,
        conversation_id: current.current,
      });
    } catch {
      toast.error("Not connected — waiting for the websocket to reconnect.");
      return;
    }
    dispatch({ kind: "ask", text, agentId: effectiveAgent });
    setDraft("");
  }

  function stop() {
    if (active?.runId) socket.send({ type: "agent.cancel", run_id: active.runId });
  }

  function confirmDelete(target: ConversationSummary) {
    setToDelete(null);
    deleted.current.add(target.id);
    deleteConversation.mutate(target.id, {
      onSuccess: () => {
        // Deleting the open chat: drop its turns (incl. a reply still streaming — the server
        // has cancelled the run) and go back to an empty chat.
        if (current.current === target.id) {
          current.current = null;
          dispatch({ kind: "load", turns: [] });
          void navigate({ search: {} });
        }
        toast.success("Chat deleted");
      },
      onError: () => {
        deleted.current.delete(target.id);
        toast.error("Couldn't delete that chat");
      },
    });
  }

  const composer = (autoFocus: boolean) => (
    <Composer
      draft={draft}
      onDraft={setDraft}
      onSend={ask}
      onStop={stop}
      streaming={!!active}
      canStop={!!active?.runId}
      connected={status === "open"}
      agents={options}
      agentId={effectiveAgent}
      onAgent={setAgentId}
      autoFocus={autoFocus}
    />
  );

  return (
    <div className="flex min-h-0 flex-1">
      <aside className="hidden w-60 shrink-0 flex-col border-r lg:flex">
        <div className="p-2">
          <Button asChild variant="outline" className="w-full justify-start">
            <Link to="/chat" search={{}}>
              <MessageSquarePlus className="size-4" /> New chat
            </Link>
          </Button>
        </div>
        <nav
          aria-label="Conversations"
          className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-2 pb-2"
        >
          <ul className="grid gap-0.5">
            {conversations.data?.map((c) => (
              <li key={c.id} className="group relative">
                <Link
                  to="/chat"
                  search={{ c: c.id }}
                  className={cn(
                    "block rounded-md py-1.5 pr-8 pl-2 text-sm hover:bg-muted",
                    search.c === c.id && "bg-muted font-medium",
                  )}
                >
                  <span className="block truncate">{c.title}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {c.agent_name}
                  </span>
                </Link>
                {/* A sibling of the link, not inside it: a button nested in an <a> is invalid
                    and screen readers would read both as one control. Shown on hover/focus. */}
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Delete "${c.title}"`}
                  title="Delete chat"
                  onClick={() => setToDelete(c)}
                  className="absolute top-1/2 right-1 size-7 -translate-y-1/2 text-muted-foreground opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                >
                  <Trash2 className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
          {conversations.data?.length === 0 && (
            <p className="px-2 py-4 text-xs text-muted-foreground">
              Your conversations appear here.
            </p>
          )}
        </nav>
      </aside>
      {toDelete && (
        <DeleteConversationDialog
          title={toDelete.title}
          onConfirm={() => confirmDelete(toDelete)}
          onCancel={() => setToDelete(null)}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {turns.length === 0 ? (
          // Empty chat: greeting and composer centred, like Claude's start screen.
          <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 pb-[12vh]">
            <div className="text-center">
              <h2 className="text-2xl font-semibold tracking-tight">
                {options.find((a) => a.id === effectiveAgent)?.name ?? "Ask the agent"}
              </h2>
              <p className="mt-1.5 text-sm text-muted-foreground">
                Watch it think, search your documents and answer — live.
              </p>
            </div>
            <div className="w-full max-w-2xl">{composer(true)}</div>
          </div>
        ) : (
          <>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
                {turns.map((turn, i) =>
                  turn.role === "user" ? (
                    <div
                      key={i}
                      className="ml-auto max-w-[85%] rounded-2xl bg-muted px-4 py-2.5 whitespace-pre-wrap"
                    >
                      {turn.text}
                    </div>
                  ) : (
                    <AssistantMessage key={i} turn={turn} />
                  ),
                )}
                <div ref={bottom} />
              </div>
            </div>
            <div className="px-4 pt-1 pb-4">
              <div className="mx-auto max-w-3xl">{composer(false)}</div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
