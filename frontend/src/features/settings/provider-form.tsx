import { CheckCircle2, Loader2, PlugZap, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

import {
  type Check,
  fieldErrors,
  needsReindexConfirmation,
  type ProviderConfig,
  type SaveProviderInput,
  useSaveProvider,
  useTestConnection,
} from "./api";
import { ReindexDialog } from "./reindex-dialog";

const PRESETS = [
  {
    name: "OpenAI",
    base_url: "https://api.openai.com/v1",
    chat: "gpt-5-mini",
    embed: "text-embedding-3-small",
  },
  {
    name: "OpenRouter",
    base_url: "https://openrouter.ai/api/v1",
    chat: "openai/gpt-5-mini",
    embed: "",
  },
  {
    name: "Ollama (local)",
    base_url: "http://localhost:11434/v1",
    chat: "",
    embed: "nomic-embed-text",
  },
];

type Form = {
  base_url: string;
  api_key: string;
  chat_model: string;
  embedding_model: string;
  embedding_dimensions: string;
};

function initialForm(saved: ProviderConfig | null): Form {
  return {
    base_url: saved?.base_url ?? "",
    api_key: "",
    chat_model: saved?.chat_model ?? "",
    embedding_model: saved?.embedding_model ?? "",
    embedding_dimensions: saved?.embedding_dimensions?.toString() ?? "",
  };
}

export function ProviderForm({ saved }: { saved: ProviderConfig | null }) {
  const [form, setForm] = useState<Form>(() => initialForm(saved));
  const [confirming, setConfirming] = useState<string | null>(null);
  const save = useSaveProvider();
  const test = useTestConnection();
  const errors = fieldErrors(save.error);

  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  function payload(confirm = false): SaveProviderInput {
    return {
      base_url: form.base_url.trim(),
      // Blank means "keep the saved key" — the server never sends it back to pre-fill.
      ...(form.api_key ? { api_key: form.api_key } : {}),
      chat_model: form.chat_model.trim(),
      embedding_model: form.embedding_model.trim(),
      embedding_dimensions: form.embedding_dimensions ? Number(form.embedding_dimensions) : null,
      confirm_reindex: confirm,
    };
  }

  function submit(confirm = false) {
    save.mutate(payload(confirm), {
      onSuccess: (data) => {
        setForm((f) => ({ ...f, api_key: "" }));
        toast.success("Provider saved");
        if (data.reindex_started) toast.info("Re-indexing your documents in the background…");
      },
      onError: (error) => {
        if (needsReindexConfirmation(error)) {
          setConfirming((error.body as { detail: string }).detail);
        } else if (Object.keys(fieldErrors(error)).length === 0) {
          toast.error("Couldn't save the provider");
        }
      },
    });
  }

  const report = test.data;

  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">Quick fill:</span>
        {PRESETS.map((p) => (
          <Button
            key={p.name}
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              setForm((f) => ({
                ...f,
                base_url: p.base_url,
                chat_model: p.chat || f.chat_model,
                embedding_model: p.embed || f.embedding_model,
              }))
            }
          >
            {p.name}
          </Button>
        ))}
      </div>

      <Field id="base_url" label="Base URL" error={errors.base_url}>
        <Input
          id="base_url"
          value={form.base_url}
          onChange={set("base_url")}
          placeholder="https://api.openai.com/v1"
          required
        />
      </Field>

      <Field
        id="api_key"
        label="API key"
        error={errors.api_key}
        hint={
          saved?.has_api_key
            ? `Saved key ends in …${saved.api_key_last4}. Leave blank to keep it.`
            : "Encrypted at rest and never sent back to the browser. Local servers may not need one."
        }
      >
        <Input
          id="api_key"
          type="password"
          autoComplete="off"
          value={form.api_key}
          onChange={set("api_key")}
          placeholder={saved?.has_api_key ? `•••• ${saved.api_key_last4}` : "sk-…"}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="chat_model" label="Chat model" error={errors.chat_model}>
          <Input id="chat_model" value={form.chat_model} onChange={set("chat_model")} required />
        </Field>
        <Field id="embedding_model" label="Embedding model" error={errors.embedding_model}>
          <Input
            id="embedding_model"
            value={form.embedding_model}
            onChange={set("embedding_model")}
            required
          />
        </Field>
      </div>

      <Field
        id="embedding_dimensions"
        label="Embedding dimensions"
        error={errors.embedding_dimensions}
        hint="Size of each vector. Test connection detects it for you."
      >
        <Input
          id="embedding_dimensions"
          type="number"
          min={1}
          className="max-w-40"
          value={form.embedding_dimensions}
          onChange={set("embedding_dimensions")}
        />
      </Field>

      {report && (
        <div
          role="status"
          aria-label="Connection test results"
          className="grid gap-2 rounded-lg border p-3 text-sm"
        >
          <CheckRow name="Chat" check={report.chat} />
          <CheckRow name="Embeddings" check={report.embeddings} />
          {report.embedding_dimensions &&
            report.embedding_dimensions.toString() !== form.embedding_dimensions && (
              <Button
                type="button"
                variant="link"
                className="h-auto justify-start p-0"
                onClick={() =>
                  setForm((f) => ({
                    ...f,
                    embedding_dimensions: String(report.embedding_dimensions),
                  }))
                }
              >
                Use detected {report.embedding_dimensions} dimensions
              </Button>
            )}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={test.isPending || !form.base_url}
          onClick={() => {
            const { base_url, api_key, chat_model, embedding_model } = payload();
            test.mutate({ base_url, api_key, chat_model, embedding_model });
          }}
        >
          {test.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <PlugZap className="size-4" />
          )}
          Test connection
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save provider"}
        </Button>
      </div>

      <ReindexDialog
        open={confirming !== null}
        detail={confirming ?? ""}
        onCancel={() => setConfirming(null)}
        onConfirm={() => {
          setConfirming(null);
          submit(true);
        }}
      />
    </form>
  );
}

function CheckRow({ name, check }: { name: string; check: Check }) {
  return (
    <div role="group" aria-label={name} className="flex items-start gap-2">
      {check.ok ? (
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-500" />
      ) : (
        <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
      )}
      <div className="min-w-0">
        <span className="font-medium">{name}: </span>
        <span className={cn(!check.ok && "text-destructive")}>{check.detail}</span>
        {check.latency_ms !== null && (
          <span className="ml-2 text-xs text-muted-foreground">{check.latency_ms} ms</span>
        )}
      </div>
    </div>
  );
}

export function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}
