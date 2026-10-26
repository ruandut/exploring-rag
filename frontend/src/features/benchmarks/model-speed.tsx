import { Gauge } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { useModelSpeed } from "./api";
import { fmt } from "./run-view";

/** How fast each model answered across all your finished runs (spec 0011). Agent runs and
 *  bare runs of the same model pool together: this is the model's speed, not the agent's. */
export function ModelSpeed() {
  const speed = useModelSpeed();
  if (!speed.data?.length) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="size-4" /> Model speed
        </CardTitle>
        <CardDescription>
          Every finished case of every run, grouped by the model that answered. Typical = p50; slow
          cases = p95. Fastest first by tokens per second.
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table aria-label="Model speed">
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead className="text-right">Runs</TableHead>
              <TableHead className="text-right">Cases</TableHead>
              <TableHead className="text-right">First token (s, typical)</TableHead>
              <TableHead className="text-right">Total (s, slow cases)</TableHead>
              <TableHead className="text-right">Tokens/s (typical)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {speed.data.map((r) => (
              <TableRow key={r.model} aria-label={r.model}>
                <TableCell>{r.model}</TableCell>
                <TableCell aria-label="Runs" className="text-right tabular-nums">
                  {r.runs}
                </TableCell>
                <TableCell className="text-right tabular-nums">{r.cases}</TableCell>
                <TableCell className="text-right tabular-nums">{fmt(r.ttft_p50)}</TableCell>
                <TableCell className="text-right tabular-nums">{fmt(r.latency_p95)}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {fmt(r.tokens_per_second_p50, 1)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
