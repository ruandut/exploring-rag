import { Check, ChevronsUpDown, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
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
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

import { type ModelInfo, type ModelSource, useModelCatalogue, type Want } from "./api";

const GROUP_LABEL = { embedding: "Embedding", chat: "Chat", unknown: "Unknown" } as const;

/** What a model row says about itself: its size, how we know its kind, tool support. */
export function ModelBadges({ model }: { model: ModelInfo }) {
  return (
    <span className="ml-auto flex shrink-0 items-center gap-1">
      {model.dimensions && <Badge variant="secondary">{model.dimensions} dims</Badge>}
      {model.source === "guessed" && <Badge variant="outline">guessed from the name</Badge>}
      {model.tools === false && <Badge variant="outline">No tools</Badge>}
    </span>
  );
}

/**
 * A searchable model picker (spec 0010): the endpoint's models grouped by kind, with
 * dimensions and badges, "Show all models", Refresh, a hint when the wanted kind is missing,
 * and "Use “…”" for any id the endpoint doesn't list. A custom id is always allowed — the
 * picker helps, it never blocks.
 */
export function ModelCombobox({
  id,
  label,
  value,
  placeholder = "Choose a model",
  source,
  want,
  onChange,
  className,
}: {
  id?: string;
  label: string;
  value: string;
  placeholder?: string;
  source: ModelSource;
  want: Want;
  onChange: (id: string, info: ModelInfo | null) => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [showAll, setShowAll] = useState(false);
  const catalogue = useModelCatalogue(source, showAll ? null : want, open);
  const models = catalogue.data?.models ?? [];
  const groups = (["embedding", "chat", "unknown"] as const)
    .filter((kind) => showAll || kind === want || kind === "unknown")
    .map((kind) => ({ kind, items: models.filter((m) => m.kind === kind) }))
    .filter((g) => g.items.length > 0);
  const custom = search.trim();
  const listed = models.some((m) => m.id === custom);

  function choose(id: string, info: ModelInfo | null) {
    onChange(id, info);
    setOpen(false);
    setSearch("");
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-label={label}
          aria-expanded={open}
          className={cn("w-full min-w-0 justify-between font-normal", className)}
        >
          <span className={cn("truncate", !value && "text-muted-foreground")}>
            {value || placeholder}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(28rem,90vw)] p-0" align="start">
        <Command aria-label={`${label} options`}>
          <CommandInput
            aria-label={`Search ${label}`}
            placeholder="Search models…"
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            {catalogue.isPending && <p className="p-3 text-sm text-muted-foreground">Loading…</p>}
            {catalogue.isError && (
              <p className="p-3 text-sm text-destructive">
                {catalogue.error instanceof ApiError
                  ? ((catalogue.error.body as { detail?: string } | null)?.detail ??
                    "Couldn't reach the endpoint")
                  : "Couldn't reach the endpoint"}{" "}
                — you can still type a model id.
              </p>
            )}
            {catalogue.data && !models.some((m) => m.kind === want) && catalogue.data.hint && (
              <p className="p-3 text-sm text-muted-foreground">{catalogue.data.hint}</p>
            )}
            <CommandEmpty>No model matches.</CommandEmpty>
            {groups.map((g) => (
              <CommandGroup key={g.kind} heading={GROUP_LABEL[g.kind]}>
                {g.items.map((m) => (
                  <CommandItem key={m.id} value={m.id} onSelect={() => choose(m.id, m)}>
                    <Check className={cn("size-4", value === m.id ? "opacity-100" : "opacity-0")} />
                    <span className="truncate">{m.id}</span>
                    <ModelBadges model={m} />
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
          <div className="flex flex-wrap items-center gap-2 border-t p-2">
            {custom && !listed && (
              <Button type="button" size="sm" onClick={() => choose(custom, null)}>
                Use “{custom}”
              </Button>
            )}
            <Button type="button" size="sm" variant="ghost" onClick={() => setShowAll((v) => !v)}>
              {showAll ? `Only ${GROUP_LABEL[want].toLowerCase()} models` : "Show all models"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="ml-auto"
              onClick={() => void catalogue.refetch()}
              disabled={catalogue.isFetching}
            >
              <RefreshCw className={cn("size-3.5", catalogue.isFetching && "animate-spin")} />
              Refresh
            </Button>
          </div>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
