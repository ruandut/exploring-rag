// Metric catalog. Ids match the backend registry (backend/apps/scoring/metrics.py). Metrics
// whose `spec` is "0007" are described but not computed yet.

export type MetricGroup = "retrieval" | "generation" | "behaviour" | "operational";

export type Metric = {
  id: string;
  name: string;
  group: MetricGroup;
  question: string; // what it measures, phrased as the question it answers
  needs: string; // gold data / inputs required
  scoring: "deterministic" | "llm-judge" | "measured";
  higherIsBetter: boolean;
  spec?: "0007";
};

/** Metrics a suite can select (retrieval + judge). Refusal rate is automatic for refusal cases. */
export const SELECTABLE = [
  "hit_rate",
  "recall",
  "precision",
  "mrr",
  "ndcg",
  "faithfulness",
  "answer_relevancy",
  "answer_correctness",
  "context_precision",
  "context_recall",
  "citation_accuracy",
];

/** "Recall@k" → "Recall@5" for the suite's k. */
export function metricName(id: string, k = 5): string {
  const m = METRICS.find((x) => x.id === id);
  return m ? m.name.replace("@k", `@${k}`) : id;
}

export const METRIC_GROUPS: Record<MetricGroup, { title: string; blurb: string }> = {
  retrieval: {
    title: "Retrieval",
    blurb: "Did search find the right chunks? Exact maths against labelled relevant chunks.",
  },
  generation: {
    title: "Generation",
    blurb: "Is the answer grounded, relevant and correct? Scored by a judge LLM (RAGAS-style).",
  },
  behaviour: {
    title: "Behaviour",
    blurb: "Boundaries on what the agent must or must not do.",
  },
  operational: {
    title: "Operational",
    blurb: "Speed and cost — a better answer that takes 40 s may still fail.",
  },
};

export const METRICS: Metric[] = [
  {
    id: "hit_rate",
    name: "Hit rate@k",
    group: "retrieval",
    question: "Did any relevant chunk appear in the top k?",
    needs: "relevant chunks",
    scoring: "deterministic",
    higherIsBetter: true,
  },
  {
    id: "recall",
    name: "Recall@k",
    group: "retrieval",
    question: "What fraction of the relevant chunks were found in the top k?",
    needs: "relevant chunks",
    scoring: "deterministic",
    higherIsBetter: true,
  },
  {
    id: "precision",
    name: "Precision@k",
    group: "retrieval",
    question: "What fraction of the top k is relevant?",
    needs: "relevant chunks",
    scoring: "deterministic",
    higherIsBetter: true,
  },
  {
    id: "mrr",
    name: "MRR",
    group: "retrieval",
    question: "How high is the first relevant chunk ranked (1/rank)?",
    needs: "relevant chunks",
    scoring: "deterministic",
    higherIsBetter: true,
  },
  {
    id: "ndcg",
    name: "nDCG@k",
    group: "retrieval",
    question: "Are relevant chunks near the top, not just present?",
    needs: "relevant chunks",
    scoring: "deterministic",
    higherIsBetter: true,
  },
  {
    id: "faithfulness",
    name: "Faithfulness",
    group: "generation",
    question: "Is every claim supported by the retrieved context?",
    needs: "—",
    scoring: "llm-judge",
    higherIsBetter: true,
  },
  {
    id: "answer_relevancy",
    name: "Answer relevancy",
    group: "generation",
    question: "Does the answer actually address the question?",
    needs: "—",
    scoring: "llm-judge",
    higherIsBetter: true,
  },
  {
    id: "context_precision",
    name: "Context precision",
    group: "generation",
    question: "Are the retrieved chunks relevant, and ranked first?",
    needs: "reference answer",
    scoring: "llm-judge",
    higherIsBetter: true,
  },
  {
    id: "context_recall",
    name: "Context recall",
    group: "generation",
    question: "Does the context contain what the reference answer needs?",
    needs: "reference answer",
    scoring: "llm-judge",
    higherIsBetter: true,
  },
  {
    id: "answer_correctness",
    name: "Answer correctness",
    group: "generation",
    question: "Does it match the reference answer?",
    needs: "reference answer",
    scoring: "llm-judge",
    higherIsBetter: true,
  },
  {
    id: "citation_accuracy",
    name: "Citation accuracy",
    group: "generation",
    question: "Do the cited [doc#chunk] sources support the sentences citing them?",
    needs: "—",
    scoring: "llm-judge",
    higherIsBetter: true,
  },
  {
    id: "refusal_rate",
    name: "Refusal rate",
    group: "behaviour",
    question: "Does it say “I don't know” when the documents don't contain the answer?",
    needs: "refusal cases",
    scoring: "llm-judge",
    higherIsBetter: true,
  },
  {
    id: "injection_resistance",
    spec: "0007",
    name: "Injection resistance",
    group: "behaviour",
    question: "Does it ignore instructions hidden in questions or documents?",
    needs: "injection cases",
    scoring: "llm-judge",
    higherIsBetter: true,
  },
  {
    id: "format_compliance",
    spec: "0007",
    name: "Format compliance",
    group: "behaviour",
    question: "Does the output follow the rule (citations present, valid JSON…)?",
    needs: "rule",
    scoring: "deterministic",
    higherIsBetter: true,
  },
  {
    id: "ttft",
    name: "Time to first token",
    group: "operational",
    question: "How long until the user sees something (p50 / p95)?",
    needs: "—",
    scoring: "measured",
    higherIsBetter: false,
  },
  {
    id: "latency_total",
    name: "Total latency",
    group: "operational",
    question: "How long until the answer is complete (p50 / p95)?",
    needs: "—",
    scoring: "measured",
    higherIsBetter: false,
  },
  {
    id: "tokens",
    name: "Tokens",
    group: "operational",
    question: "Prompt + completion tokens per case.",
    needs: "—",
    scoring: "measured",
    higherIsBetter: false,
  },
  {
    id: "cost_per_case",
    spec: "0007",
    name: "Cost per case",
    group: "operational",
    question: "Estimated $ per answered question.",
    needs: "price table",
    scoring: "measured",
    higherIsBetter: false,
  },
  {
    id: "error_rate",
    name: "Error rate",
    group: "operational",
    question: "How many cases failed to produce an answer?",
    needs: "—",
    scoring: "measured",
    higherIsBetter: false,
  },
];

export type Boundary = {
  metric: string;
  aggregate: "mean" | "p95";
  comparator: "≥" | "≤";
  value: string;
};

/** Example boundaries shown on the preview page; spec 0006 makes these editable per suite. */
export const EXAMPLE_BOUNDARIES: Boundary[] = [
  { metric: "Faithfulness", aggregate: "mean", comparator: "≥", value: "0.85" },
  { metric: "Recall@5", aggregate: "mean", comparator: "≥", value: "0.80" },
  { metric: "Refusal rate", aggregate: "mean", comparator: "≥", value: "0.95" },
  { metric: "Total latency", aggregate: "p95", comparator: "≤", value: "8 s" },
  { metric: "Cost per case", aggregate: "mean", comparator: "≤", value: "$0.01" },
];
