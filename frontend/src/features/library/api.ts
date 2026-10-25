import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { useSocketEvents } from "@/hooks/use-socket";
import { api } from "@/lib/api";

export type Folder = {
  id: number;
  name: string;
  parent: number | null;
  document_count: number;
};

export type DocumentStatus = "queued" | "indexing" | "ready" | "failed";

export type LibraryDocument = {
  id: number;
  name: string;
  folder: number | null;
  content_type: string;
  size: number;
  status: DocumentStatus;
  error: string;
  chunk_count: number;
  indexed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Chunk = {
  index: number;
  heading: string;
  text: string;
  parent_text: string;
  token_count: number;
  dimensions: number;
  embedding_model: string;
  embedding_preview: number[];
};

/** "all" = everything, "root" = top level, otherwise a folder id. */
export type FolderKey = "all" | "root" | number;

const keys = {
  folders: ["library", "folders"] as const,
  documents: (folder: FolderKey) => ["library", "documents", folder] as const,
  allDocuments: ["library", "documents"] as const,
  chunks: (id: number) => ["rag", "chunks", id] as const,
};

export function useFolders() {
  return useQuery({
    queryKey: keys.folders,
    queryFn: () => api<Folder[]>("/api/library/folders/"),
  });
}

export function useDocuments(folder: FolderKey) {
  return useQuery({
    queryKey: keys.documents(folder),
    queryFn: () => api<LibraryDocument[]>(`/api/library/documents/?folder=${folder}`),
  });
}

export function useChunks(documentId: number | null) {
  return useQuery({
    queryKey: keys.chunks(documentId ?? 0),
    queryFn: () => api<Chunk[]>(`/api/rag/documents/${documentId}/chunks/`),
    enabled: documentId !== null,
  });
}

function invalidateLibrary(qc: QueryClient) {
  return qc.invalidateQueries({ queryKey: ["library"] });
}

export function useCreateFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; parent: number | null }) =>
      api<Folder>("/api/library/folders/", { method: "POST", body: JSON.stringify(input) }),
    onSuccess: () => invalidateLibrary(qc),
  });
}

export function useRenameFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      api<Folder>(`/api/library/folders/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => invalidateLibrary(qc),
  });
}

export function useDeleteFolder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<null>(`/api/library/folders/${id}/`, { method: "DELETE" }),
    onSuccess: () => invalidateLibrary(qc),
  });
}

export function useUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ files, folder }: { files: File[]; folder: number | null }) => {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      if (folder !== null) form.append("folder", String(folder));
      return api<LibraryDocument[]>("/api/library/documents/", { method: "POST", body: form });
    },
    onSuccess: () => invalidateLibrary(qc),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<null>(`/api/library/documents/${id}/`, { method: "DELETE" }),
    onSuccess: () => invalidateLibrary(qc),
  });
}

export function useReindexDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api<LibraryDocument>(`/api/library/documents/${id}/reindex/`, { method: "POST" }),
    onSuccess: (doc) => patchDocument(qc, doc.id, doc),
  });
}

export function useMoveDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, folder }: { id: number; folder: number | null }) =>
      api<LibraryDocument>(`/api/library/documents/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ folder }),
      }),
    onSuccess: () => invalidateLibrary(qc),
  });
}

/** Update one document in every cached list it appears in. */
function patchDocument(qc: QueryClient, id: number, patch: Partial<LibraryDocument>) {
  qc.setQueriesData<LibraryDocument[]>({ queryKey: keys.allDocuments }, (docs) =>
    docs?.map((d) => (d.id === id ? { ...d, ...patch } : d)),
  );
}

/**
 * Keep the React Query cache in step with indexing: the worker reports every status change
 * as a `document.status` websocket event, so no polling and no page reloads.
 */
export function useDocumentStatusSync() {
  const qc = useQueryClient();
  useSocketEvents((e) => {
    if (e.type !== "document.status") return;
    patchDocument(qc, e.document_id, {
      status: e.status,
      error: e.error,
      chunk_count: e.chunk_count,
    });
    if (e.status === "ready") void qc.invalidateQueries({ queryKey: keys.chunks(e.document_id) });
  });
}
