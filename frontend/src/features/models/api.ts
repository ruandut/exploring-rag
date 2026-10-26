import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/** One model an endpoint offers, and how we know what it is (backend: providers/catalog.py). */
export type ModelInfo = {
  id: string;
  kind: "chat" | "embedding" | "unknown";
  source: "endpoint" | "known" | "guessed" | "unknown";
  dimensions: number | null;
  tools: boolean | null; // can it call tools? null = not known
};

export type Catalogue = { endpoint: string; hint: string; models: ModelInfo[] };

/** Where the models come from: a saved endpoint (connection null = the default provider), or
 *  an unsaved one being typed into a form. */
export type ModelSource =
  | { connection: number | null }
  | { probe: { kind: string; base_url: string; api_key: string } };

export type Want = "embedding" | "chat";

function sourceKey(source: ModelSource) {
  return "probe" in source
    ? `probe:${source.probe.kind}:${source.probe.base_url}`
    : (source.connection ?? "default");
}

/** The endpoint's models of one kind (plus unknowns), or all of them. Cached for 5 minutes;
 *  `refetch` is the picker's Refresh button. */
export function useModelCatalogue(source: ModelSource, want: Want | null, enabled = true) {
  return useQuery({
    queryKey: ["model-catalogue", sourceKey(source), want ?? "all"],
    queryFn: () => {
      const kind = want ? `?kind=${want}` : "";
      if ("probe" in source) {
        return api<Catalogue>(`/api/providers/models/probe/${kind}`, {
          method: "POST",
          body: JSON.stringify(source.probe),
        });
      }
      return api<Catalogue>(
        source.connection === null
          ? `/api/providers/models/${kind}`
          : `/api/providers/connections/${source.connection}/models/${kind}`,
      );
    },
    // An OpenAI-compatible probe needs a URL; Anthropic and Google default to their own API.
    enabled:
      enabled &&
      (!("probe" in source) ||
        source.probe.kind !== "openai" ||
        /^https?:\/\/.+/.test(source.probe.base_url)),
    retry: false,
    staleTime: 5 * 60_000,
  });
}
