import { ArrowUp, Square } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/** The message box, laid out like Claude's: one rounded card with an auto-growing text area
 *  on top and a single toolbar row inside it — the chat options (info) button on the left,
 *  send / stop on the right. The pickers live behind the info button so the row never wraps. */
export function Composer({
  draft,
  onDraft,
  onSend,
  onStop,
  streaming,
  canStop,
  connected,
  agentName,
  options,
  autoFocus,
}: {
  draft: string;
  onDraft: (text: string) => void;
  onSend: () => void;
  onStop: () => void;
  streaming: boolean;
  canStop: boolean;
  connected: boolean;
  agentName: string;
  /** The chat options button (agent, embedding, model). */
  options?: ReactNode;
  autoFocus?: boolean;
}) {
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
          placeholder={connected ? `How can ${agentName} help you today?` : "Connecting…"}
          rows={1}
          className={cn(
            "max-h-60 min-h-14 resize-none overflow-y-auto rounded-2xl border-0 bg-transparent px-4 pt-4 pb-1",
            "text-[15px] leading-relaxed shadow-none focus-visible:ring-0 dark:bg-transparent",
          )}
        />
        <div className="flex items-center gap-2 px-2.5 pb-2.5">
          {options}
          <span className="hidden text-xs text-muted-foreground sm:inline">
            Shift + Enter for a new line
          </span>
          <div className="ml-auto flex items-center">
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
