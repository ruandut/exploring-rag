import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import { useEffect, useReducer, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { modelLabel, pipelineLabel, useAgents, useConnections } from "@/features/agents/api";
import {
  type ConversationSummary,
  fetchConversation,
  toTurns,
  useConversations,
  useDeleteConversation,
} from "@/features/chat/api";
import { AssistantMessage } from "@/features/chat/assistant-message";
import { EmbeddingPicker, type ModelChoice, ModelPicker } from "@/features/chat/chat-pickers";
import { Composer } from "@/features/chat/composer";
import { DeleteConversationDialog } from "@/features/chat/delete-conversation-dialog";
import { type AssistantTurn, conversationReducer } from "@/features/chat/conversation";
import { embeddingSummary, useEmbeddings } from "@/features/embeddings/api";
import { useProviderConfig } from "@/features/settings/api";
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

type Picks = {
  for: number | null;
  embeddingId?: number | null;
  embeddingGone?: boolean;
  model?: ModelChoice;
};

const DEMO = { id: "demo", name: "Demo agent", description: "Canned stream — no LLM needed" };

function ChatPage() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const queryClient = useQueryClient();
  const agents = useAgents();
  const conversations = useConversations();
  const embeddings = useEmbeddings();
  const connections = useConnections();
  const provider = useProviderConfig();

  const options = [
    ...(agents.data ?? []).map((a) => ({
      id: String(a.id),
      name: a.name,
      description: pipelineLabel(a),
    })),
    DEMO,
  ];
  const [agentId, setAgentId] = useState<string | null>(search.agent ?? null);
  const effectiveAgent = agentId ?? options[0]?.id ?? DEMO.id;

  // Spec 0010: a chat picks an embedding (what to search; null = nothing) and a model next to
  // the agent. undefined = not picked yet: a new chat starts with the ones you used last.
  const last = conversations.data?.[0];
  // The picks belong to one conversation (null = a new chat); opening another one starts
  // from its own saved choices, so stale picks are simply ignored instead of reset.
  const [picks, setPicks] = useState<Picks>({ for: null });
  const own = picks.for === (search.c ?? null) ? picks : { for: search.c ?? null };
  const embeddingId = own.embeddingId;
  const modelChoice = own.model;
  // The open chat's embedding was deleted and nothing else has been picked yet.
  const embeddingGone = !!own.embeddingGone;
  const pick = (change: Omit<Picks, "for">) =>
    setPicks({ ...own, ...change, for: search.c ?? null });
  const effectiveEmbedding =
    embeddingId !== undefined
      ? embeddingId
      : last && !last.embedding_deleted
        ? last.embedding
        : (embeddings.data?.[0]?.id ?? null);
  const effectiveModel: ModelChoice =
    modelChoice ??
    (last ? { connection: last.connection, model: last.model } : { connection: null, model: "" });
  const chosenEmbedding = embeddings.data?.find((e) => e.id === effectiveEmbedding);
  const connectionName =
    effectiveModel.connection === null
      ? null
      : (connections.data?.find((c) => c.id === effectiveModel.connection)?.name ?? "Connection");
  const chosenModelLabel = modelLabel(
    connectionName,
    effectiveModel.model,
    provider.data?.chat_model ?? "",
  );
  const agentName = options.find((a) => a.id === effectiveAgent)?.name ?? "Agent";

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
        setPicks({
          for: id,
          embeddingId: detail.embedding,
          embeddingGone: detail.embedding_deleted,
          model: { connection: detail.connection, model: detail.model },
        });
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
      // The new chat's picks now belong to its id.
      setPicks((p) => (p.for === null ? { ...p, for: event.conversation_id! } : p));
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
    if (embeddingGone) {
      toast.error("This chat's embedding was deleted — pick another (or None) first.");
      return;
    }
    try {
      socket.send({
        type: "agent.ask",
        agent_id: effectiveAgent,
        message: text,
        conversation_id: current.current,
        embedding_id: effectiveEmbedding,
        connection_id: effectiveModel.connection,
        model: effectiveModel.model,
      });
    } catch {
      toast.error("Not connected — waiting for the websocket to reconnect.");
      return;
    }
    dispatch({
      kind: "ask",
      text,
      agentId: effectiveAgent,
      agentName,
      embeddingName: chosenEmbedding?.name ?? "",
    });
    setDraft("");
  }

  const settingsLine = (
    <p aria-label="Chat settings" className="truncate text-xs text-muted-foreground">
      {agentName} · Embedding:{" "}
      {embeddingGone ? (
        <span className="text-destructive">Embedding deleted — pick another</span>
      ) : chosenEmbedding ? (
        `${chosenEmbedding.name} (${embeddingSummary(chosenEmbedding)})`
      ) : (
        "None"
      )}{" "}
      · Model: {chosenModelLabel}
    </p>
  );

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
      pickers={
        <>
          <EmbeddingPicker
            embeddings={embeddings.data ?? []}
            value={embeddingGone ? null : effectiveEmbedding}
            onChange={(id) => pick({ embeddingId: id, embeddingGone: false })}
          />
          <ModelPicker
            connections={connections.data ?? []}
            defaultChatModel={provider.data?.chat_model ?? ""}
            value={effectiveModel}
            onChange={(model) => pick({ model })}
          />
        </>
      }
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
              <div className="mt-2">{settingsLine}</div>
            </div>
            <div className="w-full max-w-2xl">{composer(true)}</div>
          </div>
        ) : (
          <>
            <div className="border-b px-4 py-2">
              <div className="mx-auto max-w-3xl">{settingsLine}</div>
            </div>
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
