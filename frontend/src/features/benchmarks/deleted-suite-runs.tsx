import { Link } from "@tanstack/react-router";
import { Archive } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { useDeletedSuiteRuns } from "./api";
import { RunStatus } from "./run-view";

/** Runs whose suite was deleted (spec 0014). They're kept on purpose — each carries a snapshot
 *  of the suite it tested — so their results stay reachable. Hidden when there are none. */
export function DeletedSuiteRuns() {
  const runs = useDeletedSuiteRuns();
  if (!runs.data?.length) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Archive className="size-4" /> Runs of deleted suites
        </CardTitle>
        <CardDescription>
          Their suites are gone, but each run kept a copy of the suite it tested.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul aria-label="Runs of deleted suites" className="grid gap-1">
          {runs.data.map((r) => (
            <li key={r.id} aria-label={`${r.suite_name} × ${r.target_label}`} className="min-w-0">
              <Link
                to="/benchmarks/runs/$runId"
                params={{ runId: String(r.id) }}
                className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate">
                    {r.suite_name} <span className="text-muted-foreground">× {r.target_label}</span>
                  </span>
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
        </ul>
      </CardContent>
    </Card>
  );
}
