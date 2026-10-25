import { useMutation } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useSocketEvents } from "@/hooks/use-socket";
import { api } from "@/lib/api";

type JobState = { runId: string; step: number; total: number; message: string; done: boolean };

/** Try the job → worker → Redis → websocket loop by hand (the demo-index Hatchet task). */
export function DemoJobCard() {
  const [jobs, setJobs] = useState<Record<string, JobState>>({});

  const start = useMutation({
    mutationFn: () =>
      api<{ run_id: string }>("/api/jobs/demo-index/", {
        method: "POST",
        body: JSON.stringify({ steps: 12 }),
      }),
    onSuccess: ({ run_id }) =>
      setJobs((j) => ({
        ...j,
        [run_id]: { runId: run_id, step: 0, total: 12, message: "Queued", done: false },
      })),
    onError: () => toast.error("Couldn't start the job — is the Hatchet worker running?"),
  });

  useSocketEvents((e) => {
    if (e.type === "job.progress") {
      setJobs((j) => ({
        ...j,
        [e.run_id]: {
          runId: e.run_id,
          step: e.step,
          total: e.total,
          message: e.message,
          done: false,
        },
      }));
    } else if (e.type === "job.completed" && e.job === "demo-index") {
      setJobs((j) =>
        j[e.run_id] ? { ...j, [e.run_id]: { ...j[e.run_id], done: true, message: "Done" } } : j,
      );
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Try it: a demo background job</CardTitle>
        <CardDescription>
          Starts the <code className="font-mono">demo-index</code> Hatchet task. The bar moves from
          websocket events; the run shows up in the Hatchet dashboard at{" "}
          <a className="underline" href="http://localhost:8888" target="_blank" rel="noreferrer">
            localhost:8888
          </a>
          .
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Button className="w-fit" onClick={() => start.mutate()} disabled={start.isPending}>
          <Play className="size-4" /> Run demo job
        </Button>
        {Object.values(jobs)
          .reverse()
          .map((job) => (
            <div key={job.runId} className="grid gap-1.5">
              <div className="flex justify-between text-xs">
                <span className="font-mono text-muted-foreground">{job.runId.slice(0, 8)}</span>
                <span>{job.message}</span>
              </div>
              <Progress value={job.done ? 100 : (job.step / job.total) * 100} />
            </div>
          ))}
      </CardContent>
    </Card>
  );
}
