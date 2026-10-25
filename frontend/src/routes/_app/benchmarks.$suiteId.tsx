import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRunEvents, useRuns, useSuite } from "@/features/benchmarks/api";
import { RunPanel } from "@/features/benchmarks/run-panel";
import { RunStatus } from "@/features/benchmarks/run-view";
import { SuiteEditor } from "@/features/benchmarks/suite-editor";

export const Route = createFileRoute("/_app/benchmarks/$suiteId")({
  staticData: { title: "Benchmarks" },
  component: SuitePage,
});

function SuitePage() {
  const suiteId = Number(Route.useParams().suiteId);
  const suite = useSuite(suiteId);
  const runs = useRuns(suiteId);
  useRunEvents();

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-4 p-4 lg:grid-cols-[1fr_340px]">
      <div className="grid min-w-0 gap-4">
        <Link
          to="/benchmarks"
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:underline"
        >
          <ArrowLeft className="size-4" /> All suites
        </Link>
        {suite.data ? (
          // Remount when the saved version changes so the form re-reads it.
          <SuiteEditor key={suite.data.version} suite={suite.data} />
        ) : (
          <Skeleton className="h-96 w-full" />
        )}
      </div>
      <div className="grid h-fit min-w-0 gap-4">
        <RunPanel suiteId={suiteId} />
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Runs</CardTitle>
          </CardHeader>
          <CardContent>
            <ul aria-label="Runs" className="grid gap-2">
              {runs.data?.map((r) => (
                <li key={r.id} className="min-w-0">
                  <Link
                    to="/benchmarks/runs/$runId"
                    params={{ runId: String(r.id) }}
                    className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{r.target_label}</span>
                      <span className="block text-xs text-muted-foreground">
                        {new Date(r.created_at).toLocaleString()}
                      </span>
                    </span>
                    <span className="shrink-0">
                      <RunStatus status={r.status} />
                    </span>
                  </Link>
                </li>
              ))}
              {runs.data?.length === 0 && (
                <li className="text-sm text-muted-foreground">No runs yet.</li>
              )}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
