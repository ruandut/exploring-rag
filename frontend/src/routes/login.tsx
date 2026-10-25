import { useMutation } from "@tanstack/react-query";
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { BookOpenText } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { isLoggedIn, login } from "@/lib/auth";

export const Route = createFileRoute("/login")({
  beforeLoad: () => {
    if (isLoggedIn()) throw redirect({ to: "/chat" });
  },
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const signIn = useMutation({
    mutationFn: () => login(username, password),
    onSuccess: () => navigate({ to: "/chat" }),
  });

  return (
    <div className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <BookOpenText className="size-5" />
          </div>
          <CardTitle className="text-xl">Sign in to RAG Lab</CardTitle>
          <CardDescription>Use the account you created with createsuperuser.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              signIn.mutate();
            }}
          >
            <div className="grid gap-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {signIn.error && <p className="text-sm text-destructive">{signIn.error.message}</p>}
            <Button type="submit" disabled={signIn.isPending}>
              {signIn.isPending ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
