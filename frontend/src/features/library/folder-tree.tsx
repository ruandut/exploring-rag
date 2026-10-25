import {
  ChevronRight,
  Folder as FolderIcon,
  FolderOpen,
  Library,
  MoreHorizontal,
} from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

import type { Folder, FolderKey } from "./api";

export type FolderAction = "new-subfolder" | "rename" | "delete";

type Node = Folder & { children: Node[] };

export function buildTree(folders: Folder[]): Node[] {
  const nodes = new Map(folders.map((f) => [f.id, { ...f, children: [] as Node[] }]));
  const roots: Node[] = [];
  for (const node of nodes.values()) {
    const parent = node.parent === null ? undefined : nodes.get(node.parent);
    (parent ? parent.children : roots).push(node);
  }
  return roots;
}

/** Accessible tree (role=tree / treeitem / group) so it works with a keyboard and screen readers. */
export function FolderTree({
  folders,
  selected,
  onSelect,
  onAction,
}: {
  folders: Folder[];
  selected: FolderKey;
  onSelect: (key: FolderKey) => void;
  onAction: (action: FolderAction, folder: Folder) => void;
}) {
  return (
    <ul role="tree" aria-label="Folders" className="grid gap-0.5 text-sm">
      <li role="treeitem" aria-label="All documents" aria-selected={selected === "all"}>
        <Row
          depth={0}
          active={selected === "all"}
          onClick={() => onSelect("all")}
          icon={<Library className="size-4" />}
          label="All documents"
        />
      </li>
      {buildTree(folders).map((node) => (
        <TreeNode
          key={node.id}
          node={node}
          depth={0}
          selected={selected}
          onSelect={onSelect}
          onAction={onAction}
        />
      ))}
    </ul>
  );
}

function TreeNode({
  node,
  depth,
  selected,
  onSelect,
  onAction,
}: {
  node: Node;
  depth: number;
  selected: FolderKey;
  onSelect: (key: FolderKey) => void;
  onAction: (action: FolderAction, folder: Folder) => void;
}) {
  const [open, setOpen] = useState(true);
  const active = selected === node.id;
  const hasChildren = node.children.length > 0;

  return (
    <li
      role="treeitem"
      aria-label={node.name}
      aria-selected={active}
      aria-expanded={hasChildren ? open : undefined}
    >
      <Row
        depth={depth}
        active={active}
        onClick={() => onSelect(node.id)}
        icon={active ? <FolderOpen className="size-4" /> : <FolderIcon className="size-4" />}
        label={node.name}
        count={node.document_count}
        toggle={
          hasChildren ? (
            <button
              type="button"
              aria-label={open ? `Collapse ${node.name}` : `Expand ${node.name}`}
              onClick={(e) => {
                e.stopPropagation();
                setOpen((o) => !o);
              }}
              className="flex size-4 items-center justify-center"
            >
              <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
            </button>
          ) : (
            <span className="size-4" />
          )
        }
        menu={
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="size-6 opacity-60 hover:opacity-100"
                aria-label={`Folder actions for ${node.name}`}
                onClick={(e) => e.stopPropagation()}
              >
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => onAction("new-subfolder", node)}>
                New folder inside
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAction("rename", node)}>Rename</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={() => onAction("delete", node)}>
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        }
      />
      {hasChildren && open && (
        <ul role="group" className="grid gap-0.5">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              selected={selected}
              onSelect={onSelect}
              onAction={onAction}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function Row({
  depth,
  active,
  onClick,
  icon,
  label,
  count,
  toggle,
  menu,
}: {
  depth: number;
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  count?: number;
  toggle?: React.ReactNode;
  menu?: React.ReactNode;
}) {
  return (
    <div
      onClick={onClick}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onClick()}
      tabIndex={0}
      className={cn(
        "group flex cursor-pointer items-center gap-1.5 rounded-md py-1 pr-1 outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
        active && "bg-muted font-medium",
      )}
      style={{ paddingLeft: `${0.375 + depth * 1}rem` }}
    >
      {toggle}
      {icon}
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {count !== undefined && count > 0 && (
        <span className="text-xs text-muted-foreground">{count}</span>
      )}
      {menu}
    </div>
  );
}
