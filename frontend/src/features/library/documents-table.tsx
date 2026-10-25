import { FileText, MoreHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { Folder, LibraryDocument } from "./api";
import { StatusBadge } from "./status-badge";

export type DocumentAction =
  | { kind: "chunks" | "reindex" | "delete"; document: LibraryDocument }
  | { kind: "move"; document: LibraryDocument; folder: number | null };

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function DocumentsTable({
  documents,
  folders,
  showFolder,
  onAction,
}: {
  documents: LibraryDocument[];
  folders: Folder[];
  showFolder: boolean;
  onAction: (action: DocumentAction) => void;
}) {
  const folderName = new Map(folders.map((f) => [f.id, f.name]));

  return (
    <Table aria-label="Documents">
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          {showFolder && <TableHead className="hidden md:table-cell">Folder</TableHead>}
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Chunks</TableHead>
          <TableHead className="hidden text-right sm:table-cell">Size</TableHead>
          <TableHead className="w-10" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {documents.map((doc) => (
          <TableRow key={doc.id} aria-label={doc.name} className="align-top">
            <TableCell className="max-w-72 whitespace-normal">
              <div className="flex items-center gap-2 font-medium">
                <FileText className="size-4 shrink-0 text-muted-foreground" />
                <span className="truncate">{doc.name}</span>
              </div>
              {doc.status === "failed" && doc.error && (
                <p className="mt-1 pl-6 text-xs text-destructive">{doc.error}</p>
              )}
            </TableCell>
            {showFolder && (
              <TableCell className="hidden text-muted-foreground md:table-cell">
                {doc.folder === null ? "—" : folderName.get(doc.folder)}
              </TableCell>
            )}
            <TableCell>
              <StatusBadge status={doc.status} />
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {doc.status === "ready" ? doc.chunk_count : "—"}
            </TableCell>
            <TableCell className="hidden text-right text-muted-foreground tabular-nums sm:table-cell">
              {formatSize(doc.size)}
            </TableCell>
            <TableCell>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7"
                    aria-label={`Actions for ${doc.name}`}
                  >
                    <MoreHorizontal className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    disabled={doc.status !== "ready"}
                    onClick={() => onAction({ kind: "chunks", document: doc })}
                  >
                    View chunks
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    disabled={doc.status === "queued" || doc.status === "indexing"}
                    onClick={() => onAction({ kind: "reindex", document: doc })}
                  >
                    Re-index
                  </DropdownMenuItem>
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger>Move to</DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>
                      <DropdownMenuItem
                        disabled={doc.folder === null}
                        onClick={() => onAction({ kind: "move", document: doc, folder: null })}
                      >
                        Top level
                      </DropdownMenuItem>
                      {folders.map((f) => (
                        <DropdownMenuItem
                          key={f.id}
                          disabled={doc.folder === f.id}
                          onClick={() => onAction({ kind: "move", document: doc, folder: f.id })}
                        >
                          {f.name}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={() => onAction({ kind: "delete", document: doc })}
                  >
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
