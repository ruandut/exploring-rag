import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ProviderKind } from "@/features/settings/kinds";
import { api } from "@/lib/api";

// --- agents (apps.agents) ----------------------------------------------------------------

export type RagConfig = {
  query_transform: "none" | "multi_query" | "hyde" | "step_back";
  retrieval: "dense" | "keyword" | "hybrid" | "mmr";
  top_k: number;
  rerank: "none" | "llm";
  generation: "stuff" | "cited" | "map_reduce" | "refine" | "corrective";
};

/** How an agent retrieves and answers. What it searches (an embedding) and which model answers
 *  are picked in the chat, next to the agent (spec 0010). */
export type Agent = {
  id: number;
  name: string;
  system_message: string;
  effort: "" | "low" | "medium" | "high" | "xhigh" | "max"; // "" = high; ignored by some providers
  rag_config: RagConfig;
  updated_at: string;
};

export type AgentInput = Omit<Agent, "id" | "updated_at">;

export const DEFAULT_RAG: RagConfig = {
  query_transform: "none",
  retrieval: "hybrid",
  top_k: 5,
  rerank: "none",
  generation: "cited",
};

export function useAgents() {
  return useQuery({ queryKey: ["agents"], queryFn: () => api<Agent[]>("/api/agents/") });
}

export function useSaveAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...input }: AgentInput & { id?: number }) =>
      api<Agent>(id ? `/api/agents/${id}/` : "/api/agents/", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents"] }),
  });
}

export function useDeleteAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<null>(`/api/agents/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents"] }),
  });
}

/** How the UI names a model choice: "Ollama (local) · gemma4:e4b", "Default provider · gpt-5". */
export function modelLabel(connectionName: string | null, model: string, fallback = ""): string {
  const source = connectionName ?? "Default provider";
  const name = model || fallback;
  return name ? `${source} · ${name}` : source;
}

/** One-line description of an agent's RAG pipeline, for pickers and cards. */
export function pipelineLabel(agent: Agent): string {
  const r = agent.rag_config;
  return `${r.retrieval}, top-${r.top_k}, ${r.generation}`;
}

// --- connections (apps.providers) --------------------------------------------------------

export type Connection = {
  id: number;
  name: string;
  kind: ProviderKind;
  base_url: string;
  api_key_last4: string;
  has_api_key: boolean;
  updated_at: string;
};

export function useConnections() {
  return useQuery({
    queryKey: ["connections"],
    queryFn: () => api<Connection[]>("/api/providers/connections/"),
  });
}

export function useSaveConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...input
    }: {
      id?: number;
      name: string;
      kind: ProviderKind;
      base_url: string;
      api_key?: string;
    }) =>
      api<Connection>(id ? `/api/providers/connections/${id}/` : "/api/providers/connections/", {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["connections"] }),
  });
}

export function useDeleteConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      api<null>(`/api/providers/connections/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["connections"] });
      void qc.invalidateQueries({ queryKey: ["agents"] });
    },
  });
}

/** Model ids an endpoint offers. connection null = the default provider. (The model picker
 *  uses the richer features/models catalogue; this is for plain lists like Settings.) */
export function useModels(connection: number | null, enabled = true) {
  return useQuery({
    queryKey: ["models", connection ?? "default"],
    queryFn: () =>
      api<{ models: { id: string }[] }>(
        connection === null
          ? "/api/providers/models/"
          : `/api/providers/connections/${connection}/models/`,
      ),
    select: (data) => ({ models: data.models.map((m) => m.id) }),
    enabled,
    retry: false,
    staleTime: 60_000,
  });
}
