export interface AssetBinding {
  fetch(request: Request): Promise<Response>;
}

export type MediaKind = "photo" | "audio";

interface Gift {
  note?: string;
  joke?: string;
  song?: string;
  photo?: string;
  audio?: string;
}

const mediaTypes = new Map([
  ["photo.jpg", "image/jpeg"], ["photo.jpeg", "image/jpeg"], ["photo.png", "image/png"],
  ["photo.webp", "image/webp"], ["audio.mp3", "audio/mpeg"], ["audio.m4a", "audio/mp4"],
  ["audio.wav", "audio/wav"],
]);

export const privateHeaders = { "Cache-Control": "private, no-store" };

export async function loadGift(assets: AssetBinding, url: URL, day: number): Promise<Gift | undefined> {
  const manifest = await assets.fetch(new Request(new URL("/_gifts/manifest.json", url)));
  if (manifest.status !== 200) return;
  const gifts: Record<string, Gift> = await manifest.json();
  return gifts[day];
}

export function publicGift(gift: Gift, day: number) {
  const { note, joke, song, photo, audio } = gift;
  return {
    note, joke, song,
    photo: photo ? `/api/doors/${day}/photo` : undefined,
    audio: audio ? `/api/doors/${day}/audio` : undefined,
  };
}

export async function serveMedia(
  assets: AssetBinding, request: Request, url: URL, day: number, kind: MediaKind, gift: Gift,
): Promise<Response | undefined> {
  const name = gift[kind];
  const type = name?.startsWith(`${kind}.`) ? mediaTypes.get(name) : undefined;
  if (!type) return;

  const response = await assets.fetch(new Request(new URL(`/_gifts/${day}/${name}`, url), {
    method: request.method,
  }));
  if (response.status !== 200) return;

  const headers = new Headers({ ...privateHeaders, "Content-Type": type, "Accept-Ranges": "bytes",
    "X-Content-Type-Options": "nosniff" });
  const length = response.headers.get("Content-Length");
  if (length !== null) headers.set("Content-Length", length);

  const range = /^bytes=(\d*)-(\d*)$/i.exec(request.headers.get("Range")?.trim() ?? "");
  if (request.method === "HEAD" || !range || (!range[1] && !range[2]) || request.headers.has("If-Range")) {
    return new Response(response.body, { headers });
  }

  // The static assets binding returns the full file for range requests.
  const bytes = await response.arrayBuffer();
  const [, first, last] = range;
  const start = first ? Number(first) : Math.max(bytes.byteLength - Number(last), 0);
  const end = first && last ? Math.min(Number(last), bytes.byteLength - 1) : bytes.byteLength - 1;
  if (start > end) {
    headers.set("Content-Range", `bytes */${bytes.byteLength}`);
    headers.set("Content-Length", "0");
    return new Response(null, { status: 416, headers });
  }

  headers.set("Content-Range", `bytes ${start}-${end}/${bytes.byteLength}`);
  headers.set("Content-Length", String(end - start + 1));
  return new Response(bytes.slice(start, end + 1), { status: 206, headers });
}
