import { CheckCircle2, Loader2, PlugZap, XCircle } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useConnections } from "@/features/agents/api";
import { ModelCombobox } from "@/features/models/model-picker";
import { useDocuments, useFolders } from "@/features/library/api";
import { fieldErrors, STRATEGIES, type Strategy } from "@/features/settings/api";
import { Field } from "@/features/settings/provider-form";
import { cn } from "@/lib/utils";

import { type Embedding, type EmbeddingInput, useTestEmbedding } from "./api";

export function EmbeddingForm({
  embedding,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  embedding: Embedding | null;
  pending: boolean;
  error: unknown;
  onSubmit: (input: EmbeddingInput) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(embedding?.name ?? "");
  const [allDocuments, setAllDocuments] = useState(embedding?.all_documents ?? false);
  const [folders, setFolders] = useState<number[]>(embedding?.folders ?? []);
  const [documents, setDocuments] = useState<number[]>(embedding?.documents ?? []);
  const [connection, setConnection] = useState<number | null>(embedding?.connection ?? null);
  const [model, setModel] = useState(embedding?.model ?? "");
  const [dimensions, setDimensions] = useState(embedding?.dimensions?.toString() ?? "");
  const [strategy, setStrategy] = useState<Strategy>(embedding?.strategy ?? "recursive");
  const [size, setSize] = useState(String(embedding?.chunk_size ?? 512));
  const [overlap, setOverlap] = useState(String(embedding?.chunk_overlap ?? 64));
  const errors = fieldErrors(error);

  const connections = useConnections();
  const allFolders = useFolders();
  const allDocs = useDocuments("all");
  const test = useTestEmbedding();

  // Same rules as the server, shown before you press Save.
  const overlapError =
    Number(overlap) >= Number(size) ? "Overlap must be smaller than the chunk size." : undefined;
  const nothingCovered = !allDocuments && folders.length === 0 && documents.length === 0;

  const toggle = (list: number[], id: number, on: boolean) =>
    on ? [...list, id] : list.filter((x) => x !== id);

  return (
    <form
      className="grid gap-5"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          name: name.trim(),
          connection,
          model: model.trim(),
          dimensions: dimensions ? Number(dimensions) : null,
          strategy,
          chunk_size: Number(size),
          chunk_overlap: Number(overlap),
          all_documents: allDocuments,
          folders,
          documents,
        });
      }}
    >
      <Field id="embedding-name" label="Name" error={errors.name}>
        <Input
          id="embedding-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Handbook small"
          required
        />
      </Field>

      <fieldset className="grid gap-3 rounded-lg border p-4">
        <legend className="px-1 text-sm font-medium">What it covers</legend>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={allDocuments}
            onChange={(e) => setAllDocuments(e.target.checked)}
          />
          All documents
          <span className="text-xs text-muted-foreground">— including ones added later</span>
        </label>
        {!allDocuments && (
          <>
            <div role="group" aria-label="Folders" className="grid gap-1.5">
              <p className="text-xs font-medium text-muted-foreground">
                Folders (subfolders included)
              </p>
              <div className="grid max-h-36 gap-1.5 overflow-y-auto">
                {allFolders.data?.length === 0 && (
                  <p className="text-sm text-muted-foreground">No folders yet.</p>
                )}
                {allFolders.data?.map((f) => (
                  <label key={f.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="size-4 accent-primary"
                      checked={folders.includes(f.id)}
                      onChange={(e) => setFolders((fs) => toggle(fs, f.id, e.target.checked))}
                    />
                    {f.name}
                  </label>
                ))}
              </div>
            </div>
            <div role="group" aria-label="Files" className="grid gap-1.5">
              <p className="text-xs font-medium text-muted-foreground">Single files</p>
              <div className="grid max-h-36 gap-1.5 overflow-y-auto">
                {allDocs.data?.length === 0 && (
                  <p className="text-sm text-muted-foreground">No documents yet.</p>
                )}
                {allDocs.data?.map((d) => (
                  <label key={d.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="size-4 accent-primary"
                      checked={documents.includes(d.id)}
                      onChange={(e) => setDocuments((ds) => toggle(ds, d.id, e.target.checked))}
                    />
                    {d.name}
                  </label>
                ))}
              </div>
            </div>
          </>
        )}
        {errors.folders && <p className="text-sm text-destructive">{errors.folders}</p>}
      </fieldset>

      <fieldset className="grid gap-4 rounded-lg border p-4">
        <legend className="px-1 text-sm font-medium">Embedding model</legend>
        <p className="text-xs text-muted-foreground">
          Every vector in this embedding comes from this one model — vectors from different models
          can&apos;t be compared. Questions are embedded with it too.
        </p>
        <Field id="embedding-connection" label="Connection">
          <Select
            value={connection === null ? "default" : String(connection)}
            onValueChange={(v) => setConnection(v === "default" ? null : Number(v))}
          >
            <SelectTrigger id="embedding-connection" className="w-full">
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
        <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
          <Field id="embedding-model" label="Embedding model" error={errors.model}>
            <ModelCombobox
              id="embedding-model"
              label="Embedding model"
              placeholder="e.g. nomic-embed-text"
              value={model}
              source={{ connection }}
              want="embedding"
              onChange={(id, info) => {
                setModel(id);
                // Another model may make vectors of another size: use what the endpoint says,
                // or leave it for the first indexing run (or Test) to detect.
                setDimensions(info?.dimensions ? String(info.dimensions) : "");
              }}
            />
          </Field>
          <Field id="embedding-dimensions" label="Dimensions" error={errors.dimensions}>
            <Input
              id="embedding-dimensions"
              type="number"
              min={1}
              value={dimensions}
              onChange={(e) => setDimensions(e.target.value)}
              placeholder="auto"
            />
          </Field>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={test.isPending || !model.trim()}
            onClick={() =>
              test.mutate(
                { connection, model: model.trim() },
                {
                  onSuccess: (r) => {
                    if (r.ok && r.dimensions && !dimensions) setDimensions(String(r.dimensions));
                  },
                },
              )
            }
          >
            {test.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <PlugZap className="size-4" />
            )}
            Test
          </Button>
          {test.data && (
            <span
              role="status"
              aria-label="Embedding test result"
              className={cn(
                "flex items-center gap-1.5 text-sm",
                !test.data.ok && "text-destructive",
              )}
            >
              {test.data.ok ? (
                <CheckCircle2 className="size-4 text-emerald-500" />
              ) : (
                <XCircle className="size-4" />
              )}
              {test.data.detail}
            </span>
          )}
        </div>
      </fieldset>

      <fieldset className="grid gap-4 rounded-lg border p-4">
        <legend className="px-1 text-sm font-medium">Chunking</legend>
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
      </fieldset>

      <div className="flex gap-2">
        <Button
          type="submit"
          disabled={pending || !name.trim() || !model.trim() || !!overlapError || nothingCovered}
        >
          {pending ? "Saving…" : embedding ? "Save embedding" : "Create embedding"}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
