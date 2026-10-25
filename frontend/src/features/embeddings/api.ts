import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useSocketEvents } from "@/hooks/use-socket";
import { api } from "@/lib/api";

import type { Strategy } from "@/features/settings/api";

/** A named embedding (spec 0010): what it covers, and the model + chunking that index it. */
export type Embedding = {
  id: number;
  name: string;
  connection: number | null; // null = the default provider
  connection_name: string;
  model: string;
  dimensions: number | null;
  strategy: Strategy;
  chunk_size: number;
  chunk_overlap: number;
  all_documents: boolean;
  folders: number[];
  documents: number[];
  status: "indexing" | "ready" | "failed";
  error: string;
  done: number;
  total: number;
  created_at: string;
  updated_at: string;
};

export type EmbeddingInput = Pick<
  Embedding,
  | "name"
  | "connection"
  | "model"
  | "dimensions"
  | "strategy"
  | "chunk_size"
  | "chunk_overlap"
  | "all_documents"
  | "folders"
  | "documents"
>;

export type CoveredDocument = {
  document_id: number;
  name: string;
  folder: number | null;
  status: "queued" | "indexing" | "ready" | "failed";
  error: string;
  chunk_count: number;
  indexed_at: string | null;
};

export type EmbeddingTest = {
  ok: boolean;
  detail: string;
  latency_ms: number | null;
  dimensions: number | null;
};

const keys = {
  all: ["embeddings"] as const,
  documents: (id: number) => ["embeddings", id, "documents"] as const,
};

export function useEmbeddings() {
  return useQuery({ queryKey: keys.all, queryFn: () => api<Embedding[]>("/api/rag/embeddings/") });
}

export function useCoveredDocuments(id: number | null) {
  return useQuery({
    queryKey: keys.documents(id ?? 0),
    queryFn: () => api<CoveredDocument[]>(`/api/rag/embeddings/${id}/documents/`),
    enabled: id !== null,
  });
}

/** Create (no id) or update. Updates that change how vectors are made answer 409 until
 *  confirm_reindex is sent — see needsReindexConfirmation in settings/api. */
export function useSaveEmbedding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      confirm_reindex,
      ...input
    }: Partial<EmbeddingInput> & { id?: number; confirm_reindex?: boolean }) =>
      api<Embedding & { reindex_started?: boolean }>(
        id ? `/api/rag/embeddings/${id}/` : "/api/rag/embeddings/",
        {
          method: id ? "PATCH" : "POST",
          body: JSON.stringify({ ...input, confirm_reindex }),
        },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.all }),
  });
}

export function useReindexEmbedding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api<Embedding>(`/api/rag/embeddings/${id}/reindex/`, { method: "POST" }),
    // Show "Indexing" straight away; embedding.status events take it from there.
    onSuccess: (emb) =>
      qc.setQueryData<Embedding[]>(keys.all, (list) =>
        list?.map((e) => (e.id === emb.id ? emb : e)),
      ),
  });
}

export function useDeleteEmbedding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<null>(`/api/rag/embeddings/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.all });
      void qc.invalidateQueries({ queryKey: ["library"] });
    },
  });
}

export function useTestEmbedding() {
  return useMutation({
    mutationFn: (input: { connection: number | null; model: string }) =>
      api<EmbeddingTest>("/api/rag/embeddings/test/", {
        method: "POST",
        body: JSON.stringify(input),
      }),
  });
}

/**
 * Indexing reports progress as `embedding.status` websocket events: patch the list in place
 * (status + done/total) and refetch the covered documents, so the page updates live.
 */
export function useEmbeddingStatusSync() {
  const qc = useQueryClient();
  useSocketEvents((e) => {
    if (e.type !== "embedding.status") return;
    qc.setQueryData<Embedding[]>(keys.all, (list) =>
      list?.map((emb) =>
        emb.id === e.embedding_id
          ? { ...emb, status: e.status, done: e.done, total: e.total, error: e.error ?? "" }
          : emb,
      ),
    );
    void qc.invalidateQueries({ queryKey: keys.documents(e.embedding_id) });
    // A first indexing run may have filled in the dimensions.
    if (e.status !== "indexing") void qc.invalidateQueries({ queryKey: keys.all });
  });
}

export function chunkingLabel(e: Pick<Embedding, "strategy" | "chunk_size" | "chunk_overlap">) {
  return `${e.strategy} ${e.chunk_size}/${e.chunk_overlap}`;
}

/** e.g. "fake-embed, 8 dims, recursive 512/64" — how chats and runs describe an embedding. */
export function embeddingSummary(e: Embedding) {
  const dims = e.dimensions ? `${e.dimensions} dims` : "dims unknown";
  return `${e.model}, ${dims}, ${chunkingLabel(e)}`;
}
