import { useNavigate } from "@tanstack/react-router";
import { Play } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAgents, useConnections, useModels } from "@/features/agents/api";
import { ApiError } from "@/lib/api";

import { type Target, useStartRun } from "./api";
import { nativeSelect } from "./suite-editor";

/** "agent:12", "model:default" or "model:3" (a connection) + a model name for bare models. */
function TargetPicker({
  id,
  label,
  value,
  model,
  onChange,
  onModel,
}: {
  id: string;
  label: string;
  value: string;
  model: string;
  onChange: (v: string) => void;
  onModel: (m: string) => void;
}) {
  const agents = useAgents();
  const connections = useConnections();
  const bare = value.startsWith("model:");
  const connection = value === "model:default" || !bare ? null : Number(value.split(":")[1]);
  const models = useModels(connection, bare);

  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        className={nativeSelect}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Choose…</option>
        <optgroup label="Agents (full RAG)">
          {agents.data?.map((a) => (
            <option key={a.id} value={`agent:${a.id}`}>
              {a.name}
            </option>
          ))}
        </optgroup>
        <optgroup label="Bare model (no retrieval — the baseline)">
          <option value="model:default">Bare model · Default provider</option>
          {connections.data?.map((c) => (
            <option key={c.id} value={`model:${c.id}`}>
              Bare model · {c.name}
            </option>
          ))}
        </optgroup>
      </select>
      {bare && (
        <>
          <Input
            aria-label={`${label} model`}
            list={`${id}-models`}
            placeholder={connection === null ? "Provider's chat model" : "Model name"}
            value={model}
            onChange={(e) => onModel(e.target.value)}
            autoComplete="off"
          />
          <datalist id={`${id}-models`}>
            {models.data?.models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </>
      )}
    </div>
  );
}

function toTarget(value: string, model: string): Target | null {
  if (value.startsWith("agent:")) return { kind: "agent", agent: Number(value.slice(6)) };
  if (value === "model:default") return { kind: "model", connection: null, model };
  if (value.startsWith("model:"))
    return { kind: "model", connection: Number(value.slice(6)), model };
  return null;
}

export function RunPanel({ suiteId }: { suiteId: number }) {
  const navigate = useNavigate();
  const start = useStartRun();
  const [first, setFirst] = useState("");
  const [firstModel, setFirstModel] = useState("");
  const [compare, setCompare] = useState(false);
  const [second, setSecond] = useState("");
  const [secondModel, setSecondModel] = useState("");

  function run() {
    const targets = [
      toTarget(first, firstModel),
      compare ? toTarget(second, secondModel) : null,
    ].filter((t): t is Target => t !== null);
    if (!targets.length || (compare && targets.length < 2)) return;
    start.mutate(
      { suite: suiteId, targets },
      {
        onSuccess: (runs) =>
          void navigate({
            to: "/benchmarks/runs/$runId",
            params: { runId: String(runs[0].id) },
          }),
        onError: (e) =>
          toast.error(
            (e instanceof ApiError && (e.body as { detail?: string } | null)?.detail) ||
              "Couldn't start the run",
          ),
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Run</CardTitle>
        <CardDescription>
          Each case runs as its own Hatchet child run; results stream in live.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <TargetPicker
          id="target"
          label="Target"
          value={first}
          model={firstModel}
          onChange={setFirst}
          onModel={setFirstModel}
        />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={compare}
            onChange={(e) => setCompare(e.target.checked)}
          />
          Compare with a second target
        </label>
        {compare && (
          <TargetPicker
            id="compare-target"
            label="Second target"
            value={second}
            model={secondModel}
            onChange={setSecond}
            onModel={setSecondModel}
          />
        )}
        <Button
          className="w-fit"
          onClick={run}
          disabled={start.isPending || !first || (compare && !second)}
        >
          <Play className="size-4" /> {compare ? "Run both" : "Run"}
        </Button>
      </CardContent>
    </Card>
  );
}
