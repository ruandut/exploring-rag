import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useFolders } from "@/features/library/api";
import { Field } from "@/features/settings/provider-form";
import { ApiError } from "@/lib/api";

import {
  type Agent,
  type AgentInput,
  DEFAULT_RAG,
  type RagConfig,
  useConnections,
  useModels,
} from "./api";
import { GENERATION, QUERY_TRANSFORMS, RERANKERS, RETRIEVAL } from "./options";

function errorsOf(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.status !== 400 || !error.body) return {};
  return Object.fromEntries(
    Object.entries(error.body as Record<string, unknown>).map(([k, v]) => [
      k,
      Array.isArray(v) ? v.join(" ") : typeof v === "string" ? v : JSON.stringify(v),
    ]),
  );
}

export function AgentForm({
  agent,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  agent: Agent | null;
  pending: boolean;
  error: unknown;
  onSubmit: (input: AgentInput) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(agent?.name ?? "");
  const [systemMessage, setSystemMessage] = useState(agent?.system_message ?? "");
  const [connection, setConnection] = useState<number | null>(agent?.connection ?? null);
  const [model, setModel] = useState(agent?.model ?? "");
  const [folders, setFolders] = useState<number[]>(agent?.folders ?? []);
  const [rag, setRag] = useState<RagConfig>(agent?.rag_config ?? DEFAULT_RAG);
  const errors = errorsOf(error);

  const connections = useConnections();
  const models = useModels(connection);
  const allFolders = useFolders();

  const setRagField = <K extends keyof RagConfig>(key: K, value: RagConfig[K]) =>
    setRag((r) => ({ ...r, [key]: value }));

  return (
    <form
      className="grid gap-5"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          name,
          system_message: systemMessage,
          connection,
          model,
          folders,
          rag_config: rag,
        });
      }}
    >
      <Field id="agent-name" label="Name" error={errors.name}>
        <Input id="agent-name" value={name} onChange={(e) => setName(e.target.value)} required />
      </Field>

      <Field
        id="system-message"
        label="System message"
        hint="Who the agent is and how it should answer. RAG instructions are added for you."
        error={errors.system_message}
      >
        <Textarea
          id="system-message"
          rows={4}
          value={systemMessage}
          onChange={(e) => setSystemMessage(e.target.value)}
          placeholder="You are a helpful assistant for our team handbook…"
        />
      </Field>

      <fieldset className="grid gap-4 rounded-lg border p-4">
        <legend className="px-1 text-sm font-medium">Model</legend>
        <Field
          id="connection"
          label="Connection"
          hint="Add local models (e.g. Ollama) under Settings → Connections."
        >
          <Select
            value={connection === null ? "default" : String(connection)}
            onValueChange={(v) => {
              setConnection(v === "default" ? null : Number(v));
              setModel("");
            }}
          >
            <SelectTrigger id="connection" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="default">Default provider (Settings)</SelectItem>
              {connections.data?.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field
          id="model"
          label="Model"
          error={errors.model}
          hint={
            models.isError
              ? "Couldn't list this endpoint's models — type the model name."
              : connection === null
                ? "Leave blank to use the default provider's chat model."
                : `${models.data?.models.length ?? "…"} models available — start typing to pick one.`
          }
        >
          <Input
            id="model"
            list="model-options"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={connection === null ? "Provider default" : "e.g. gemma4:e4b"}
            autoComplete="off"
          />
          <datalist id="model-options">
            {models.data?.models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </Field>
      </fieldset>

      <fieldset className="grid gap-2 rounded-lg border p-4">
        <legend className="px-1 text-sm font-medium">Folders it may search</legend>
        <p className="text-xs text-muted-foreground">
          None ticked = all your documents. Subfolders are included.
        </p>
        <div className="grid max-h-40 gap-1.5 overflow-y-auto">
          {allFolders.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">No folders yet.</p>
          )}
          {allFolders.data?.map((f) => (
            <label key={f.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={folders.includes(f.id)}
                onChange={(e) =>
                  setFolders((fs) =>
                    e.target.checked ? [...fs, f.id] : fs.filter((x) => x !== f.id),
                  )
                }
              />
              {f.name}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="grid gap-4 rounded-lg border p-4 sm:grid-cols-2">
        <legend className="px-1 text-sm font-medium">RAG pipeline</legend>
        <OptionSelect
          id="retrieval"
          label="Retrieval"
          options={RETRIEVAL}
          value={rag.retrieval}
          onChange={(v) => setRagField("retrieval", v)}
        />
        <Field
          id="top-k"
          label="Chunks to retrieve (top-k)"
          hint="How many passages the agent sees per search."
        >
          <Input
            id="top-k"
            type="number"
            min={1}
            max={20}
            value={rag.top_k}
            onChange={(e) => setRagField("top_k", Number(e.target.value))}
          />
        </Field>
        <OptionSelect
          id="query-transform"
          label="Query transform"
          options={QUERY_TRANSFORMS}
          value={rag.query_transform}
          onChange={(v) => setRagField("query_transform", v)}
        />
        <OptionSelect
          id="rerank"
          label="Rerank"
          options={RERANKERS}
          value={rag.rerank}
          onChange={(v) => setRagField("rerank", v)}
        />
        <div className="sm:col-span-2">
          <OptionSelect
            id="generation"
            label="Generation"
            options={GENERATION}
            value={rag.generation}
            onChange={(v) => setRagField("generation", v)}
          />
        </div>
        {errors.rag_config && (
          <p className="text-sm text-destructive sm:col-span-2">{errors.rag_config}</p>
        )}
      </fieldset>

      <div className="flex gap-2">
        <Button type="submit" disabled={pending || !name.trim()}>
          {pending ? "Saving…" : "Save agent"}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function OptionSelect<T extends string>({
  id,
  label,
  options,
  value,
  onChange,
}: {
  id: string;
  label: string;
  options: { value: T; label: string; hint: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={(v) => onChange(v as T)}>
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">
        {options.find((o) => o.value === value)?.hint}
      </p>
    </div>
  );
}
