import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useMatchRoute, useNavigate } from "@tanstack/react-router";
import {
  BookOpenText,
  Bot,
  ChevronsUpDown,
  FlaskConical,
  FolderOpen,
  LogOut,
  MessageSquare,
  Monitor,
  Moon,
  Network,
  Settings,
  Sun,
} from "lucide-react";
import { useTheme } from "next-themes";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { useSocketStatus } from "@/hooks/use-socket";
import { api, type Me } from "@/lib/api";
import { clearTokens } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/library", label: "Library", icon: FolderOpen },
  { to: "/benchmarks", label: "Benchmarks", icon: FlaskConical },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

const LEARN = [{ to: "/system-design", label: "System design", icon: Network }] as const;

export function AppSidebar() {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to="/chat">
                <div className="flex aspect-square size-8 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
                  <BookOpenText className="size-4" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">RAG Lab</span>
                  <span className="truncate text-xs text-muted-foreground">Learn by building</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavGroup label="Workspace" items={NAV} />
        <NavGroup label="Learn" items={LEARN} />
      </SidebarContent>
      <SidebarFooter>
        <UserMenu />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

function NavGroup({
  label,
  items,
}: {
  label: string;
  items: ReadonlyArray<{ to: string; label: string; icon: typeof MessageSquare }>;
}) {
  const matchRoute = useMatchRoute();
  return (
    <SidebarGroup>
      <SidebarGroupLabel>{label}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => (
            <SidebarMenuItem key={item.to}>
              <SidebarMenuButton
                asChild
                isActive={!!matchRoute({ to: item.to, fuzzy: true })}
                tooltip={item.label}
              >
                <Link to={item.to}>
                  <item.icon />
                  <span>{item.label}</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}

const STATUS_STYLE = {
  open: { dot: "bg-emerald-500", label: "Live" },
  connecting: { dot: "bg-amber-500 animate-pulse", label: "Connecting" },
  closed: { dot: "bg-red-500", label: "Disconnected" },
  idle: { dot: "bg-muted-foreground", label: "Idle" },
} as const;

function UserMenu() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/api/auth/me/") });
  const status = STATUS_STYLE[useSocketStatus()];
  const { setTheme } = useTheme();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" tooltip={`Websocket: ${status.label}`}>
              <div className="relative flex size-8 items-center justify-center rounded-md bg-muted font-medium uppercase">
                {me.data?.username.slice(0, 2) ?? "··"}
                <span
                  className={cn(
                    "absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full ring-2 ring-sidebar",
                    status.dot,
                  )}
                />
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{me.data?.username ?? "…"}</span>
                <span className="truncate text-xs text-muted-foreground">
                  Websocket: {status.label}
                </span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-56">
            <DropdownMenuLabel className="text-xs text-muted-foreground">Theme</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => setTheme("light")}>
              <Sun /> Light
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme("dark")}>
              <Moon /> Dark
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme("system")}>
              <Monitor /> System
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                clearTokens();
                queryClient.clear();
                void navigate({ to: "/login" });
              }}
            >
              <LogOut /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
