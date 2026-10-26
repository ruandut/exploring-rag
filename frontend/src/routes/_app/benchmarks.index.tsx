import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { FlaskConical, Plus } from "lucide-react";
import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSaveSuite, useSuites } from "@/features/benchmarks/api";
import { MetricCatalog } from "@/features/benchmarks/metric-catalog";
import { metricName } from "@/features/benchmarks/metrics";
import { DeletedSuiteRuns } from "@/features/benchmarks/deleted-suite-runs";
import { ModelSpeed } from "@/features/benchmarks/model-speed";
import { FolderDialog } from "@/features/library/folder-dialog";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";

export const Route = createFileRoute("/_app/benchmarks/")({
  staticData: { title: "Benchmarks" },
  component: BenchmarksPage,
});

function BenchmarksPage() {
  const suites = useSuites();
  const create = useSaveSuite();
  const navigate = useNavigate();
  const [naming, setNaming] = useState(false);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="max-w-2xl text-sm text-muted-foreground">
          A suite is a set of questions with the answers you expect, the metrics that score them and
          the boundaries a run must meet. Run it against an agent or a bare model, and compare.
        </p>
        <Button onClick={() => setNaming(true)}>
          <Plus className="size-4" /> New suite
        </Button>
      </div>

      {suites.isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : suites.data?.length ? (
        <ul aria-label="Suites" className="grid gap-3 md:grid-cols-2">
          {suites.data.map((s) => (
            <li key={s.id} aria-label={s.name}>
              <Link to="/benchmarks/$suiteId" params={{ suiteId: String(s.id) }} className="block">
                <Card className="h-full gap-2 transition-colors hover:bg-muted/40">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <FlaskConical className="size-4" /> {s.name}
                    </CardTitle>
                    <CardDescription>
                      {s.case_count} cases · version {s.version}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="text-xs text-muted-foreground">
                    {s.metrics.map((m) => metricName(m, s.k)).join(", ") || "No metrics selected"}
                  </CardContent>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <FlaskConical className="size-6" />
            <p className="text-sm">No suites yet. Create one to start measuring your agents.</p>
          </CardContent>
        </Card>
      )}

      <DeletedSuiteRuns />

      <ModelSpeed />

      <div>
        <h2 className="mb-1 text-lg font-semibold">Metric catalog</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          What each metric measures. Injection, format and cost metrics arrive with spec 0007.
        </p>
        <MetricCatalog />
      </div>

      {naming && (
        <FolderDialog
          title="New suite"
          submitLabel="Create suite"
          fieldLabel="Suite name"
          pending={create.isPending}
          error={create.error instanceof ApiError ? JSON.stringify(create.error.body) : undefined}
          onClose={() => {
            create.reset();
            setNaming(false);
          }}
          onSubmit={(name) =>
            create.mutate(
              { name, metrics: ["faithfulness", "answer_relevancy"], cases: [], boundaries: [] },
              {
                onSuccess: (suite) =>
                  void navigate({
                    to: "/benchmarks/$suiteId",
                    params: { suiteId: String(suite.id) },
                  }),
              },
            )
          }
        />
      )}
    </div>
  );
}
