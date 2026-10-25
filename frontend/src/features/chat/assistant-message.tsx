import { Brain, FileText, Loader2, Wrench } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import type { AssistantTurn } from "./conversation";

export function AssistantMessage({ turn }: { turn: AssistantTurn }) {
  const [showThinking, setShowThinking] = useState(true);
  const live = turn.status === "pending" || turn.status === "streaming";

  return (
    <div role="article" aria-label="Agent answer" aria-busy={live} className="flex flex-col gap-3">
      {turn.status === "pending" && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Queuing run on Hatchet…
        </div>
      )}

      {turn.thinking && (
        <div className="rounded-lg border border-dashed bg-muted/30 px-3 py-2">
          <button
            type="button"
            onClick={() => setShowThinking((v) => !v)}
            className="flex items-center gap-2 text-xs font-medium text-muted-foreground"
          >
            <Brain className="size-3.5" /> Thinking {showThinking ? "▾" : "▸"}
          </button>
          {showThinking && (
            <p className="mt-1 text-sm whitespace-pre-wrap text-muted-foreground italic">
              {turn.thinking}
            </p>
          )}
        </div>
      )}

      {turn.toolCalls.map((call, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <Wrench className="size-3.5 text-muted-foreground" />
          <span className="font-mono text-xs">
            {call.tool}({JSON.stringify(call.args)})
          </span>
        </div>
      ))}

      {turn.retrieved.length > 0 && (
        <div role="list" aria-label="Retrieved chunks" className="grid gap-2 sm:grid-cols-2">
          {turn.retrieved.map((c) => (
            <div
              role="listitem"
              aria-label={`${c.document}#${c.chunk}`}
              key={`${c.document}#${c.chunk}`}
              className="rounded-md border bg-card p-2.5 text-xs"
            >
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-1 font-medium">
                  <FileText className="size-3 shrink-0" />
                  <span className="truncate">
                    {c.document}#{c.chunk}
                  </span>
                </span>
                <Badge variant="secondary" className="font-mono">
                  {c.score.toFixed(2)}
                </Badge>
              </div>
              <p className="line-clamp-3 text-muted-foreground">{c.text}</p>
            </div>
          ))}
        </div>
      )}

      {(turn.text || turn.status === "streaming") && (
        <p aria-label="Answer text" className="leading-relaxed whitespace-pre-wrap">
          <WithCitations text={turn.text} />
          {live && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-foreground align-middle" />
          )}
        </p>
      )}

      {turn.status !== "streaming" && turn.status !== "pending" && (
        <div
          className={cn(
            "text-xs",
            turn.status === "error" ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {turn.status === "cancelled" && "Stopped."}
          {turn.status === "error" && `Error: ${turn.error}`}
          {turn.model && <span className={cn(turn.status !== "done" && "ml-2")}>{turn.model}</span>}
          {turn.runId && (
            <span className="ml-2 font-mono opacity-70">run {turn.runId.slice(0, 8)}</span>
          )}
        </div>
      )}
    </div>
  );
}

const CITATION = /\[([^\]\s]+#\d+)\]/g;

/** Renders [handbook.md#3] citations as small chips. */
function WithCitations({ text }: { text: string }) {
  const parts = text.split(CITATION);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <cite
        key={i}
        className="mx-0.5 rounded bg-muted px-1.5 py-0.5 font-mono text-xs not-italic text-muted-foreground"
      >
        {part}
      </cite>
    ) : (
      part
    ),
  );
}
