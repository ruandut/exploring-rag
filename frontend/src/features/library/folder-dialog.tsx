import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** A one-field naming dialog (folders, suites). Mount it with a `key` so it resets each time. */
export function FolderDialog({
  title,
  description,
  submitLabel,
  initialName = "",
  fieldLabel = "Folder name",
  error,
  pending,
  onSubmit,
  onClose,
}: {
  title: string;
  description?: string;
  submitLabel: string;
  initialName?: string;
  fieldLabel?: string;
  error?: string;
  pending: boolean;
  onSubmit: (name: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(initialName);
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) onSubmit(name.trim());
          }}
        >
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="folder-name">{fieldLabel}</Label>
            <Input
              id="folder-name"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={200}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending || !name.trim()}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
