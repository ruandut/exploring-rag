import { Download, Plus, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useConnections } from "@/features/agents/api";
import { ModelCombobox } from "@/features/models/model-picker";
import { ApiError } from "@/lib/api";

import {
  type Boundary,
  type EvalCase,
  exportCases,
  type Suite,
  useImportCases,
  useSaveSuite,
} from "./api";
import { METRICS, metricName, SELECTABLE } from "./metrics";

// Native selects on purpose (specs pick options with Playwright's selectOption). native-select
// in index.css draws our own chevron so it sits inside the padding like the shadcn Select.
export const nativeSelect =
  "native-select h-9 min-w-0 rounded-md border border-input bg-transparent pl-3 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring";

const BOUNDARY_METRICS = [
  ...SELECTABLE,
  "refusal_rate",
  "ttft",
  "latency_total",
  "tokens",
  "tokens_per_second",
  "waiting_time",
  "search_time",
  "reasoning_time",
  "writing_time",
  "error_rate",
];

const emptyCase = (): EvalCase => ({
  kind: "qa",
  question: "",
  reference_answer: "",
  relevant_documents: [],
  evidence: "",
});

function detail(error: unknown): string | undefined {
  if (!(error instanceof ApiError) || !error.body) return undefined;
  return Object.entries(error.body as Record<string, unknown>)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? JSON.stringify(v) : String(v)}`)
    .join(" · ");
}

export function SuiteEditor({ suite }: { suite: Suite }) {
  const [name, setName] = useState(suite.name);
  const [description, setDescription] = useState(suite.description);
  const [metrics, setMetrics] = useState<string[]>(suite.metrics);
  const [k, setK] = useState(suite.k);
  const [judgeConnection, setJudgeConnection] = useState<number | null>(suite.judge_connection);
  const [judgeModel, setJudgeModel] = useState(suite.judge_model);
  const [cases, setCases] = useState<EvalCase[]>(suite.cases);
  const [boundaries, setBoundaries] = useState<Boundary[]>(suite.boundaries);
  const save = useSaveSuite();
  const importCases = useImportCases(suite.id);
  const connections = useConnections();
  const fileInput = useRef<HTMLInputElement>(null);

  const setCase = (i: number, patch: Partial<EvalCase>) =>
    setCases((cs) => cs.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const setBoundary = (i: number, patch: Partial<Boundary>) =>
    setBoundaries((bs) => bs.map((b, j) => (j === i ? { ...b, ...patch } : b)));

  function submit() {
    save.mutate(
      {
        id: suite.id,
        name,
        description,
        metrics,
        k,
        judge_connection: judgeConnection,
        judge_model: judgeModel,
        cases,
        boundaries,
      },
      { onSuccess: (s) => toast.success(`Saved ${s.name} (version ${s.version})`) },
    );
  }

  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Card>
        <CardHeader>
          <CardTitle>Suite</CardTitle>
          <CardDescription aria-label="Suite summary">
            {suite.cases.length} cases · {suite.metrics.length} metrics · version {suite.version}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="suite-name">Suite name</Label>
            <Input
              id="suite-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="suite-description">Description</Label>
            <Input
              id="suite-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Metrics</CardTitle>
          <CardDescription>
            Refusal rate is scored automatically for refusal cases; latency, tokens and errors are
            always recorded.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="flex items-center gap-2">
            <Label htmlFor="suite-k">Retrieval cut-off (k)</Label>
            <Input
              id="suite-k"
              type="number"
              min={1}
              max={50}
              className="w-20"
              value={k}
              onChange={(e) => setK(Number(e.target.value))}
            />
          </div>
          {(["retrieval", "generation"] as const).map((group) => (
            <fieldset key={group} className="grid gap-2">
              <legend className="mb-1 text-sm font-medium capitalize">{group}</legend>
              <div className="grid gap-x-4 gap-y-1.5 sm:grid-cols-3">
                {METRICS.filter((m) => m.group === group && SELECTABLE.includes(m.id)).map((m) => (
                  <label key={m.id} className="flex items-center gap-2 text-sm" title={m.question}>
                    <input
                      type="checkbox"
                      className="size-4 accent-primary"
                      checked={metrics.includes(m.id)}
                      onChange={(e) =>
                        setMetrics((ms) =>
                          e.target.checked ? [...ms, m.id] : ms.filter((x) => x !== m.id),
                        )
                      }
                    />
                    {metricName(m.id, k)}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Judge</CardTitle>
          <CardDescription>
            The model that grades answers. Use a different one from the model under test where you
            can — a local model makes judging free.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="judge-connection">Judge connection</Label>
            <select
              id="judge-connection"
              className={nativeSelect}
              value={judgeConnection ?? ""}
              onChange={(e) => {
                setJudgeConnection(e.target.value ? Number(e.target.value) : null);
                setJudgeModel("");
              }}
            >
              <option value="">Default provider</option>
              {connections.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="judge-model">Judge model</Label>
            <ModelCombobox
              id="judge-model"
              label="Judge model"
              value={judgeModel}
              placeholder={judgeConnection === null ? "Provider's chat model" : "e.g. gemma4:e4b"}
              source={{ connection: judgeConnection }}
              want="chat"
              onChange={(id) => setJudgeModel(id)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
          <div className="grid gap-1.5">
            <CardTitle>Cases</CardTitle>
            <CardDescription>
              Relevance is by document name plus an optional evidence quote — chunk numbers change
              on every re-index, so they're never used.
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInput.current?.click()}
            >
              <Upload className="size-4" /> Import JSONL
            </Button>
            <input
              ref={fileInput}
              type="file"
              accept=".jsonl,.ndjson,application/x-ndjson"
              aria-label="Choose a JSONL file of cases"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  importCases.mutate(file, {
                    onSuccess: ({ added }) => toast.success(`Imported ${added} cases`),
                    onError: (err) => toast.error(detail(err) ?? "Import failed"),
                  });
                }
                e.target.value = "";
              }}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void exportCases(suite).catch(() => toast.error("Export failed"))}
            >
              <Download className="size-4" /> Export JSONL
            </Button>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3">
          {cases.map((c, i) => (
            <fieldset
              key={i}
              aria-label={`Case ${i + 1}`}
              className="grid gap-2 rounded-lg border p-3 sm:grid-cols-[8rem_1fr]"
            >
              <select
                aria-label={`Kind ${i + 1}`}
                className={nativeSelect}
                value={c.kind}
                onChange={(e) => setCase(i, { kind: e.target.value as EvalCase["kind"] })}
              >
                <option value="qa">Q&amp;A</option>
                <option value="refusal">Should refuse</option>
              </select>
              <div className="flex gap-2">
                <Textarea
                  aria-label={`Question ${i + 1}`}
                  rows={1}
                  className="min-h-9 resize-y"
                  placeholder="Question"
                  value={c.question}
                  onChange={(e) => setCase(i, { question: e.target.value })}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove case ${i + 1}`}
                  onClick={() => setCases((cs) => cs.filter((_, j) => j !== i))}
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
              {c.kind === "qa" && (
                <div className="grid gap-2 sm:col-span-2 sm:grid-cols-3">
                  <Input
                    aria-label={`Reference answer ${i + 1}`}
                    placeholder="Reference answer"
                    value={c.reference_answer}
                    onChange={(e) => setCase(i, { reference_answer: e.target.value })}
                  />
                  <Input
                    aria-label={`Relevant document ${i + 1}`}
                    placeholder="Relevant document(s), comma-separated"
                    value={c.relevant_documents.join(", ")}
                    onChange={(e) =>
                      setCase(i, {
                        relevant_documents: e.target.value
                          .split(",")
                          .map((d) => d.trim())
                          .filter(Boolean),
                      })
                    }
                  />
                  <Input
                    aria-label={`Evidence ${i + 1}`}
                    placeholder="Evidence quote (optional)"
                    value={c.evidence}
                    onChange={(e) => setCase(i, { evidence: e.target.value })}
                  />
                </div>
              )}
            </fieldset>
          ))}
          <Button
            type="button"
            variant="outline"
            className="w-fit"
            onClick={() => setCases((cs) => [...cs, emptyCase()])}
          >
            <Plus className="size-4" /> Add case
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Boundaries</CardTitle>
          <CardDescription>
            A run passes only if every applicable boundary holds (n/a metrics are skipped).
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2">
          {boundaries.map((b, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2">
              <select
                aria-label={`Boundary metric ${i + 1}`}
                className={nativeSelect}
                value={b.metric}
                onChange={(e) => setBoundary(i, { metric: e.target.value })}
              >
                {BOUNDARY_METRICS.map((m) => (
                  <option key={m} value={m}>
                    {metricName(m, k)}
                  </option>
                ))}
              </select>
              <select
                aria-label={`Boundary aggregate ${i + 1}`}
                className={nativeSelect}
                value={b.aggregate}
                onChange={(e) =>
                  setBoundary(i, { aggregate: e.target.value as Boundary["aggregate"] })
                }
              >
                <option value="mean">mean</option>
                <option value="p50">p50</option>
                <option value="p95">p95</option>
              </select>
              <select
                aria-label={`Boundary comparator ${i + 1}`}
                className={nativeSelect}
                value={b.comparator}
                onChange={(e) =>
                  setBoundary(i, { comparator: e.target.value as Boundary["comparator"] })
                }
              >
                <option value="gte">≥</option>
                <option value="lte">≤</option>
              </select>
              <Input
                aria-label={`Boundary value ${i + 1}`}
                type="number"
                step="any"
                className="w-24"
                value={b.value}
                onChange={(e) => setBoundary(i, { value: Number(e.target.value) })}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove boundary ${i + 1}`}
                onClick={() => setBoundaries((bs) => bs.filter((_, j) => j !== i))}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            className="w-fit"
            onClick={() =>
              setBoundaries((bs) => [
                ...bs,
                { metric: "faithfulness", aggregate: "mean", comparator: "gte", value: 0.8 },
              ])
            }
          >
            <Plus className="size-4" /> Add boundary
          </Button>
        </CardContent>
      </Card>

      {save.error && (
        <p className="text-sm text-destructive">{detail(save.error) ?? "Couldn't save"}</p>
      )}
      <Button type="submit" className="w-fit" disabled={save.isPending}>
        {save.isPending ? "Saving…" : "Save suite"}
      </Button>
    </form>
  );
}
