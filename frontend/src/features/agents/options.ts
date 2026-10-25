// Labels and one-line explanations for every RAG option. Ids match apps/agents/models.py.
import type { RagConfig } from "./api";

type Option<T extends string> = { value: T; label: string; hint: string };

export const RETRIEVAL: Option<RagConfig["retrieval"]>[] = [
  {
    value: "hybrid",
    label: "Hybrid",
    hint: "Meaning + exact keywords, merged with RRF. A good default.",
  },
  {
    value: "dense",
    label: "Dense",
    hint: "Vector similarity only — finds paraphrases, misses exact codes.",
  },
  { value: "keyword", label: "Keyword", hint: "Postgres full-text — exact terms, no synonyms." },
  {
    value: "mmr",
    label: "MMR",
    hint: "Dense, then picks diverse chunks instead of near-duplicates.",
  },
];

export const QUERY_TRANSFORMS: Option<RagConfig["query_transform"]>[] = [
  { value: "none", label: "None", hint: "Search with the question as asked." },
  {
    value: "multi_query",
    label: "Multi-query",
    hint: "LLM writes 3 variants; results are merged.",
  },
  { value: "hyde", label: "HyDE", hint: "Embed a hypothetical answer instead of the question." },
  {
    value: "step_back",
    label: "Step-back",
    hint: "Also search a broader version of the question.",
  },
];

export const RERANKERS: Option<RagConfig["rerank"]>[] = [
  { value: "none", label: "None", hint: "Keep the search order." },
  {
    value: "llm",
    label: "LLM rerank",
    hint: "Fetch 3× more, let the LLM order them by relevance.",
  },
];

export const GENERATION: Option<RagConfig["generation"]>[] = [
  { value: "cited", label: "Cited", hint: "Answer from the chunks and cite [document#chunk]." },
  { value: "stuff", label: "Stuff", hint: "Chunks go straight into the prompt; no citation rule." },
  {
    value: "map_reduce",
    label: "Map-reduce",
    hint: "Summarise each chunk first, then answer from the notes.",
  },
  {
    value: "refine",
    label: "Refine",
    hint: "Draft from the first chunk, improve it chunk by chunk.",
  },
  {
    value: "corrective",
    label: "Corrective",
    hint: "Grade chunks; if none help, rewrite the query and retry.",
  },
];
