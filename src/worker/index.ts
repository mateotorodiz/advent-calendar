import { calendar } from "./calendar";
import { hasSession, issueSession, matchesPassphrase } from "./session";

export interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
  CALENDAR_SCHEDULE: string;
  CALENDAR_PASSPHRASE: string;
  SESSION_SIGNING_KEY: string;
  SIGN_IN_LIMITER: { limit(options: { key: string }): Promise<{ success: boolean }> };
}

const privateHeaders = { "Cache-Control": "private, no-store" };

function apiError(error: string, status: number, headers?: Record<string, string>) {
  return Response.json({ error }, { status, headers: { ...privateHeaders, ...headers } });
}

async function readPassphrase(request: Request): Promise<string | undefined> {
  const contentType = request.headers.get("Content-Type")?.split(";", 1)[0].trim().toLowerCase();
  if (contentType !== "application/json" || !request.body) {
    return;
  }

  const reader = request.body.getReader();
  const decoder = new TextDecoder();
  let length = 0;
  let body = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > 1024) {
        await reader.cancel();
        return;
      }
      body += decoder.decode(value, { stream: true });
    }
    const data = JSON.parse(body + decoder.decode());
    return typeof data?.passphrase === "string" ? data.passphrase : undefined;
  } catch {
    return;
  } finally {
    reader.releaseLock();
  }
}

async function signIn(request: Request, env: Env, schedule: string, now: Date) {
  const key = request.headers.get("CF-Connecting-IP") ?? "unknown";
  const { success } = await env.SIGN_IN_LIMITER.limit({ key });
  if (!success) {
    return apiError("too_many_attempts", 429, { "Retry-After": "60" });
  }

  const passphrase = await readPassphrase(request);
  if (passphrase === undefined) {
    return apiError("invalid_request", 400);
  }
  if (!(await matchesPassphrase(passphrase, env.CALENDAR_PASSPHRASE, env.SESSION_SIGNING_KEY))) {
    return apiError("wrong_passphrase", 401);
  }

  const cookie = await issueSession(env.SESSION_SIGNING_KEY, schedule, now);
  return new Response(null, { status: 204, headers: { ...privateHeaders, "Set-Cookie": cookie } });
}

export function createWorker(clock: (request: Request) => Date) {
  return {
    async fetch(request: Request, env: Env): Promise<Response> {
      const url = new URL(request.url);
      if (request.method === "GET" && url.pathname === "/healthz") {
        return Response.json({ status: "ok" });
      }

      let path: string;
      try {
        path = new URL(url.origin + decodeURIComponent(url.pathname)).pathname.replace(/\/{2,}/g, "/");
      } catch {
        return apiError("not_found", 404);
      }
      if (/^\/_gifts(?:\/|$)/i.test(path)) {
        return apiError("not_found", 404);
      }
      if (path !== "/api" && !path.startsWith("/api/")) {
        return env.ASSETS.fetch(request);
      }

      const day = /^\/api\/doors\/([1-9]\d?)$/.exec(path);
      if (path !== "/api/session" && path !== "/api/calendar" && !day) {
        return apiError("not_found", 404);
      }
      const method = path === "/api/session" ? "POST" : "GET";
      if (request.method !== method) {
        return apiError("method_not_allowed", 405, { Allow: method });
      }
      const schedule = env.CALENDAR_SCHEDULE;
      if ((schedule !== "demo" && schedule !== "production") || !env.CALENDAR_PASSPHRASE ||
          (env.SESSION_SIGNING_KEY?.length ?? 0) < 32 || !env.SIGN_IN_LIMITER) {
        return apiError("calendar_unavailable", 503);
      }

      const now = clock(request);
      if (path === "/api/session") {
        return signIn(request, env, schedule, now);
      }
      if (!(await hasSession(request, env.SESSION_SIGNING_KEY, schedule, now))) {
        return apiError("sign_in_required", 401);
      }

      const doors = calendar(schedule, now);
      if (!day) {
        return Response.json({ doors }, { headers: privateHeaders });
      }
      const door = doors[Number(day[1]) - 1];
      if (!door) {
        return apiError("not_found", 404);
      }
      if (!door.unlocked) {
        return apiError("door_locked", 403);
      }

      const manifest = await env.ASSETS.fetch(new Request(new URL("/_gifts/manifest.json", url)));
      if (!manifest.ok) {
        return apiError("gift_unavailable", 503);
      }
      const gifts: Record<string, unknown> = await manifest.json();
      const gift = gifts[door.day];
      if (!gift) {
        return apiError("gift_unavailable", 503);
      }
      return Response.json({ day: door.day, gift }, { headers: privateHeaders });
    },
  };
}

export default createWorker(() => new Date());
