import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useIndexingConfig, useProviderConfig } from "@/features/settings/api";
import { Connections } from "@/features/settings/connections";
import { IndexingForm } from "@/features/settings/indexing-form";
import { ProviderForm } from "@/features/settings/provider-form";
import { useSocketEvents } from "@/hooks/use-socket";

export const Route = createFileRoute("/_app/settings")({
  staticData: { title: "Settings" },
  component: SettingsPage,
});

function SettingsPage() {
  const provider = useProviderConfig();
  const indexing = useIndexingConfig();

  // Re-index runs report back over the websocket when they finish.
  useSocketEvents((e) => {
    if (e.type === "job.completed" && e.job === "reindex")
      toast.success(e.message ?? "Re-index finished");
  });

  return (
    <div className="mx-auto w-full max-w-3xl p-4">
      <Tabs defaultValue="provider">
        <TabsList>
          <TabsTrigger value="provider">LLM provider</TabsTrigger>
          <TabsTrigger value="indexing">Indexing</TabsTrigger>
          <TabsTrigger value="connections">Connections</TabsTrigger>
        </TabsList>

        <TabsContent value="provider">
          <Card>
            <CardHeader>
              <CardTitle>OpenAI-compatible provider</CardTitle>
              <CardDescription>
                Any endpoint that speaks the OpenAI API: OpenAI, OpenRouter, Ollama, vLLM, Groq…
                Used for embeddings when indexing and for chat when answering.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {provider.isPending ? (
                <FormSkeleton />
              ) : (
                // Remount when the saved row changes so the form re-initialises from it.
                <ProviderForm
                  key={provider.data?.updated_at ?? "new"}
                  saved={provider.data ?? null}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="indexing">
          <Card>
            <CardHeader>
              <CardTitle>Indexing</CardTitle>
              <CardDescription>
                How documents are split before they&apos;re embedded. Changing these re-indexes your
                documents in a Hatchet run.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {indexing.data ? (
                <IndexingForm key={indexing.data.updated_at ?? "defaults"} saved={indexing.data} />
              ) : (
                <FormSkeleton />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="connections">
          <Card>
            <CardHeader>
              <CardTitle>Model connections</CardTitle>
              <CardDescription>
                More OpenAI-compatible endpoints for agents to chat with — like Ollama running your
                own models locally. Embeddings always use the default provider, so every document is
                searched with the same model.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Connections />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function FormSkeleton() {
  return (
    <div className="grid gap-4">
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-2/3" />
    </div>
  );
}
