import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useSocketEvents } from "@/hooks/use-socket";
import { api, ApiError } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

// --- suites (apps.evals) -----------------------------------------------------------------

export type CaseKind = "qa" | "refusal";

export type EvalCase = {
  id?: number;
  kind: CaseKind;
  question: string;
  reference_answer: string;
  relevant_documents: string[];
  evidence: string;
};

export type Boundary = {
  metric: string;
  aggregate: "mean" | "p50" | "p95";
  comparator: "gte" | "lte";
  value: number;
};

export type SuiteSummary = {
  id: number;
  name: string;
  description: string;
  metrics: string[];
  k: number;
  version: number;
  case_count: number;
  updated_at: string;
};

export type Suite = Omit<SuiteSummary, "case_count"> & {
  judge_connection: number | null;
  judge_model: string;
  cases: EvalCase[];
  boundaries: Boundary[];
};

export type SuiteInput = Omit<Suite, "id" | "version" | "updated_at">;

export function useSuites() {
  return useQuery({
    queryKey: ["suites"],
    queryFn: () => api<SuiteSummary[]>("/api/evals/suites/"),
  });
}

export function useSuite(id: number) {
  return useQuery({
    queryKey: ["suite", id],
    queryFn: () => api<Suite>(`/api/evals/suites/${id}/`),
  });
}

export function useSaveSuite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...input }: Partial<SuiteInput> & { id?: number; name: string }) =>
      api<Suite>(id ? `/api/evals/suites/${id}/` : "/api/evals/suites/", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: (suite) => {
      qc.setQueryData(["suite", suite.id], suite);
      void qc.invalidateQueries({ queryKey: ["suites"] });
    },
  });
}

export function useDeleteSuite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<null>(`/api/evals/suites/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["suites"] }),
  });
}

export function useImportCases(suiteId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api<{ added: number }>(`/api/evals/suites/${suiteId}/import/`, {
        method: "POST",
        body: form,
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suite", suiteId] });
      void qc.invalidateQueries({ queryKey: ["suites"] });
    },
  });
}

/** Download the suite's cases as a .jsonl file. */
export async function exportCases(suite: { id: number; name: string }) {
  const res = await fetch(`/api/evals/suites/${suite.id}/export/`, {
    headers: { Authorization: `Bearer ${getAccessToken()}` },
  });
  if (!res.ok) throw new ApiError(res.status, null);
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `${suite.name}.jsonl`;
  link.click();
  URL.revokeObjectURL(url);
}

// --- runs (apps.benchmarks) --------------------------------------------------------------

export type Target =
  | { kind: "agent"; agent: number }
  | { kind: "model"; connection: number | null; model: string };

export type Stats = { mean: number | null; p50: number | null; p95: number | null; n: number };

export type BoundaryResult = Boundary & {
  actual: number | null;
  passed: boolean | null; // null = skipped (metric n/a)
  margin: number | null;
};

export type RunSummary = {
  done: number;
  total: number;
  failed_cases: number;
  passed_cases?: number;
  metrics?: Record<string, Stats>;
  boundaries?: BoundaryResult[];
};

export type Run = {
  id: number;
  suite: number | null;
  suite_name: string;
  target_kind: "agent" | "model";
  target_label: string;
  compare_group: string | null;
  status: "running" | "passed" | "failed";
  summary: RunSummary;
  created_at: string;
  finished_at: string | null;
};

export type CaseResult = {
  id: number;
  position: number;
  case: EvalCase;
  status: "pending" | "done" | "failed";
  answer: string;
  retrieved: { document: string; chunk: number; score: number; text: string }[];
  scores: Record<string, number | null>;
  explanations: Record<string, string>;
  ttft_ms: number | null;
  latency_ms: number | null;
  tokens: number | null;
  passed: boolean | null;
  error: string;
};

export type RunDetail = Run & {
  suite_snapshot: { k: number; metrics: string[]; judge_model: string; version: number };
  target_snapshot: Record<string, unknown> & {
    system_message?: string;
    model?: string;
    connection_name?: string | null;
    rag_config?: Record<string, unknown>;
  };
  hatchet_run_id: string;
  results: CaseResult[];
  siblings: number[];
};

export function useRuns(suiteId: number) {
  return useQuery({
    queryKey: ["runs", suiteId],
    queryFn: () => api<Run[]>(`/api/benchmarks/runs/?suite=${suiteId}`),
  });
}

export function useRun(id: number | null) {
  return useQuery({
    queryKey: ["run", id],
    queryFn: () => api<RunDetail>(`/api/benchmarks/runs/${id}/`),
    enabled: id !== null,
  });
}

export function useStartRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { suite: number; targets: Target[] }) =>
      api<Run[]>("/api/benchmarks/runs/", { method: "POST", body: JSON.stringify(input) }),
    onSuccess: (_, input) => qc.invalidateQueries({ queryKey: ["runs", input.suite] }),
  });
}

export function useRetryFailed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: number) =>
      api<{ retried: number }>(`/api/benchmarks/runs/${runId}/retry/`, { method: "POST" }),
    onSuccess: (_, runId) => qc.invalidateQueries({ queryKey: ["run", runId] }),
  });
}

/** Live updates: refetch a run whenever the worker reports progress on it. */
export function useRunEvents(onProgress?: (runId: number, done: number, total: number) => void) {
  const qc = useQueryClient();
  useSocketEvents((e) => {
    if (e.type === "benchmark.progress") onProgress?.(e.run_id, e.done, e.total);
    if (e.type === "benchmark.case" || e.type === "benchmark.completed") {
      void qc.invalidateQueries({ queryKey: ["run", e.run_id] });
    }
    if (e.type === "benchmark.completed") void qc.invalidateQueries({ queryKey: ["runs"] });
  });
}
