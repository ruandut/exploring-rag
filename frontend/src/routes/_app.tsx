import { createFileRoute, Outlet, redirect, useMatches } from "@tanstack/react-router";
import { useEffect } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { isLoggedIn } from "@/lib/auth";
import { socket } from "@/lib/socket";

// Pathless layout: every authenticated page renders inside the navigation drawer.
export const Route = createFileRoute("/_app")({
  beforeLoad: () => {
    if (!isLoggedIn()) throw redirect({ to: "/login" });
  },
  component: AppLayout,
});

function AppLayout() {
  useEffect(() => {
    socket.start();
    return () => socket.stop();
  }, []);

  const matches = useMatches();
  const title = matches.findLast((m) => m.staticData?.title)?.staticData.title;

  return (
    <SidebarProvider>
      <AppSidebar />
      {/* Fixed viewport height: pages scroll inside the content area, so Chat can pin its composer. */}
      <SidebarInset className="h-svh min-w-0 overflow-hidden">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 data-[orientation=vertical]:h-4" />
          <h1 className="text-sm font-medium">{title}</h1>
        </header>
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}

declare module "@tanstack/react-router" {
  interface StaticDataRouteOption {
    title?: string;
  }
}
