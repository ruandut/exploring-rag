import { createFileRoute, Link } from "@tanstack/react-router";
import { Bot, MessageSquare, MoreHorizontal, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { AgentForm } from "@/features/agents/agent-form";
import {
  type Agent,
  pipelineLabel,
  useAgents,
  useDeleteAgent,
  useSaveAgent,
} from "@/features/agents/api";
import { GENERATION, QUERY_TRANSFORMS, RETRIEVAL } from "@/features/agents/options";
import { ConfirmDialog } from "@/features/library/confirm-dialog";

export const Route = createFileRoute("/_app/agents")({
  staticData: { title: "Agents" },
  component: AgentsPage,
});

const label = (options: { value: string; label: string }[], value: string) =>
  options.find((o) => o.value === value)?.label ?? value;

function AgentsPage() {
  const agents = useAgents();
  const save = useSaveAgent();
  const remove = useDeleteAgent();
  const [editing, setEditing] = useState<Agent | "new" | null>(null);
  const [deleting, setDeleting] = useState<Agent | null>(null);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="max-w-2xl text-sm text-muted-foreground">
          An agent is a system message and a RAG pipeline. In Chat you pick it together with an
          embedding (what to search) and a model (what answers).
        </p>
        <Button onClick={() => setEditing("new")}>
          <Plus className="size-4" /> New agent
        </Button>
      </div>

      {agents.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : agents.data?.length ? (
        <ul aria-label="Agents" className="grid gap-4 md:grid-cols-2">
          {agents.data.map((agent) => (
            <li key={agent.id}>
              <Card className="h-full gap-3">
                <CardHeader className="flex flex-row items-start justify-between gap-2">
                  <div className="grid min-w-0 gap-1">
                    <CardTitle className="flex items-center gap-2">
                      <Bot className="size-4 shrink-0" /> {agent.name}
                    </CardTitle>
                    <CardDescription className="truncate">{pipelineLabel(agent)}</CardDescription>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        aria-label={`Actions for ${agent.name}`}
                      >
                        <MoreHorizontal className="size-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => setEditing(agent)}>Edit</DropdownMenuItem>
                      <DropdownMenuItem variant="destructive" onClick={() => setDeleting(agent)}>
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </CardHeader>
                <CardContent className="grid gap-3 text-sm">
                  {agent.system_message && (
                    <p className="line-clamp-2 text-muted-foreground">{agent.system_message}</p>
                  )}
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="secondary">
                      {label(RETRIEVAL, agent.rag_config.retrieval)}
                    </Badge>
                    <Badge variant="secondary">top-{agent.rag_config.top_k}</Badge>
                    {agent.rag_config.query_transform !== "none" && (
                      <Badge variant="secondary">
                        {label(QUERY_TRANSFORMS, agent.rag_config.query_transform)}
                      </Badge>
                    )}
                    {agent.rag_config.rerank !== "none" && (
                      <Badge variant="secondary">LLM rerank</Badge>
                    )}
                    <Badge variant="secondary">
                      {label(GENERATION, agent.rag_config.generation)}
                    </Badge>
                  </div>
                  <Button asChild variant="outline" size="sm" className="w-fit">
                    <Link to="/chat" search={{ agent: String(agent.id) }}>
                      <MessageSquare className="size-4" /> Chat
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
            <Bot className="size-6" />
            <p className="text-sm">No agents yet. Create one to chat with your documents.</p>
          </CardContent>
        </Card>
      )}

      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>
              {editing === "new" ? "New agent" : `Edit ${editing?.name ?? ""}`}
            </SheetTitle>
            <SheetDescription>
              Every option is explained on the System design page.
            </SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-6">
            {editing !== null && (
              <AgentForm
                key={editing === "new" ? "new" : editing.id}
                agent={editing === "new" ? null : editing}
                pending={save.isPending}
                error={save.error}
                onCancel={() => setEditing(null)}
                onSubmit={(input) =>
                  save.mutate(
                    { ...input, id: editing === "new" ? undefined : editing.id },
                    {
                      onSuccess: (saved) => {
                        toast.success(`Saved ${saved.name}`);
                        save.reset();
                        setEditing(null);
                      },
                    },
                  )
                }
              />
            )}
          </div>
        </SheetContent>
      </Sheet>

      {deleting && (
        <ConfirmDialog
          title={`Delete ${deleting.name}?`}
          description="Its conversations are kept but can't be continued with this agent."
          confirmLabel="Delete agent"
          onCancel={() => setDeleting(null)}
          onConfirm={() => {
            remove.mutate(deleting.id, { onSuccess: () => toast.success("Agent deleted") });
            setDeleting(null);
          }}
        />
      )}
    </div>
  );
}
