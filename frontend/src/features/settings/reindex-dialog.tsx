import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

/** Shown when the server answers 409 reindex_required. */
export function ReindexDialog({
  open,
  detail,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  detail: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Re-index all documents?</AlertDialogTitle>
          <AlertDialogDescription>
            {detail} Existing embeddings can&apos;t be compared with new ones, so every document is
            processed again in the background (a Hatchet run). Search may be incomplete until it
            finishes.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>Save and re-index</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
