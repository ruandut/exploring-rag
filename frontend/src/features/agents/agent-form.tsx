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
import { Field } from "@/features/settings/provider-form";
import { ApiError } from "@/lib/api";

import { type Agent, type AgentInput, DEFAULT_RAG, type RagConfig } from "./api";
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
  const [rag, setRag] = useState<RagConfig>(agent?.rag_config ?? DEFAULT_RAG);
  const [effort, setEffort] = useState<Agent["effort"]>(agent?.effort ?? "");
  const errors = errorsOf(error);

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
          effort,
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

      <OptionSelect
        id="effort"
        label="Reasoning effort"
        options={EFFORTS}
        value={effort || "high"}
        onChange={(v) => setEffort(v === "high" ? "" : v)}
      />

      <p className="text-xs text-muted-foreground">
        What the agent searches (an embedding) and which model answers are picked in Chat, next to
        the agent — so one agent can be tried with different embeddings and models.
      </p>

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

type Effort = Exclude<Agent["effort"], "">;

// Used by models that support it (e.g. Claude); others ignore it.
const EFFORTS: { value: Effort; label: string; hint: string }[] = [
  { value: "low", label: "Low", hint: "Quick answers, little thinking." },
  { value: "medium", label: "Medium", hint: "Some thinking." },
  { value: "high", label: "High (default)", hint: "Thinks before answering — a good default." },
  { value: "xhigh", label: "Extra high", hint: "More thinking for harder questions." },
  { value: "max", label: "Max", hint: "As much thinking as needed. Slowest." },
];

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
