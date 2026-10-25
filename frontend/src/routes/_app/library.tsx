import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { FolderPlus, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  type Folder,
  type FolderKey,
  type LibraryDocument,
  useCreateFolder,
  useDeleteDocument,
  useDeleteFolder,
  useDocuments,
  useDocumentStatusSync,
  useFolders,
  useMoveDocument,
  useReindexDocument,
  useRenameFolder,
  useUpload,
} from "@/features/library/api";
import { ChunksSheet } from "@/features/library/chunks-sheet";
import { ConfirmDialog } from "@/features/library/confirm-dialog";
import { type DocumentAction, DocumentsTable } from "@/features/library/documents-table";
import { FolderDialog } from "@/features/library/folder-dialog";
import { type FolderAction, FolderTree } from "@/features/library/folder-tree";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

type Search = { folder?: number };

export const Route = createFileRoute("/_app/library")({
  staticData: { title: "Library" },
  // ?folder=12 keeps the selected folder in the URL (reload- and link-safe).
  validateSearch: (search: Record<string, unknown>): Search => {
    const folder = Number(search.folder);
    return Number.isInteger(folder) && folder > 0 ? { folder } : {};
  },
  component: LibraryPage,
});

const ACCEPT = ".pdf,.docx,.md,.markdown,.txt";

type Dialog =
  | { kind: "create"; parent: Folder | null }
  | { kind: "rename"; folder: Folder }
  | { kind: "delete-folder"; folder: Folder }
  | { kind: "delete-document"; document: LibraryDocument }
  | null;

function detail(error: unknown): string | undefined {
  return error instanceof ApiError ? (error.body as { detail?: string } | null)?.detail : undefined;
}

function LibraryPage() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const selected: FolderKey = search.folder ?? "all";

  const folders = useFolders();
  const documents = useDocuments(selected);
  useDocumentStatusSync();

  const createFolder = useCreateFolder();
  const renameFolder = useRenameFolder();
  const deleteFolder = useDeleteFolder();
  const upload = useUpload();
  const deleteDocument = useDeleteDocument();
  const reindex = useReindexDocument();
  const move = useMoveDocument();

  const [dialog, setDialog] = useState<Dialog>(null);
  const [chunksOf, setChunksOf] = useState<LibraryDocument | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const folderList = folders.data ?? [];
  const current =
    typeof selected === "number" ? folderList.find((f) => f.id === selected) : undefined;

  const select = (key: FolderKey) =>
    void navigate({ search: typeof key === "number" ? { folder: key } : {} });

  function uploadFiles(files: File[]) {
    if (files.length === 0) return;
    upload.mutate(
      { files, folder: current?.id ?? null },
      {
        onSuccess: (docs) =>
          toast.success(
            `${docs.length} document${docs.length === 1 ? "" : "s"} queued for indexing`,
          ),
        onError: (e) => toast.error(detail(e) ?? "Upload failed"),
      },
    );
  }

  function onFolderAction(action: FolderAction, folder: Folder) {
    if (action === "new-subfolder") setDialog({ kind: "create", parent: folder });
    if (action === "rename") setDialog({ kind: "rename", folder });
    if (action === "delete") setDialog({ kind: "delete-folder", folder });
  }

  function onDocumentAction(action: DocumentAction) {
    const doc = action.document;
    if (action.kind === "chunks") setChunksOf(doc);
    if (action.kind === "delete") setDialog({ kind: "delete-document", document: doc });
    if (action.kind === "reindex") {
      reindex.mutate(doc.id, { onSuccess: () => toast.info(`Re-indexing ${doc.name}…`) });
    }
    if (action.kind === "move") {
      move.mutate(
        { id: doc.id, folder: action.folder },
        { onSuccess: () => toast.success(`Moved ${doc.name}`) },
      );
    }
  }

  return (
    <div className="grid flex-1 gap-4 p-4 lg:grid-cols-[260px_1fr]">
      <Card className="h-fit gap-2">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm">Folders</CardTitle>
          <Button
            size="icon"
            variant="ghost"
            className="size-7"
            aria-label="New folder"
            onClick={() => setDialog({ kind: "create", parent: current ?? null })}
          >
            <FolderPlus className="size-4" />
          </Button>
        </CardHeader>
        <CardContent>
          {folders.isPending ? (
            <Skeleton className="h-20 w-full" />
          ) : (
            <FolderTree
              folders={folderList}
              selected={selected}
              onSelect={select}
              onAction={onFolderAction}
            />
          )}
        </CardContent>
      </Card>

      <Card
        className={cn("min-w-0 gap-4 transition-colors", dragging && "ring-2 ring-primary")}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          uploadFiles([...e.dataTransfer.files]);
        }}
      >
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
          <CardTitle>{current?.name ?? "All documents"}</CardTitle>
          <Button onClick={() => fileInput.current?.click()} disabled={upload.isPending}>
            <Upload className="size-4" /> Upload documents
          </Button>
          <input
            ref={fileInput}
            type="file"
            multiple
            accept={ACCEPT}
            aria-label="Choose documents to upload"
            className="hidden"
            onChange={(e) => {
              uploadFiles([...(e.target.files ?? [])]);
              e.target.value = "";
            }}
          />
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {documents.isPending ? (
            <Skeleton className="h-32 w-full" />
          ) : documents.data?.length ? (
            <DocumentsTable
              documents={documents.data}
              folders={folderList}
              showFolder={selected === "all"}
              onAction={onDocumentAction}
            />
          ) : (
            <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-12 text-center text-muted-foreground">
              <Upload className="size-6" />
              <p className="text-sm">
                Drop PDF, Word, Markdown or text files here
                {current ? ` to add them to ${current.name}` : ""}.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {dialog?.kind === "create" && (
        <FolderDialog
          title="New folder"
          description={dialog.parent ? `Inside ${dialog.parent.name}` : "At the top level"}
          submitLabel="Create folder"
          pending={createFolder.isPending}
          error={detail(createFolder.error)}
          onClose={() => {
            createFolder.reset();
            setDialog(null);
          }}
          onSubmit={(name) =>
            createFolder.mutate(
              { name, parent: dialog.parent?.id ?? null },
              { onSuccess: () => setDialog(null) },
            )
          }
        />
      )}
      {dialog?.kind === "rename" && (
        <FolderDialog
          title="Rename folder"
          submitLabel="Rename"
          initialName={dialog.folder.name}
          pending={renameFolder.isPending}
          error={detail(renameFolder.error)}
          onClose={() => {
            renameFolder.reset();
            setDialog(null);
          }}
          onSubmit={(name) =>
            renameFolder.mutate(
              { id: dialog.folder.id, name },
              { onSuccess: () => setDialog(null) },
            )
          }
        />
      )}
      {dialog?.kind === "delete-folder" && (
        <ConfirmDialog
          title={`Delete ${dialog.folder.name}?`}
          description="Its subfolders and every document in them are deleted too, along with their chunks. This can't be undone."
          confirmLabel="Delete folder"
          onCancel={() => setDialog(null)}
          onConfirm={() => {
            const id = dialog.folder.id;
            deleteFolder.mutate(id, {
              onSuccess: () => {
                if (selected === id) select("all");
                toast.success("Folder deleted");
              },
            });
            setDialog(null);
          }}
        />
      )}
      {dialog?.kind === "delete-document" && (
        <ConfirmDialog
          title={`Delete ${dialog.document.name}?`}
          description="The file and all its chunks are removed. This can't be undone."
          confirmLabel="Delete"
          onCancel={() => setDialog(null)}
          onConfirm={() => {
            const doc = dialog.document;
            deleteDocument.mutate(doc.id, {
              onSuccess: () => toast.success(`Deleted ${doc.name}`),
            });
            setDialog(null);
          }}
        />
      )}
      <ChunksSheet document={chunksOf} onClose={() => setChunksOf(null)} />
    </div>
  );
}
