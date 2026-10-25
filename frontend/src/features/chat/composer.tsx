import { Link } from "@tanstack/react-router";
import { ArrowUp, Bot, Square } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export type AgentOption = { id: string; name: string; description: string };

/** The message box, laid out like Claude's: one rounded card with an auto-growing text area
 *  on top and a toolbar row inside it — embedding, model and agent pickers and send / stop on
 *  the right. */
export function Composer({
  draft,
  onDraft,
  onSend,
  onStop,
  streaming,
  canStop,
  connected,
  agents,
  agentId,
  onAgent,
  pickers,
  autoFocus,
}: {
  draft: string;
  onDraft: (text: string) => void;
  onSend: () => void;
  onStop: () => void;
  streaming: boolean;
  canStop: boolean;
  connected: boolean;
  agents: AgentOption[];
  agentId: string;
  onAgent: (id: string) => void;
  /** Extra pickers shown before the agent picker (embedding, model). */
  pickers?: ReactNode;
  autoFocus?: boolean;
}) {
  const agent = agents.find((a) => a.id === agentId);

  return (
    <form
      className="w-full"
      onSubmit={(e) => {
        e.preventDefault();
        onSend();
      }}
    >
      <div
        className={cn(
          "rounded-2xl border bg-card shadow-sm transition-[border-color,box-shadow]",
          "focus-within:border-ring/50 focus-within:shadow-md",
        )}
      >
        <Textarea
          aria-label="Message"
          autoFocus={autoFocus}
          value={draft}
          onChange={(e) => onDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              onSend();
            }
          }}
          placeholder={
            connected ? `How can ${agent?.name ?? "the agent"} help you today?` : "Connecting…"
          }
          rows={1}
          className={cn(
            "max-h-60 min-h-14 resize-none overflow-y-auto rounded-2xl border-0 bg-transparent px-4 pt-4 pb-1",
            "text-[15px] leading-relaxed shadow-none focus-visible:ring-0 dark:bg-transparent",
          )}
        />
        <div className="flex items-center gap-2 px-2.5 pb-2.5">
          <span className="ml-1.5 hidden text-xs text-muted-foreground xl:inline">
            Shift + Enter for a new line
          </span>
          <div className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
            {pickers}
            <Select value={agentId} onValueChange={onAgent}>
              <SelectTrigger
                size="sm"
                aria-label="Agent"
                title={agent?.description}
                className="max-w-56 border-0 bg-transparent text-muted-foreground shadow-none hover:bg-muted hover:text-foreground dark:bg-transparent dark:hover:bg-muted"
              >
                <Bot className="size-3.5" />
                {/* Just the name in the trigger; the description only shows in the menu. */}
                <SelectValue placeholder="Choose an agent">{agent?.name}</SelectValue>
              </SelectTrigger>
              <SelectContent align="end">
                {agents.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    <span className="flex flex-col">
                      <span>{a.name}</span>
                      <span className="text-xs text-muted-foreground">{a.description}</span>
                    </span>
                  </SelectItem>
                ))}
                <SelectSeparator />
                <Link
                  to="/agents"
                  className="block rounded-sm px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  Manage agents…
                </Link>
              </SelectContent>
            </Select>
            {streaming ? (
              <Button
                type="button"
                size="icon"
                variant="secondary"
                className="size-8 rounded-lg"
                onClick={onStop}
                disabled={!canStop}
                aria-label="Stop"
              >
                <Square className="size-3.5 fill-current" />
              </Button>
            ) : (
              <Button
                type="submit"
                size="icon"
                className="size-8 rounded-lg"
                disabled={!draft.trim() || !connected}
                aria-label="Send"
              >
                <ArrowUp className="size-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </form>
  );
}
