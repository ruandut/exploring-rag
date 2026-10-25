import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

// --- agents (apps.agents) ----------------------------------------------------------------

export type RagConfig = {
  query_transform: "none" | "multi_query" | "hyde" | "step_back";
  retrieval: "dense" | "keyword" | "hybrid" | "mmr";
  top_k: number;
  rerank: "none" | "llm";
  generation: "stuff" | "cited" | "map_reduce" | "refine" | "corrective";
};

export type Agent = {
  id: number;
  name: string;
  system_message: string;
  connection: number | null;
  connection_name: string | null;
  model: string;
  folders: number[];
  rag_config: RagConfig;
  updated_at: string;
};

export type AgentInput = Omit<Agent, "id" | "connection_name" | "updated_at">;

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

/** How the UI names an agent's model: "Ollama (local) · gemma4:e4b" or "Default provider". */
export function modelLabel(agent: Agent): string {
  if (agent.connection_name) return `${agent.connection_name} · ${agent.model}`;
  return agent.model ? `Default provider · ${agent.model}` : "Default provider";
}

// --- connections (apps.providers) --------------------------------------------------------

export type Connection = {
  id: number;
  name: string;
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

/** Models an endpoint offers. connection null = the default provider. */
export function useModels(connection: number | null, enabled = true) {
  return useQuery({
    queryKey: ["models", connection ?? "default"],
    queryFn: () =>
      api<{ models: string[] }>(
        connection === null
          ? "/api/providers/models/"
          : `/api/providers/connections/${connection}/models/`,
      ),
    enabled,
    retry: false,
    staleTime: 60_000,
  });
}
