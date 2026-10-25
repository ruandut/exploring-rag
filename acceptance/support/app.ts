// Execution layer for the API: test users and an authenticated REST client.
// Step definitions call these instead of doing HTTP themselves.
import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";

import { APP_URL, BACKEND_DIR } from "./env.ts";

export type TestUser = { username: string; password: string };

/** A fresh user per scenario, so scenarios never see each other's data. */
export function createTestUser(prefix = "spec"): TestUser {
  const user = {
    username: `${prefix}-${randomBytes(4).toString("hex")}`,
    password: `pw-${randomBytes(8).toString("hex")}`,
  };
  execFileSync(
    "uv",
    ["run", "python", "manage.py", "create_test_user", user.username, user.password],
    { cwd: BACKEND_DIR, stdio: "pipe" },
  );
  return user;
}

/** Run Python inside the Django project (for checks with no HTTP API, e.g. Hatchet crons). */
export function runDjango(code: string): string {
  return execFileSync("uv", ["run", "python", "manage.py", "shell", "--no-imports", "-c", code], {
    cwd: BACKEND_DIR,
    stdio: "pipe",
  })
    .toString()
    .trim();
}

export type ApiResponse = { status: number; body: any; text: string };

export class ApiClient {
  accessToken: string | null = null;
  refreshToken: string | null = null;

  async login(user: TestUser): Promise<void> {
    const res = await this.request("POST", "/api/auth/token/", user);
    if (res.status !== 200) throw new Error(`Login failed: ${res.status} ${res.text}`);
    this.accessToken = res.body.access;
    this.refreshToken = res.body.refresh;
  }

  async request(method: string, path: string, body?: unknown): Promise<ApiResponse> {
    const res = await fetch(new URL(path, APP_URL), {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(this.accessToken ? { Authorization: `Bearer ${this.accessToken}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await res.text();
    let parsed: unknown = null;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      parsed = null;
    }
    return { status: res.status, body: parsed, text };
  }

  /** Multipart upload of files from acceptance/fixtures. */
  async upload(fileNames: string[], folder?: number): Promise<ApiResponse> {
    const form = new FormData();
    for (const name of fileNames) {
      const path = new URL(`../fixtures/${name}`, import.meta.url);
      form.append("files", new Blob([readFileSync(path)]), name);
    }
    if (folder) form.append("folder", String(folder));
    const res = await fetch(new URL("/api/library/documents/", APP_URL), {
      method: "POST",
      headers: { Authorization: `Bearer ${this.accessToken}` },
      body: form,
    });
    const text = await res.text();
    return { status: res.status, body: text ? JSON.parse(text) : null, text };
  }

  get = (path: string) => this.request("GET", path);
  put = (path: string, body: unknown) => this.request("PUT", path, body);
  post = (path: string, body: unknown) => this.request("POST", path, body);
}
