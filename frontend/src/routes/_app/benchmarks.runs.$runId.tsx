import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { type RunDetail, useRun, useRunEvents } from "@/features/benchmarks/api";
import { metricName } from "@/features/benchmarks/metrics";
import { fmt, metricRows, RunView } from "@/features/benchmarks/run-view";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/benchmarks/runs/$runId")({
  staticData: { title: "Benchmarks" },
  component: RunPage,
});

function RunPage() {
  const runId = Number(Route.useParams().runId);
  const run = useRun(runId);
  const siblingId = run.data?.siblings[0] ?? null;
  const sibling = useRun(siblingId);
  const [live, setLive] = useState<Record<number, { done: number; total: number }>>({});
  useRunEvents((id, done, total) => setLive((l) => ({ ...l, [id]: { done, total } })));

  if (!run.data) return <Skeleton className="m-4 h-96" />;
  const runs = [run.data, sibling.data].filter((r): r is RunDetail => !!r);
  // The bare model goes on the left so deltas read "what the agent adds".
  runs.sort((a, b) =>
    a.target_kind === b.target_kind ? a.id - b.id : a.target_kind === "model" ? -1 : 1,
  );

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-4 p-4">
      {run.data.suite && (
        <Link
          to="/benchmarks/$suiteId"
          params={{ suiteId: String(run.data.suite) }}
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:underline"
        >
          <ArrowLeft className="size-4" /> {run.data.suite_name}
        </Link>
      )}
      {runs.length === 2 && <Comparison a={runs[0]} b={runs[1]} />}
      <div className={cn("grid gap-4", runs.length === 2 && "lg:grid-cols-2")}>
        {runs.map((r) => (
          <RunView key={r.id} run={r} live={r.status === "running" ? live[r.id] : undefined} />
        ))}
      </div>
    </div>
  );
}

function Comparison({ a, b }: { a: RunDetail; b: RunDetail }) {
  const k = a.suite_snapshot.k;
  const metrics = [...new Set([...metricRows(a), ...metricRows(b)])];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Side by side</CardTitle>
        <CardDescription>
          Δ = {b.target_label} minus {a.target_label}. n/a means the metric doesn't apply (a bare
          model retrieves nothing).
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table aria-label="Comparison">
          <TableHeader>
            <TableRow>
              <TableHead>Metric (mean)</TableHead>
              <TableHead className="text-right">{a.target_label}</TableHead>
              <TableHead className="text-right">{b.target_label}</TableHead>
              <TableHead className="text-right">Δ</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {metrics.map((m) => {
              const va = a.summary.metrics?.[m]?.mean ?? null;
              const vb = b.summary.metrics?.[m]?.mean ?? null;
              const delta = va !== null && vb !== null ? vb - va : null;
              return (
                <TableRow key={m} aria-label={metricName(m, k)}>
                  <TableCell>{metricName(m, k)}</TableCell>
                  <TableCell className="text-right tabular-nums">{fmt(va)}</TableCell>
                  <TableCell className="text-right tabular-nums">{fmt(vb)}</TableCell>
                  <TableCell
                    aria-label="Delta"
                    className={cn(
                      "text-right tabular-nums",
                      delta !== null && delta > 0 && "text-emerald-600",
                      delta !== null && delta < 0 && "text-destructive",
                    )}
                  >
                    {delta === null ? "n/a" : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
