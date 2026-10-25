import { Skeleton } from "@/components/ui/skeleton";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

import { type LibraryDocument, useChunks } from "./api";

/** "What did indexing actually produce?" — every chunk with its size and a peek at its vector. */
export function ChunksSheet({
  document,
  onClose,
}: {
  document: LibraryDocument | null;
  onClose: () => void;
}) {
  const chunks = useChunks(document?.id ?? null);
  const first = chunks.data?.[0];

  return (
    <Sheet open={document !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>Chunks of {document?.name}</SheetTitle>
          <SheetDescription>
            {first
              ? `${chunks.data!.length} chunks · ${first.dimensions} dimensions · ${first.embedding_model}`
              : "What the indexer stored: each chunk's text, its size and the start of its embedding."}
          </SheetDescription>
        </SheetHeader>
        <ol aria-label="Chunks" className="grid gap-3 px-4 pb-6">
          {chunks.isPending && <Skeleton className="h-24 w-full" />}
          {chunks.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">No chunks yet — is it still indexing?</p>
          )}
          {chunks.data?.map((c) => (
            <li key={c.index} className="grid gap-2 rounded-lg border p-3 text-sm">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                <span className="font-mono font-medium text-foreground">#{c.index}</span>
                {c.heading && <span>{c.heading}</span>}
                <span>{c.token_count} tokens</span>
                <span>{c.dimensions} dimensions</span>
              </div>
              <p className="whitespace-pre-wrap">{c.text}</p>
              <code className="truncate text-xs text-muted-foreground">
                [{c.embedding_preview.join(", ")}, …]
              </code>
              {c.parent_text && (
                <details className="text-xs text-muted-foreground">
                  <summary className="cursor-pointer">Parent context given to the LLM</summary>
                  <p className="mt-1 whitespace-pre-wrap">{c.parent_text}</p>
                </details>
              )}
            </li>
          ))}
        </ol>
      </SheetContent>
    </Sheet>
  );
}
