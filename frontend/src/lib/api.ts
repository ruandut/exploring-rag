import { getAccessToken, refreshAccessToken } from "./auth";

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    super(`API ${status}`);
    this.status = status;
    this.body = body;
  }
}

/** fetch() for /api/* with the JWT attached and one transparent refresh on 401. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const send = (token: string | null) => {
    const headers = new Headers(init.headers);
    // FormData (file uploads) must let the browser set the multipart boundary itself.
    if (!headers.has("Content-Type") && !(init.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(path, { ...init, headers });
  };

  let res = await send(getAccessToken());
  if (res.status === 401) {
    const fresh = await refreshAccessToken();
    if (fresh) res = await send(fresh);
  }
  if (res.status === 401) {
    window.location.assign("/login");
  }
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

export type Me = { id: number; username: string; email: string };
export type Health = { postgres: string; pgvector?: string; redis: string };
