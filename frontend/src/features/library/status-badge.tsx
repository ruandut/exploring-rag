import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import type { DocumentStatus } from "./api";

const STYLES: Record<DocumentStatus, { label: string; className: string }> = {
  queued: { label: "Queued", className: "bg-muted text-muted-foreground" },
  indexing: { label: "Indexing", className: "bg-amber-500/15 text-amber-700 dark:text-amber-400" },
  ready: { label: "Ready", className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400" },
  failed: { label: "Failed", className: "bg-destructive/15 text-destructive" },
  not_indexed: { label: "Not indexed", className: "bg-muted text-muted-foreground" },
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const style = STYLES[status];
  return (
    <Badge className={cn("border-0", style.className)}>
      {status === "indexing" && <Loader2 className="size-3 animate-spin" />}
      {style.label}
    </Badge>
  );
}
