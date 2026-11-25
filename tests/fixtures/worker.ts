import { createWorker, type Env } from "../../src/worker/index";

const worker = createWorker((request) => {
  const time = request.headers.get("x-fixture-time");
  return time ? new Date(time) : new Date();
});

export default {
  fetch(request: Request, env: Env) {
    const headers = new Headers(request.headers);
    // Give each pytest case its own rate limiter bucket.
    headers.set("CF-Connecting-IP", headers.get("x-fixture-client") ?? "fixture");
    const schedule = headers.get("x-fixture-schedule") ?? env.CALENDAR_SCHEDULE;
    return worker.fetch(new Request(request, { headers }), { ...env, CALENDAR_SCHEDULE: schedule });
  },
};
