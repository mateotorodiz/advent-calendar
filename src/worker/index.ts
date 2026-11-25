interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
}

export default {
  fetch(request: Request, env: Env): Response | Promise<Response> {
    if (request.method === "GET" && new URL(request.url).pathname === "/healthz") {
      return Response.json({ status: "ok" });
    }

    return env.ASSETS.fetch(request);
  },
};
