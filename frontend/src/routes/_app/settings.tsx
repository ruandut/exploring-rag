import { createFileRoute } from "@tanstack/react-router";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useProviderConfig } from "@/features/settings/api";
import { Connections } from "@/features/settings/connections";
import { ProviderForm } from "@/features/settings/provider-form";

export const Route = createFileRoute("/_app/settings")({
  staticData: { title: "Settings" },
  component: SettingsPage,
});

function SettingsPage() {
  const provider = useProviderConfig();

  return (
    <div className="mx-auto w-full max-w-3xl p-4">
      <Tabs defaultValue="provider">
        <TabsList>
          <TabsTrigger value="provider">LLM provider</TabsTrigger>
          <TabsTrigger value="connections">Connections</TabsTrigger>
        </TabsList>

        <TabsContent value="provider">
          <Card>
            <CardHeader>
              <CardTitle>OpenAI-compatible provider</CardTitle>
              <CardDescription>
                Any endpoint that speaks the OpenAI API: OpenAI, OpenRouter, Ollama, vLLM, Groq…
                Used for chat when answering, and by embeddings that pick it as their endpoint.
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

        <TabsContent value="connections">
          <Card>
            <CardHeader>
              <CardTitle>Model connections</CardTitle>
              <CardDescription>
                More OpenAI-compatible endpoints — like Ollama running your own models locally — to
                chat with, or to embed with: each embedding names its own endpoint and model.
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
