/**
 * Same-origin API client. Auth is carried by httpOnly cookies set by the backend;
 * state-changing requests echo the CSRF cookie in the X-CSRF-Token header.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(name + "="));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

async function ensureCsrf(): Promise<string> {
  let token = readCookie("fs_csrf");
  if (!token) {
    await fetch("/api/auth/csrf", { credentials: "same-origin" });
    token = readCookie("fs_csrf");
  }
  return token ?? "";
}

function errorDetail(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d) && d.length && typeof d[0] === "object" && d[0] && "msg" in d[0]) {
      return d
        .map((e: { msg: string }) => e.msg.replace(/^Value error, /, ""))
        .join("; ");
    }
  }
  return fallback;
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      const csrf = await ensureCsrf();
      const r = await fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "same-origin",
        headers: { "x-csrf-token": csrf },
      });
      return r.ok;
    })().finally(() => {
      setTimeout(() => (refreshing = null), 0);
    });
  }
  return refreshing;
}

const NO_REFRESH = ["/api/auth/login", "/api/auth/refresh", "/api/auth/mfa/verify", "/api/auth/logout"];

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}, retry = true): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("content-type", "application/json");
    body = JSON.stringify(init.json);
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers.set("x-csrf-token", await ensureCsrf());
  }
  const res = await fetch(path, { ...init, method, headers, body, credentials: "same-origin" });
  if (res.status === 401 && retry && !NO_REFRESH.includes(path)) {
    if (await tryRefresh()) return api<T>(path, init, false);
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, errorDetail(data, res.statusText || "Request failed"));
  return data as T;
}
