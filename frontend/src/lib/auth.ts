// JWT storage + refresh. Tokens live in localStorage to keep the learning setup simple;
// see System Design → Security notes for the trade-off vs httpOnly cookies.

const ACCESS_KEY = "rag.access";
const REFRESH_KEY = "rag.refresh";

export type Tokens = { access: string; refresh: string };

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function isLoggedIn(): boolean {
  return localStorage.getItem(REFRESH_KEY) !== null;
}

function storeTokens(tokens: Partial<Tokens>) {
  if (tokens.access) localStorage.setItem(ACCESS_KEY, tokens.access);
  if (tokens.refresh) localStorage.setItem(REFRESH_KEY, tokens.refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export async function login(username: string, password: string): Promise<void> {
  const res = await fetch("/api/auth/token/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(res.status === 401 ? "Wrong username or password" : "Login failed");
  storeTokens((await res.json()) as Tokens);
}

// Concurrent 401s share one refresh request instead of racing (refresh tokens rotate).
let refreshing: Promise<string | null> | null = null;

export function refreshAccessToken(): Promise<string | null> {
  refreshing ??= (async () => {
    const refresh = localStorage.getItem(REFRESH_KEY);
    if (!refresh) return null;
    const res = await fetch("/api/auth/token/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) {
      clearTokens();
      return null;
    }
    const tokens = (await res.json()) as Partial<Tokens>;
    storeTokens(tokens);
    return tokens.access ?? null;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}
