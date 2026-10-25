import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { METRIC_GROUPS, METRICS, type MetricGroup } from "./metrics";

const SCORING_LABEL = {
  deterministic: "exact",
  "llm-judge": "LLM judge",
  measured: "measured",
} as const;

/** Grouped list of every metric. Used on the Benchmarks page and the System Design page. */
export function MetricCatalog() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {(Object.keys(METRIC_GROUPS) as MetricGroup[]).map((group) => (
        <Card key={group} className="gap-3">
          <CardHeader>
            <CardTitle className="text-base">{METRIC_GROUPS[group].title}</CardTitle>
            <CardDescription>{METRIC_GROUPS[group].blurb}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {METRICS.filter((m) => m.group === group).map((m) => (
              <div key={m.id} className="grid gap-0.5 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{m.name}</span>
                  <Badge variant="outline" className="text-[10px]">
                    {SCORING_LABEL[m.scoring]}
                  </Badge>
                  {m.needs !== "—" && (
                    <span className="text-xs text-muted-foreground">needs {m.needs}</span>
                  )}
                </div>
                <p className="text-muted-foreground">{m.question}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
