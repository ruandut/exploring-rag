import { createFileRoute } from "@tanstack/react-router";
import { Layers, Loader2, MoreHorizontal, Plus } from "lucide-react";
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
import { Progress } from "@/components/ui/progress";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  type Embedding,
  type EmbeddingInput,
  embeddingSummary,
  useCoveredDocuments,
  useDeleteEmbedding,
  useEmbeddings,
  useEmbeddingStatusSync,
  useReindexEmbedding,
  useSaveEmbedding,
} from "@/features/embeddings/api";
import { EmbeddingForm } from "@/features/embeddings/embedding-form";
import { ConfirmDialog } from "@/features/library/confirm-dialog";
import { StatusBadge } from "@/features/library/status-badge";
import { needsReindexConfirmation } from "@/features/settings/api";
import { ReindexDialog } from "@/features/settings/reindex-dialog";

export const Route = createFileRoute("/_app/embeddings")({
  staticData: { title: "Embeddings" },
  component: EmbeddingsPage,
});

const STATUS_LABEL = { indexing: "Indexing", ready: "Ready", failed: "Failed" } as const;

function EmbeddingsPage() {
  const embeddings = useEmbeddings();
  const save = useSaveEmbedding();
  const reindex = useReindexEmbedding();
  const remove = useDeleteEmbedding();
  const [editing, setEditing] = useState<Embedding | "new" | null>(null);
  const [deleting, setDeleting] = useState<Embedding | null>(null);
  // A save the server refused until a re-index is confirmed (409 reindex_required).
  const [pending, setPending] = useState<EmbeddingInput | null>(null);
  useEmbeddingStatusSync();

  function submit(input: EmbeddingInput, confirm = false) {
    const id = editing && editing !== "new" ? editing.id : undefined;
    save.mutate(
      { ...input, id, confirm_reindex: confirm },
      {
        onSuccess: (saved) => {
          toast.success(`Saved ${saved.name}`);
          if (saved.reindex_started) toast.info(`Re-indexing ${saved.name} in the background…`);
          save.reset();
          setEditing(null);
          setPending(null);
        },
        onError: (error) => {
          if (needsReindexConfirmation(error)) setPending(input);
        },
      },
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="max-w-2xl text-sm text-muted-foreground">
          An embedding is a searchable index of some of your documents: which folders or files, the
          model that turns their chunks into vectors, and how they&apos;re chunked. Keep several
          side by side to compare them, then pick one in Chat.
        </p>
        <Button onClick={() => setEditing("new")}>
          <Plus className="size-4" /> New embedding
        </Button>
      </div>

      {embeddings.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : embeddings.data?.length ? (
        <ul aria-label="Embeddings" className="grid gap-4 md:grid-cols-2">
          {embeddings.data.map((emb) => (
            // min-w-0: a grid item is at least as wide as its content by default, so one long
            // file name would widen the card past the screen instead of truncating.
            <li key={emb.id} aria-label={emb.name} className="min-w-0">
              <EmbeddingCard
                embedding={emb}
                onEdit={() => setEditing(emb)}
                onReindex={() =>
                  reindex.mutate(emb.id, {
                    onSuccess: () => toast.info(`Re-indexing ${emb.name}…`),
                  })
                }
                onDelete={() => setDeleting(emb)}
              />
            </li>
          ))}
        </ul>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
            <Layers className="size-6" />
            <p className="text-sm">
              No embeddings yet. Create one to make your documents searchable in Chat.
            </p>
          </CardContent>
        </Card>
      )}

      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>
              {editing === "new" ? "New embedding" : `Edit ${editing?.name ?? ""}`}
            </SheetTitle>
            <SheetDescription>
              Creating or changing an embedding indexes it in the background (Hatchet runs).
            </SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-6">
            {editing !== null && (
              <EmbeddingForm
                key={editing === "new" ? "new" : editing.id}
                embedding={editing === "new" ? null : editing}
                pending={save.isPending}
                error={needsReindexConfirmation(save.error) ? null : save.error}
                onCancel={() => setEditing(null)}
                onSubmit={(input) => submit(input)}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>

      <ReindexDialog
        open={pending !== null}
        title="Re-index this embedding?"
        detail="This changes the endpoint, model, dimensions or chunking."
        // Also fires when the dialog closes after "Save and re-index" — so no save.reset() here:
        // it would drop the in-flight save's onSuccess and leave the sheet open.
        onCancel={() => setPending(null)}
        onConfirm={() => pending && submit(pending, true)}
      />

      {deleting && (
        <ConfirmDialog
          title="Delete this embedding?"
          description={`“${deleting.name}” and its vectors are deleted. Your documents stay in the library; chats using it will ask you to pick another.`}
          confirmLabel="Delete"
          onCancel={() => setDeleting(null)}
          onConfirm={() => {
            remove.mutate(deleting.id, { onSuccess: () => toast.success("Embedding deleted") });
            setDeleting(null);
          }}
        />
      )}
    </div>
  );
}

function EmbeddingCard({
  embedding: emb,
  onEdit,
  onReindex,
  onDelete,
}: {
  embedding: Embedding;
  onEdit: () => void;
  onReindex: () => void;
  onDelete: () => void;
}) {
  const docs = useCoveredDocuments(emb.id);
  return (
    <Card className="h-full gap-3">
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <div className="grid min-w-0 gap-1">
          <CardTitle className="flex items-center gap-2">
            <Layers className="size-4 shrink-0" /> {emb.name}
          </CardTitle>
          <CardDescription className="truncate">
            {emb.connection_name} · {embeddingSummary(emb)}
          </CardDescription>
        </div>
        <div className="flex items-center gap-1">
          <Badge
            role="status"
            aria-label={`Status of ${emb.name}`}
            variant={emb.status === "failed" ? "destructive" : "secondary"}
          >
            {emb.status === "indexing" && <Loader2 className="size-3 animate-spin" />}
            {STATUS_LABEL[emb.status]}
          </Badge>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                aria-label={`Actions for ${emb.name}`}
              >
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={onEdit}>Edit</DropdownMenuItem>
              <DropdownMenuItem onClick={onReindex}>Re-index</DropdownMenuItem>
              <DropdownMenuItem variant="destructive" onClick={onDelete}>
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        {emb.status === "indexing" && emb.total > 0 && (
          <div className="grid gap-1">
            <Progress value={(emb.done / emb.total) * 100} aria-label={`${emb.name} progress`} />
            <span className="text-xs text-muted-foreground">
              {emb.done} of {emb.total} documents
            </span>
          </div>
        )}
        {emb.error && <p className="text-sm text-destructive">{emb.error}</p>}
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline">
            {emb.all_documents
              ? "All documents"
              : [
                  emb.folders.length && `${emb.folders.length} folders`,
                  emb.documents.length && `${emb.documents.length} files`,
                ]
                  .filter(Boolean)
                  .join(" + ")}
          </Badge>
        </div>
        <details>
          <summary className="cursor-pointer text-xs text-muted-foreground">
            {docs.data ? `${docs.data.length} documents` : "Documents"}
          </summary>
          <ul aria-label={`Documents in ${emb.name}`} className="mt-2 grid gap-1">
            {docs.data?.map((d) => (
              <li key={d.document_id} className="flex min-w-0 items-center justify-between gap-2">
                <span className="min-w-0 truncate" title={d.name}>
                  {d.name}
                </span>
                <span className="flex shrink-0 items-center gap-2 text-xs whitespace-nowrap text-muted-foreground">
                  {d.status === "ready" && `${d.chunk_count} chunks`}
                  <StatusBadge status={d.status} />
                </span>
              </li>
            ))}
          </ul>
        </details>
      </CardContent>
    </Card>
  );
}
