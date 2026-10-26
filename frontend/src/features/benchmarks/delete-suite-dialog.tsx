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

/** Confirms deleting a suite (spec 0014). Its runs are kept — each holds a snapshot of the
 *  suite it tested — and move to "Runs of deleted suites" on the Benchmarks page. */
export function DeleteSuiteDialog({
  name,
  runs,
  pending,
  onConfirm,
  onCancel,
}: {
  name: string;
  runs: number;
  pending: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const kept =
    runs === 0
      ? "It has no runs."
      : `Its ${runs} ${runs === 1 ? "run is" : "runs are"} kept under Runs of deleted suites.`;
  return (
    <AlertDialog open onOpenChange={(open) => !open && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete “{name}”?</AlertDialogTitle>
          <AlertDialogDescription>
            Its cases and boundaries will be deleted. {kept} This can&apos;t be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={pending}
            onClick={(e) => {
              e.preventDefault(); // stay open until the delete finishes (we navigate away then)
              onConfirm();
            }}
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
