import { useNavigate } from "@tanstack/react-router";
import { Play } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useAgents, useConnections } from "@/features/agents/api";
import { useEmbeddings } from "@/features/embeddings/api";
import { ModelCombobox } from "@/features/models/model-picker";
import { ApiError } from "@/lib/api";

import { type Target, useStartRun } from "./api";
import { nativeSelect } from "./suite-editor";

/** What one target needs besides its kind: a model name, and for agents (spec 0010) the
 *  embedding to search ("" = the oldest one, "none" = nothing) and the connection. */
type TargetExtras = { model: string; embedding: string; connection: string };

const NO_EXTRAS: TargetExtras = { model: "", embedding: "", connection: "default" };

/** "agent:12", "model:default" or "model:3" (a connection) + extras. */
function TargetPicker({
  id,
  label,
  value,
  extras,
  onChange,
  onExtras,
}: {
  id: string;
  label: string;
  value: string;
  extras: TargetExtras;
  onChange: (v: string) => void;
  onExtras: (e: TargetExtras) => void;
}) {
  const agents = useAgents();
  const connections = useConnections();
  const embeddings = useEmbeddings();
  const bare = value.startsWith("model:");
  const isAgent = value.startsWith("agent:");
  const connection = bare
    ? value === "model:default"
      ? null
      : Number(value.split(":")[1])
    : extras.connection === "default"
      ? null
      : Number(extras.connection);
  const set = (change: Partial<TargetExtras>) => onExtras({ ...extras, ...change });

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
      {isAgent && (
        <div className="grid gap-2 sm:grid-cols-2">
          <select
            aria-label={`${label} embedding`}
            className={nativeSelect}
            value={extras.embedding}
            onChange={(e) => set({ embedding: e.target.value })}
          >
            <option value="">
              Embedding: {embeddings.data?.[0]?.name ?? "none yet"} (default)
            </option>
            {embeddings.data?.map((emb) => (
              <option key={emb.id} value={String(emb.id)}>
                Embedding: {emb.name}
              </option>
            ))}
            <option value="none">No embedding (model alone)</option>
          </select>
          <select
            aria-label={`${label} connection`}
            className={nativeSelect}
            value={extras.connection}
            onChange={(e) => set({ connection: e.target.value, model: "" })}
          >
            <option value="default">Default provider</option>
            {connections.data?.map((c) => (
              <option key={c.id} value={String(c.id)}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      )}
      {(bare || isAgent) && (
        <ModelCombobox
          id={`${id}-model`}
          label={`${label} model`}
          value={extras.model}
          placeholder={connection === null ? "Provider's chat model" : "Model name"}
          source={{ connection }}
          want="chat"
          onChange={(m) => set({ model: m })}
        />
      )}
    </div>
  );
}

function toTarget(value: string, extras: TargetExtras): Target | null {
  const { model } = extras;
  if (value.startsWith("agent:")) {
    return {
      kind: "agent",
      agent: Number(value.slice(6)),
      // Left out = the server's default (the oldest embedding).
      ...(extras.embedding
        ? { embedding: extras.embedding === "none" ? null : Number(extras.embedding) }
        : {}),
      connection: extras.connection === "default" ? null : Number(extras.connection),
      model,
    };
  }
  if (value === "model:default") return { kind: "model", connection: null, model };
  if (value.startsWith("model:"))
    return { kind: "model", connection: Number(value.slice(6)), model };
  return null;
}

export function RunPanel({ suiteId }: { suiteId: number }) {
  const navigate = useNavigate();
  const start = useStartRun();
  const [first, setFirst] = useState("");
  const [firstExtras, setFirstExtras] = useState(NO_EXTRAS);
  const [compare, setCompare] = useState(false);
  const [second, setSecond] = useState("");
  const [secondExtras, setSecondExtras] = useState(NO_EXTRAS);

  function run() {
    const targets = [
      toTarget(first, firstExtras),
      compare ? toTarget(second, secondExtras) : null,
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
          extras={firstExtras}
          onChange={setFirst}
          onExtras={setFirstExtras}
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
            extras={secondExtras}
            onChange={setSecond}
            onExtras={setSecondExtras}
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
