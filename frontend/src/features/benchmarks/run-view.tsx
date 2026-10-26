import { CheckCircle2, ChevronRight, Loader2, MinusCircle, RotateCcw, XCircle } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

import { type CaseResult, type RunDetail, useRetryFailed } from "./api";
import { metricName, PHASES } from "./metrics";

const COMPARATOR = { gte: "≥", lte: "≤" } as const;

export function fmt(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "n/a" : value.toFixed(digits);
}

/** Seconds with one decimal, or "n/a". Takes milliseconds. */
export function secs(ms: number | null | undefined): string {
  return ms === null || ms === undefined ? "n/a" : `${(ms / 1000).toFixed(2)} s`;
}

/** "1m 12s" / "8s" — how long a whole run took. */
export function duration(from: string, to: string): string {
  const total = Math.max(0, Math.round((Date.parse(to) - Date.parse(from)) / 1000));
  const m = Math.floor(total / 60);
  return m ? `${m}m ${total % 60}s` : `${total}s`;
}

export function RunStatus({ status }: { status: RunDetail["status"] }) {
  const style = {
    running: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    passed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    failed: "bg-destructive/15 text-destructive",
  }[status];
  return (
    <Badge aria-label="Run status" className={cn("border-0 capitalize", style)}>
      {status === "running" && <Loader2 className="size-3 animate-spin" />}
      {status === "running" ? "Running" : status === "passed" ? "Passed" : "Failed"}
    </Badge>
  );
}

/** Metrics shown for a run: the suite's selections, refusal rate if any, then operational. */
export function metricRows(run: RunDetail): string[] {
  const ids = Object.keys(run.summary.metrics ?? {});
  const order = [
    ...run.suite_snapshot.metrics,
    "refusal_rate",
    "ttft",
    "latency_total",
    "tokens",
    "tokens_per_second",
    "waiting_time",
    "search_time",
    "reasoning_time",
    "writing_time",
    "judge_time",
    "error_rate",
  ];
  return order.filter((m, i) => ids.includes(m) && order.indexOf(m) === i);
}

export function RunView({ run, live }: { run: RunDetail; live?: { done: number; total: number } }) {
  const retry = useRetryFailed();
  const k = run.suite_snapshot.k;
  const done = live?.done ?? run.results.filter((r) => r.status !== "pending").length;
  const total = live?.total ?? run.results.length;
  const snap = run.target_snapshot;

  return (
    <div className="grid min-w-0 gap-4" aria-label={`Run ${run.target_label}`} role="region">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
          <div className="grid gap-1.5">
            <CardTitle className="flex flex-wrap items-center gap-2">
              {run.target_label} <RunStatus status={run.status} />
            </CardTitle>
            <CardDescription>
              {run.suite_name} · version {run.suite_snapshot.version} ·{" "}
              {new Date(run.created_at).toLocaleString()}
              {run.finished_at && (
                // Start to finish, queueing included: the time you actually waited.
                <span aria-label="Run duration">
                  {" "}
                  · Took {duration(run.created_at, run.finished_at)}
                </span>
              )}
            </CardDescription>
            {run.target_kind === "agent" && (
              <p aria-label="Run embedding" className="text-xs text-muted-foreground">
                {snap.embedding
                  ? `Embedding: ${snap.embedding.name} (${snap.embedding.model}, ${
                      snap.embedding.dimensions ?? "?"
                    } dims, ${snap.embedding.strategy} ${snap.embedding.chunk_size}/${
                      snap.embedding.chunk_overlap
                    })`
                  : snap.embedding === null
                    ? "No embedding (the model answered alone)"
                    : "Embedding: all documents (before spec 0010)"}{" "}
                · Model: {(snap.connection_name as string | null) ?? "Default provider"} ·{" "}
                {(snap.model as string) || "provider default"}
              </p>
            )}
          </div>
          {run.status !== "running" && run.summary.failed_cases > 0 && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => retry.mutate(run.id)}
              disabled={retry.isPending}
            >
              <RotateCcw className="size-4" /> Retry failed cases
            </Button>
          )}
        </CardHeader>
        <CardContent className="grid gap-3">
          <div className="grid gap-1.5">
            <div className="flex justify-between text-sm">
              <span aria-label="Progress">
                {done} / {total}
              </span>
              {run.status !== "running" && (
                <span
                  aria-label="Failed cases"
                  className={cn(run.summary.failed_cases > 0 && "text-destructive")}
                >
                  {run.summary.failed_cases} failed cases
                </span>
              )}
            </div>
            <Progress value={total ? (done / total) * 100 : 0} />
          </div>
          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground">
              Target configuration (snapshot)
            </summary>
            <dl className="mt-2 grid gap-1 text-xs">
              {snap.system_message !== undefined && (
                <>
                  <dt className="font-medium">System message</dt>
                  <dd
                    aria-label="Snapshot system message"
                    className="whitespace-pre-wrap text-muted-foreground"
                  >
                    {snap.system_message || "(none)"}
                  </dd>
                </>
              )}
              <dt className="font-medium">Model</dt>
              <dd className="text-muted-foreground">
                {(snap.connection_name as string | null) ?? "Default provider"} ·{" "}
                {(snap.model as string) || "provider default"}
              </dd>
              {snap.rag_config && (
                <>
                  <dt className="font-medium">RAG</dt>
                  <dd className="font-mono text-muted-foreground">
                    {JSON.stringify(snap.rag_config)}
                  </dd>
                </>
              )}
            </dl>
          </details>
        </CardContent>
      </Card>

      {run.summary.boundaries && run.summary.boundaries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Boundaries</CardTitle>
          </CardHeader>
          <CardContent>
            <ul aria-label="Boundaries" className="grid gap-1.5 text-sm">
              {run.summary.boundaries.map((b, i) => {
                const label = `${b.metric} ${b.aggregate} ${COMPARATOR[b.comparator]} ${b.value}`;
                return (
                  <li key={i} aria-label={label} className="flex flex-wrap items-center gap-2">
                    {b.passed === null ? (
                      <MinusCircle className="size-4 text-muted-foreground" />
                    ) : b.passed ? (
                      <CheckCircle2 className="size-4 text-emerald-500" />
                    ) : (
                      <XCircle className="size-4 text-destructive" />
                    )}
                    <span>
                      {metricName(b.metric, k)} {b.aggregate} {COMPARATOR[b.comparator]} {b.value}
                    </span>
                    <span className="text-muted-foreground">
                      {b.passed === null ? "skipped (n/a)" : `actual ${fmt(b.actual)} · margin `}
                      {b.passed !== null && (
                        <span className={cn(b.passed ? "text-emerald-600" : "text-destructive")}>
                          {b.margin! >= 0 ? "+" : ""}
                          {fmt(b.margin)}
                        </span>
                      )}
                    </span>
                    <span className="sr-only">
                      {b.passed === null ? "skipped" : b.passed ? "✓" : "✗"}
                    </span>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}

      {run.summary.metrics && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Metrics</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table aria-label="Metrics">
              <TableHeader>
                <TableRow>
                  <TableHead>Metric</TableHead>
                  <TableHead className="text-right">Mean</TableHead>
                  <TableHead className="text-right">p50</TableHead>
                  <TableHead className="text-right">p95</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {metricRows(run).map((m) => {
                  const s = run.summary.metrics![m];
                  return (
                    <TableRow key={m} aria-label={metricName(m, k)}>
                      <TableCell>{metricName(m, k)}</TableCell>
                      <TableCell className="text-right tabular-nums">{fmt(s.mean)}</TableCell>
                      <TableCell className="text-right tabular-nums">{fmt(s.p50)}</TableCell>
                      <TableCell className="text-right tabular-nums">{fmt(s.p95)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {run.summary.metrics && <TimingCard run={run} />}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cases</CardTitle>
          <CardDescription>
            Open a case to see the answer, what was retrieved, and how each score was reached.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul aria-label="Case results" className="grid gap-2">
            {run.results.map((r) => (
              <CaseRow key={r.id} result={r} k={k} />
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

const PHASE_COLOURS = ["bg-chart-1", "bg-chart-2", "bg-chart-3", "bg-chart-4"];

/** One stacked bar: the mean time per phase, so the bottleneck is visible at a glance. */
function TimingCard({ run }: { run: RunDetail }) {
  const metrics = run.summary.metrics ?? {};
  const parts = PHASES.map((p, i) => ({
    ...p,
    seconds: metrics[p.id]?.mean ?? null,
    colour: PHASE_COLOURS[i],
  }));
  const total = parts.reduce((sum, p) => sum + (p.seconds ?? 0), 0);
  // Runs from before spec 0011 have no phases.
  if (parts.every((p) => p.seconds === null)) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Timing</CardTitle>
        <CardDescription>
          Mean time per case, split by where it went. The judge's time isn't included.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-2">
        <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
          {total > 0 &&
            parts.map((p) =>
              p.seconds ? (
                <div
                  key={p.id}
                  className={p.colour}
                  style={{ width: `${(p.seconds / total) * 100}%` }}
                />
              ) : null,
            )}
        </div>
        <ul aria-label="Time per phase" className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {parts.map((p) => {
            const value = p.seconds === null ? "n/a" : `${p.seconds.toFixed(2)} s`;
            return (
              <li
                key={p.id}
                aria-label={`${p.name} ${value}`}
                className="flex items-center gap-1.5"
              >
                <span className={cn("size-2.5 rounded-sm", p.colour)} />
                {p.name} <span className="tabular-nums text-muted-foreground">{value}</span>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}

function CaseRow({ result, k }: { result: CaseResult; k: number }) {
  const [open, setOpen] = useState(false);
  const label =
    result.status === "pending"
      ? "Pending"
      : result.status === "failed"
        ? "Error"
        : result.passed
          ? "Passed"
          : "Failed";

  return (
    <li aria-label={result.case.question} className="rounded-lg border">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm"
      >
        <ChevronRight className={cn("size-4 shrink-0 transition-transform", open && "rotate-90")} />
        <span className="min-w-0 flex-1 truncate">{result.case.question}</span>
        {result.latency_ms !== null && (
          <span className="text-xs text-muted-foreground tabular-nums">
            {(result.latency_ms / 1000).toFixed(1)} s
          </span>
        )}
        <Badge
          aria-label="Case status"
          variant="outline"
          className={cn(
            label === "Passed" && "text-emerald-600",
            (label === "Failed" || label === "Error") && "text-destructive",
          )}
        >
          {result.status === "pending" && <Loader2 className="size-3 animate-spin" />}
          {label}
        </Badge>
      </button>
      {open && (
        <div className="grid gap-3 border-t px-3 py-3 text-sm">
          {result.error && <p className="text-destructive">{result.error}</p>}
          <div>
            <div className="text-xs font-medium text-muted-foreground">Answer</div>
            <p aria-label="Case answer" className="whitespace-pre-wrap">
              {result.answer || "—"}
            </p>
          </div>
          {result.case.reference_answer && (
            <div>
              <div className="text-xs font-medium text-muted-foreground">Reference answer</div>
              <p>{result.case.reference_answer}</p>
            </div>
          )}
          <div>
            <div className="text-xs font-medium text-muted-foreground">
              Retrieved ({result.retrieved.length})
            </div>
            <ul aria-label="Case retrieved chunks" className="grid gap-1">
              {result.retrieved.map((c) => (
                <li
                  key={`${c.document}#${c.chunk}`}
                  aria-label={`${c.document}#${c.chunk}`}
                  className="text-xs"
                >
                  <span className="font-mono">
                    {c.document}#{c.chunk}
                  </span>{" "}
                  <span className="text-muted-foreground">{c.text.slice(0, 160)}</span>
                </li>
              ))}
              {result.retrieved.length === 0 && (
                <li className="text-xs text-muted-foreground">Nothing retrieved.</li>
              )}
            </ul>
          </div>
          <div>
            <div className="text-xs font-medium text-muted-foreground">Scores</div>
            <ul aria-label="Case scores" className="grid gap-1">
              {Object.entries(result.scores).map(([m, v]) => (
                <li key={m} aria-label={metricName(m, k)} className="text-xs">
                  <span className="font-medium">
                    {metricName(m, k)}: {fmt(v)}
                  </span>{" "}
                  <span className="text-muted-foreground">— {result.explanations[m]}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="grid gap-1 text-xs text-muted-foreground">
            <div aria-label="Case speed">
              First token {secs(result.ttft_ms)} · total {secs(result.latency_ms)} · ~
              {result.tokens ?? "—"} answer tokens ·{" "}
              {result.tokens_per_second === null ? "n/a" : `${result.tokens_per_second.toFixed(1)}`}{" "}
              tokens/s
            </div>
            <ul aria-label="Case timing" className="flex flex-wrap gap-x-3">
              {PHASES.map((p) => (
                <li key={p.id} aria-label={p.name}>
                  {p.name} {secs(result[p.field])}
                </li>
              ))}
            </ul>
            <div aria-label="Case judge time">
              Judge {secs(result.judge_ms)} (not counted above)
            </div>
          </div>
        </div>
      )}
    </li>
  );
}
