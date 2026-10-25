import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  fieldErrors,
  type IndexingConfig,
  needsReindexConfirmation,
  STRATEGIES,
  type Strategy,
  useSaveIndexing,
} from "./api";
import { Field } from "./provider-form";
import { ReindexDialog } from "./reindex-dialog";

export function IndexingForm({ saved }: { saved: IndexingConfig }) {
  const [strategy, setStrategy] = useState<Strategy>(saved.strategy);
  const [size, setSize] = useState(String(saved.chunk_size));
  const [overlap, setOverlap] = useState(String(saved.chunk_overlap));
  const [confirming, setConfirming] = useState<string | null>(null);
  const save = useSaveIndexing();
  const errors = fieldErrors(save.error);

  // Same rule as the server, shown before you press Save.
  const overlapError =
    Number(overlap) >= Number(size) ? "Overlap must be smaller than the chunk size." : undefined;

  function submit(confirm = false) {
    save.mutate(
      {
        strategy,
        chunk_size: Number(size),
        chunk_overlap: Number(overlap),
        confirm_reindex: confirm,
      },
      {
        onSuccess: (data) => {
          toast.success("Indexing settings saved");
          if (data.reindex_started) toast.info("Re-indexing your documents in the background…");
        },
        onError: (error) => {
          if (needsReindexConfirmation(error)) {
            setConfirming((error.body as { detail: string }).detail);
          }
        },
      },
    );
  }

  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Field
        id="strategy"
        label="Chunking strategy"
        hint={STRATEGIES.find((s) => s.value === strategy)?.hint}
        error={errors.strategy}
      >
        <Select value={strategy} onValueChange={(v) => setStrategy(v as Strategy)}>
          <SelectTrigger id="strategy" className="w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STRATEGIES.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          id="chunk_size"
          label="Chunk size (tokens)"
          hint="Bigger chunks carry more context but match less precisely."
          error={errors.chunk_size}
        >
          <Input
            id="chunk_size"
            type="number"
            min={64}
            max={8192}
            value={size}
            onChange={(e) => setSize(e.target.value)}
            required
          />
        </Field>
        <Field
          id="chunk_overlap"
          label="Overlap (tokens)"
          hint="Repeated between neighbouring chunks so ideas aren't cut in half."
          error={overlapError ?? errors.chunk_overlap}
        >
          <Input
            id="chunk_overlap"
            type="number"
            min={0}
            value={overlap}
            onChange={(e) => setOverlap(e.target.value)}
            required
          />
        </Field>
      </div>

      <Button type="submit" className="w-fit" disabled={save.isPending || !!overlapError}>
        {save.isPending ? "Saving…" : "Save indexing settings"}
      </Button>

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
