import { CheckCircle2, Loader2, PlugZap, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ModelCombobox } from "@/features/models/model-picker";
import { cn } from "@/lib/utils";

import {
  type Check,
  fieldErrors,
  type ProviderConfig,
  type SaveProviderInput,
  useSaveProvider,
  useTestConnection,
} from "./api";

const PRESETS = [
  { name: "OpenAI", base_url: "https://api.openai.com/v1", chat: "gpt-5-mini" },
  { name: "OpenRouter", base_url: "https://openrouter.ai/api/v1", chat: "openai/gpt-5-mini" },
  { name: "Ollama (local)", base_url: "http://localhost:11434/v1", chat: "" },
];

type Form = { base_url: string; api_key: string; chat_model: string };

function initialForm(saved: ProviderConfig | null): Form {
  return {
    base_url: saved?.base_url ?? "",
    api_key: "",
    chat_model: saved?.chat_model ?? "",
  };
}

export function ProviderForm({ saved }: { saved: ProviderConfig | null }) {
  const [form, setForm] = useState<Form>(() => initialForm(saved));
  const save = useSaveProvider();
  const test = useTestConnection();
  const errors = fieldErrors(save.error);

  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  function payload(): SaveProviderInput {
    return {
      base_url: form.base_url.trim(),
      // Blank means "keep the saved key" — the server never sends it back to pre-fill.
      ...(form.api_key ? { api_key: form.api_key } : {}),
      chat_model: form.chat_model.trim(),
    };
  }

  function submit() {
    save.mutate(payload(), {
      onSuccess: () => {
        setForm((f) => ({ ...f, api_key: "" }));
        toast.success("Provider saved");
      },
      onError: (error) => {
        if (Object.keys(fieldErrors(error)).length === 0) toast.error("Couldn't save the provider");
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

      <Field
        id="chat_model"
        label="Chat model"
        error={errors.chat_model}
        hint="Embedding models are chosen per embedding, on the Embeddings page."
      >
        <ModelCombobox
          id="chat_model"
          label="Chat model"
          value={form.chat_model}
          source={{ probe: { base_url: form.base_url.trim(), api_key: form.api_key } }}
          want="chat"
          onChange={(id) => setForm((f) => ({ ...f, chat_model: id }))}
        />
      </Field>

      {report && (
        <div
          role="status"
          aria-label="Connection test results"
          className="grid gap-2 rounded-lg border p-3 text-sm"
        >
          <CheckRow name="Chat" check={report.chat} />
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={test.isPending || !form.base_url}
          onClick={() => {
            test.mutate(payload());
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
