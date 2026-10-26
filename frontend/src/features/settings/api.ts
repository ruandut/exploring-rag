import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";

import type { ProviderKind } from "./kinds";

// --- LLM provider (apps.providers) -------------------------------------------------------

export type ProviderConfig = {
  kind: ProviderKind;
  base_url: string;
  api_key_last4: string;
  has_api_key: boolean;
  chat_model: string;
  updated_at: string;
};

export type SaveProviderInput = {
  kind: ProviderKind;
  base_url: string; // blank = the SDK's default endpoint (Anthropic, Google)
  api_key?: string; // omitted = keep the stored key
  chat_model: string;
};

export type Check = { ok: boolean; detail: string; latency_ms: number | null };
/** Test connection checks chat only; each embedding has its own Test (spec 0010). */
export type ConnectionReport = { ok: boolean; chat: Check };

export function useProviderConfig() {
  return useQuery({
    queryKey: ["provider-config"],
    // 204 (nothing saved yet) comes back as null.
    queryFn: () => api<ProviderConfig | null>("/api/providers/config/"),
  });
}

export function useSaveProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SaveProviderInput) =>
      api<ProviderConfig>("/api/providers/config/", {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: (data) => queryClient.setQueryData(["provider-config"], data),
  });
}

export function useTestConnection() {
  return useMutation({
    mutationFn: (input: SaveProviderInput) =>
      api<ConnectionReport>("/api/providers/test/", {
        method: "POST",
        body: JSON.stringify(input),
      }),
  });
}

// --- Chunking (per embedding, apps.rag) ----------------------------------------------------

export type Strategy = "fixed" | "recursive" | "markdown" | "semantic" | "parent_document";

export const STRATEGIES: { value: Strategy; label: string; hint: string }[] = [
  { value: "fixed", label: "Fixed size", hint: "Every N tokens. Simple and predictable." },
  {
    value: "recursive",
    label: "Recursive",
    hint: "Paragraphs → sentences → words until it fits. A solid default.",
  },
  { value: "markdown", label: "Markdown / headings", hint: "Keeps sections together." },
  {
    value: "semantic",
    label: "Semantic",
    hint: "Splits where meaning shifts (uses extra embedding calls).",
  },
  {
    value: "parent_document",
    label: "Parent document",
    hint: "Search small chunks, give the LLM the larger parent.",
  },
];

// --- error helpers -----------------------------------------------------------------------

/** The server refused because the change re-indexes documents and needs confirmation. */
export function needsReindexConfirmation(error: unknown): error is ApiError {
  return (
    error instanceof ApiError &&
    error.status === 409 &&
    (error.body as { code?: string } | null)?.code === "reindex_required"
  );
}

/** DRF 400 bodies: { field: ["message", …] }. */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.status !== 400 || !error.body) return {};
  return Object.fromEntries(
    Object.entries(error.body as Record<string, string[] | string>).map(([k, v]) => [
      k,
      Array.isArray(v) ? v.join(" ") : String(v),
    ]),
  );
}
