import { Cpu, Loader2, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  type Connection,
  useConnections,
  useDeleteConnection,
  useModels,
  useSaveConnection,
} from "@/features/agents/api";
import { ApiError } from "@/lib/api";

import { KindSelect } from "./kind-select";
import { kindLabel, needsBaseUrl, PRESETS, type ProviderKind } from "./kinds";
import { Field } from "./provider-form";

/** Extra endpoints to chat or embed with — e.g. a local Ollama, Claude or Gemini. */
export function Connections() {
  const connections = useConnections();
  return (
    <div className="grid gap-6">
      <ul aria-label="Connections" className="grid gap-3">
        {connections.data?.map((c) => (
          <ConnectionRow key={c.id} connection={c} />
        ))}
        {connections.data?.length === 0 && (
          <li className="text-sm text-muted-foreground">
            No connections yet. Agents use your default provider until you add one.
          </li>
        )}
      </ul>
      <NewConnection />
    </div>
  );
}

function ConnectionRow({ connection }: { connection: Connection }) {
  const [showModels, setShowModels] = useState(false);
  const models = useModels(connection.id, showModels);
  const remove = useDeleteConnection();
  const error =
    models.error instanceof ApiError
      ? (models.error.body as { detail?: string } | null)?.detail
      : undefined;

  return (
    <li aria-label={connection.name} className="grid gap-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Cpu className="size-4 text-muted-foreground" />
        <span className="font-medium">{connection.name}</span>
        <span className="text-xs text-muted-foreground">{kindLabel(connection.kind)}</span>
        <code className="truncate text-xs text-muted-foreground">{connection.base_url}</code>
        <div className="ml-auto flex gap-1">
          <Button size="sm" variant="outline" onClick={() => setShowModels(true)}>
            {models.isFetching && <Loader2 className="size-3 animate-spin" />} List models
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="size-8"
            aria-label={`Delete ${connection.name}`}
            onClick={() =>
              remove.mutate(connection.id, { onSuccess: () => toast.success("Connection removed") })
            }
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      </div>
      {showModels && models.data && (
        <p className="text-sm">
          <span className="text-muted-foreground">{models.data.models.length} models: </span>
          {models.data.models.join(", ")}
        </p>
      )}
      {showModels && error && <p className="text-sm text-destructive">{error}</p>}
    </li>
  );
}

function NewConnection() {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<ProviderKind>("openai");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const save = useSaveConnection();
  const errors =
    save.error instanceof ApiError && save.error.status === 400
      ? (save.error.body as Record<string, string[]>)
      : {};

  return (
    <form
      className="grid gap-4 rounded-lg border border-dashed p-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(
          {
            name: name.trim(),
            kind,
            base_url: baseUrl.trim(),
            ...(apiKey ? { api_key: apiKey } : {}),
          },
          {
            onSuccess: (c) => {
              toast.success(`Added ${c.name}`);
              setName("");
              setKind("openai");
              setBaseUrl("");
              setApiKey("");
            },
          },
        );
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Add a connection</h3>
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.filter((p) => p.name !== "OpenAI").map((p) => (
            <Button
              key={p.name}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setName(p.name);
                setKind(p.kind);
                setBaseUrl(p.base_url);
              }}
            >
              {p.name}
            </Button>
          ))}
        </div>
      </div>
      <KindSelect id="connection-kind" value={kind} onChange={setKind} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="connection-name" label="Connection name" error={errors.name?.join(" ")}>
          <Input
            id="connection-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </Field>
        <Field id="connection-url" label="Connection base URL" error={errors.base_url?.join(" ")}>
          <Input
            id="connection-url"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={needsBaseUrl(kind) ? "http://localhost:11434/v1" : "Provider default"}
            required={needsBaseUrl(kind)}
          />
        </Field>
      </div>
      <Field
        id="connection-key"
        label="Connection API key"
        hint="Optional — local servers like Ollama don't need one. Encrypted at rest."
      >
        <Input
          id="connection-key"
          type="password"
          autoComplete="off"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
      </Field>
      <Button type="submit" className="w-fit" disabled={save.isPending}>
        Add connection
      </Button>
    </form>
  );
}
