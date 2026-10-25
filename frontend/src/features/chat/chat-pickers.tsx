import { Link } from "@tanstack/react-router";
import { Cpu, Layers } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { type Connection, modelLabel } from "@/features/agents/api";
import type { Embedding } from "@/features/embeddings/api";
import { useModelCatalogue } from "@/features/models/api";
import { ModelBadges } from "@/features/models/model-picker";
import { cn } from "@/lib/utils";

/** What answers a chat: a connection (null = the default provider) and a model ("" = its chat
 *  model). Picked next to the agent and the embedding (spec 0010). */
export type ModelChoice = { connection: number | null; model: string };

const NONE = "none";

const TRIGGER =
  "max-w-48 border-0 bg-transparent text-muted-foreground shadow-none hover:bg-muted hover:text-foreground dark:bg-transparent dark:hover:bg-muted";

export function EmbeddingPicker({
  embeddings,
  value,
  onChange,
}: {
  embeddings: Embedding[];
  value: number | null;
  onChange: (id: number | null) => void;
}) {
  const current = embeddings.find((e) => e.id === value);
  return (
    <Select
      value={value === null ? NONE : String(value)}
      onValueChange={(v) => onChange(v === NONE ? null : Number(v))}
    >
      <SelectTrigger size="sm" aria-label="Embedding" className={TRIGGER}>
        <Layers className="size-3.5" />
        <SelectValue placeholder="Embedding">{current?.name ?? "No embedding"}</SelectValue>
      </SelectTrigger>
      <SelectContent align="end">
        {embeddings.map((e) => (
          <SelectItem key={e.id} value={String(e.id)}>
            <span className="flex flex-col">
              <span>{e.name}</span>
              <span className="text-xs text-muted-foreground">
                {e.model}
                {e.dimensions ? `, ${e.dimensions} dims` : ""} · {e.status}
              </span>
            </span>
          </SelectItem>
        ))}
        <SelectItem value={NONE}>
          <span className="flex flex-col">
            <span>None</span>
            <span className="text-xs text-muted-foreground">Answer from the model alone</span>
          </span>
        </SelectItem>
        <SelectSeparator />
        <Link
          to="/embeddings"
          className="block rounded-sm px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          Manage embeddings…
        </Link>
      </SelectContent>
    </Select>
  );
}

const key = (c: ModelChoice) => `${c.connection ?? "default"}|${c.model}`;

/** Which model answers: every endpoint's chat models (and unknowns — never hidden), grouped by
 *  endpoint, with "No tools" where the endpoint says so (spec 0010). Searchable; any id can be
 *  typed for the endpoint chosen with "Use". */
export function ModelPicker({
  connections,
  defaultChatModel,
  value,
  onChange,
}: {
  connections: Connection[];
  defaultChatModel: string;
  value: ModelChoice;
  onChange: (choice: ModelChoice) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const connName =
    value.connection === null
      ? null
      : (connections.find((c) => c.id === value.connection)?.name ?? "Connection");
  const choose = (choice: ModelChoice) => {
    onChange(choice);
    setOpen(false);
    setSearch("");
  };
  const custom = search.trim();
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          role="combobox"
          aria-label="Model"
          aria-expanded={open}
          className={cn(TRIGGER, "h-8 font-normal")}
        >
          <Cpu className="size-3.5" />
          <span className="truncate">{modelLabel(connName, value.model, defaultChatModel)}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(26rem,90vw)] p-0" align="end">
        <Command aria-label="Model options">
          <CommandInput
            aria-label="Search Model"
            placeholder="Search models…"
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            <CommandEmpty>No model matches.</CommandEmpty>
            <ModelGroup
              label="Default provider"
              connection={null}
              open={open}
              defaultModel={defaultChatModel}
              selected={value}
              onChoose={choose}
            />
            {connections.map((c) => (
              <ModelGroup
                key={c.id}
                label={c.name}
                connection={c.id}
                open={open}
                selected={value}
                onChoose={choose}
              />
            ))}
          </CommandList>
          {custom && (
            <div className="flex flex-wrap gap-2 border-t p-2">
              {[{ id: null, name: "Default provider" }, ...connections].map((c) => (
                <Button
                  key={c.id ?? "default"}
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => choose({ connection: c.id, model: custom })}
                >
                  Use “{custom}” on {c.name}
                </Button>
              ))}
            </div>
          )}
        </Command>
      </PopoverContent>
    </Popover>
  );
}

/** One endpoint's chat models. Its own component so each endpoint runs its own query. */
function ModelGroup({
  label,
  connection,
  open,
  defaultModel,
  selected,
  onChoose,
}: {
  label: string;
  connection: number | null;
  open: boolean;
  defaultModel?: string;
  selected: ModelChoice;
  onChoose: (choice: ModelChoice) => void;
}) {
  const catalogue = useModelCatalogue({ connection }, "chat", open);
  const models = catalogue.data?.models ?? [];
  const current = selected.connection === connection ? selected.model : "";
  // Keep the current choice listed even if the endpoint doesn't list it (a custom id).
  const extra = current && !models.some((m) => m.id === current) ? [current] : [];
  return (
    <CommandGroup heading={label}>
      {connection === null && (
        <CommandItem
          value={`${label} default ${defaultModel ?? ""}`}
          onSelect={() => onChoose({ connection: null, model: "" })}
        >
          {defaultModel ? `${defaultModel} (default)` : "Provider default"}
        </CommandItem>
      )}
      {models.map((m) => (
        <CommandItem
          key={m.id}
          value={`${key({ connection, model: m.id })} ${m.id}`}
          onSelect={() => onChoose({ connection, model: m.id })}
        >
          <span className="truncate">{m.id}</span>
          <ModelBadges model={m} />
        </CommandItem>
      ))}
      {extra.map((m) => (
        <CommandItem
          key={m}
          value={`${key({ connection, model: m })} ${m}`}
          onSelect={() => onChoose({ connection, model: m })}
        >
          {m}
        </CommandItem>
      ))}
      {catalogue.isError && (
        <p className="px-2 py-1 text-xs text-muted-foreground">Couldn&apos;t list models.</p>
      )}
    </CommandGroup>
  );
}
