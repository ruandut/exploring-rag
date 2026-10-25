import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MetricCatalog } from "@/features/benchmarks/metric-catalog";
import { ArchitectureDiagram } from "@/features/system-design/architecture-diagram";
import { DemoJobCard } from "@/features/system-design/demo-job";
import { SPECS } from "@/features/system-design/specs";
import {
  CHAT_FLOW,
  COMPONENTS,
  DJANGO_APPS,
  EVAL_FLOW,
  GLOSSARY,
  GOTCHAS,
  HATCHET_FEATURES,
  INDEXING_STEPS,
  JOB_FLOW,
  LAST_UPDATED,
  QUERY_STEPS,
  SPEC_TO_TEST,
  TEST_LAYERS,
  TEST_RULES,
  type Status,
  type Step,
} from "@/features/system-design/content";
import { useSocketStatus } from "@/hooks/use-socket";
import { api, type Health } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/system-design")({
  staticData: { title: "System design" },
  component: SystemDesignPage,
});

const STATUS_BADGE: Record<Status, string> = {
  live: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  demo: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  planned: "bg-muted text-muted-foreground",
};

function StatusBadge({ status }: { status: Status }) {
  return <Badge className={cn("border-0 capitalize", STATUS_BADGE[status])}>{status}</Badge>;
}

function SystemDesignPage() {
  return (
    <div className="mx-auto w-full max-w-5xl p-4">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <p className="max-w-2xl text-sm text-muted-foreground">
          How this system is built and how RAG works inside it, step by step. Badges show what's{" "}
          <StatusBadge status="live" /> today, <StatusBadge status="demo" /> with fake data, or{" "}
          <StatusBadge status="planned" /> in a drafted spec.
        </p>
        <span className="text-xs text-muted-foreground">Updated {LAST_UPDATED}</span>
      </div>

      <Tabs defaultValue="architecture">
        <TabsList className="flex-wrap">
          <TabsTrigger value="architecture">Architecture</TabsTrigger>
          <TabsTrigger value="rag">How RAG works</TabsTrigger>
          <TabsTrigger value="realtime">Realtime & jobs</TabsTrigger>
          <TabsTrigger value="evaluation">Evaluation</TabsTrigger>
          <TabsTrigger value="testing">Testing</TabsTrigger>
          <TabsTrigger value="glossary">Glossary & specs</TabsTrigger>
        </TabsList>

        <TabsContent value="architecture" className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>The big picture</CardTitle>
              <CardDescription>
                Solid boxes run today; dashed boxes arrive with a later spec.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ArchitectureDiagram />
            </CardContent>
          </Card>
          <LiveHealth />
          <Card>
            <CardHeader>
              <CardTitle>Components</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Component</TableHead>
                    <TableHead>Responsibility</TableHead>
                    <TableHead>How it runs</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {COMPONENTS.map((c) => (
                    <TableRow key={c.name} className="align-top">
                      <TableCell className="min-w-44 whitespace-normal">
                        <div className="font-medium">{c.name}</div>
                        <div className="text-xs text-muted-foreground">{c.tech}</div>
                      </TableCell>
                      <TableCell className="min-w-64 whitespace-normal">{c.role}</TableCell>
                      <TableCell className="min-w-48 font-mono text-xs whitespace-normal">
                        {c.runs}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={c.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Backend Django apps</CardTitle>
              <CardDescription>
                One app per domain, layered: an app may only import from apps it depends on
                (enforced by <code>apps/core/test_architecture.py</code>). Cross-app calls go
                through the other app&apos;s <code>services.py</code> / <code>selectors.py</code>.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>App</TableHead>
                    <TableHead>Owns</TableHead>
                    <TableHead>May import</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {DJANGO_APPS.map((a) => (
                    <TableRow key={a.name} className="align-top">
                      <TableCell>
                        <div className="font-mono font-medium">apps.{a.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {a.layer}
                          {a.spec && ` · spec ${a.spec}`}
                        </div>
                      </TableCell>
                      <TableCell className="min-w-64 whitespace-normal">{a.owns}</TableCell>
                      <TableCell className="min-w-40 text-xs whitespace-normal text-muted-foreground">
                        {a.dependsOn}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={a.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="rag" className="flex flex-col gap-6">
          <section>
            <h2 className="mb-1 text-lg font-semibold">Phase 1 · Indexing (once per document)</h2>
            <p className="mb-3 text-sm text-muted-foreground">
              Runs in the background on Hatchet when you upload. Turns documents into searchable
              vectors.
            </p>
            <StepList label="Indexing steps" steps={INDEXING_STEPS} />
          </section>
          <section>
            <h2 className="mb-1 text-lg font-semibold">Phase 2 · Answering (every question)</h2>
            <p className="mb-3 text-sm text-muted-foreground">
              Runs as an agent run on Hatchet, streamed live to the Chat page.
            </p>
            <StepList label="Answering steps" steps={QUERY_STEPS} />
          </section>
        </TabsContent>

        <TabsContent value="realtime" className="flex flex-col gap-4">
          <FlowCard
            title="What happens when you send a chat message"
            description="Agent runs are Hatchet tasks; their output is a Hatchet stream relayed to your socket."
            steps={CHAT_FLOW}
          />
          <FlowCard
            title="What happens when a background job reports progress"
            description="Jobs push to your user group through the Redis channel layer — every open tab updates."
            steps={JOB_FLOW}
          />
          <DemoJobCard />
          <Card>
            <CardHeader>
              <CardTitle>Hatchet features in use</CardTitle>
              <CardDescription>
                Dashboard at{" "}
                <a
                  className="underline"
                  href="http://localhost:8888"
                  target="_blank"
                  rel="noreferrer"
                >
                  localhost:8888
                </a>{" "}
                — inspect runs, logs, streams; cancel or replay failures.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2">
              {HATCHET_FEATURES.map((f) => (
                <div
                  key={f.name}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2"
                >
                  <div>
                    <div className="text-sm font-medium">{f.name}</div>
                    <code className="text-xs text-muted-foreground">{f.where}</code>
                  </div>
                  <StatusBadge status={f.status} />
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="size-4" /> Gotchas worth knowing
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="grid list-disc gap-2 pl-5 text-sm">
                {GOTCHAS.map((g) => (
                  <li key={g}>{g}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="evaluation" className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Why evaluate?</CardTitle>
              <CardDescription>
                Every RAG option (chunk size, HyDE, hybrid search, reranking, the model) trades
                quality, speed and cost. Benchmarks turn &quot;feels better&quot; into numbers: run
                the same suite before and after a change and compare. Always include a bare-LLM
                baseline — it shows what retrieval actually adds.
              </CardDescription>
            </CardHeader>
          </Card>
          <FlowCard
            title="What happens when you run a benchmark"
            description="Spec 0006 — Django apps scoring (how to score), evals (what to test) and benchmarks (running tests). Try it under Benchmarks."
            steps={EVAL_FLOW}
          />
          <MetricCatalog />
        </TabsContent>

        <TabsContent value="testing" className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Specs are the tests</CardTitle>
              <CardDescription>
                Specification by Example / BDD: each spec in <code>specs/</code> is a Markdown file
                that people read and Cucumber executes. The documentation can&apos;t drift from the
                app, because if it does, the build goes red.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap items-center gap-2 text-sm" aria-label="Test pipeline">
                {[
                  "specs/*.feature.md",
                  "Cucumber.js",
                  "Step definitions",
                  "Page objects · ApiClient · SocketClient",
                  "Playwright · HTTP · WebSocket",
                  "Running app (+ fake LLM)",
                ].map((label, i, all) => (
                  <span key={label} className="flex items-center gap-2">
                    <span className="rounded-md border bg-muted/40 px-2.5 py-1 font-mono text-xs">
                      {label}
                    </span>
                    {i < all.length - 1 && <span className="text-muted-foreground">→</span>}
                  </span>
                ))}
              </div>
              <pre className="mt-4 overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs">{`## Scenario: AT-0004-03 — Overlap must be smaller than the chunk size
* Given I open the Indexing settings
* When I set the chunk size to 256 and the overlap to 256
* Then I see "Overlap must be smaller than the chunk size."`}</pre>
            </CardContent>
          </Card>
          <FlowCard
            title="How specs become tests"
            description="From a Markdown file to a real browser clicking through the app."
            steps={SPEC_TO_TEST.map((s) => `${s.title} — ${s.detail}`)}
          />
          <Card>
            <CardHeader>
              <CardTitle>Test layers</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table aria-label="Test layers">
                <TableHeader>
                  <TableRow>
                    <TableHead>Layer</TableHead>
                    <TableHead>Proves</TableHead>
                    <TableHead>Run</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {TEST_LAYERS.map((l) => (
                    <TableRow key={l.name} className="align-top">
                      <TableCell className="min-w-48 whitespace-normal">
                        <div className="font-medium">{l.name}</div>
                        <div className="text-xs text-muted-foreground">{l.tool}</div>
                      </TableCell>
                      <TableCell className="min-w-64 whitespace-normal">
                        {l.proves}
                        <div className="mt-1 font-mono text-xs text-muted-foreground">
                          {l.where}
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{l.runs}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Rules we build by</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="grid list-disc gap-2 pl-5 text-sm">
                {TEST_RULES.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="glossary" className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Glossary</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-3 text-sm">
                {GLOSSARY.map(([term, def]) => (
                  <div key={term}>
                    <dt className="font-medium">{term}</dt>
                    <dd className="text-muted-foreground">{def}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
          <Card className="h-fit">
            <CardHeader>
              <CardTitle>Specs</CardTitle>
              <CardDescription>
                Read from the specs/ folder at build time. Executable specs run with{" "}
                <code>make acceptance</code>.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul aria-label="Specs" className="grid gap-2">
                {SPECS.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-2 text-sm">
                    <span className="min-w-0">
                      <span className="font-mono text-muted-foreground">{s.id}</span> {s.title}
                      <span className="block text-xs text-muted-foreground">
                        {s.scenarios} scenarios{s.executable ? " · executable" : ""}
                      </span>
                    </span>
                    <Badge variant={s.status === "Done" ? "default" : "outline"}>{s.status}</Badge>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StepList({ label, steps }: { label: string; steps: Step[] }) {
  return (
    <ol aria-label={label} className="grid gap-3">
      {steps.map((s) => (
        <li key={s.n}>
          <Card className="gap-3 py-4">
            <CardHeader className="px-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                  {s.n}
                </span>
                <CardTitle className="text-base">{s.title}</CardTitle>
                <StatusBadge status={s.status} />
                {s.spec && <span className="text-xs text-muted-foreground">spec {s.spec}</span>}
              </div>
            </CardHeader>
            <CardContent className="grid gap-2 px-4 text-sm sm:pl-14">
              <p>{s.what}</p>
              <p className="text-muted-foreground">
                <span className="font-medium text-foreground">In this system: </span>
                {s.here}
              </p>
              {s.options && (
                <ul className="grid list-disc gap-1 pl-5 text-muted-foreground">
                  {s.options.map((o) => (
                    <li key={o}>{o}</li>
                  ))}
                </ul>
              )}
              {s.code && (
                <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs">
                  {s.code}
                </pre>
              )}
            </CardContent>
          </Card>
        </li>
      ))}
    </ol>
  );
}

function FlowCard({
  title,
  description,
  steps,
}: {
  title: string;
  description: string;
  steps: string[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="grid gap-3">
          {steps.map((step, i) => (
            <li key={i} className="flex gap-3 text-sm">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium">
                {i + 1}
              </span>
              <span className="pt-0.5">{step}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function LiveHealth() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/api/health/"),
    refetchInterval: 10_000,
  });
  const ws = useSocketStatus();
  const items: [string, string | undefined][] = [
    ["Postgres", health.data?.postgres],
    ["pgvector", health.data?.pgvector && `v${health.data.pgvector}`],
    ["Redis", health.data?.redis],
    ["Your websocket", ws === "open" ? "ok" : ws],
  ];
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {items.map(([name, value]) => {
        const ok = value === "ok" || value?.startsWith("v");
        return (
          <div key={name} className="rounded-lg border bg-card px-3 py-2">
            <div className="text-xs text-muted-foreground">{name}</div>
            <div
              className={cn(
                "flex items-center gap-1.5 text-sm font-medium",
                !ok && "text-destructive",
              )}
            >
              <span className={cn("size-2 rounded-full", ok ? "bg-emerald-500" : "bg-red-500")} />
              {value ?? (health.isError ? "unreachable" : "…")}
            </div>
          </div>
        );
      })}
    </div>
  );
}
