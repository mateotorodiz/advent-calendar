const sessionSeconds = 7 * 24 * 60 * 60;
const cookieName = "__Host-advent_session";
const encoder = new TextEncoder();

function signingKey(secret: string) {
  return crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

export async function matchesPassphrase(candidate: string, passphrase: string, secret: string) {
  const key = await signingKey(secret);
  const expected = await crypto.subtle.sign("HMAC", key, encoder.encode(`passphrase:${passphrase}`));
  return crypto.subtle.verify("HMAC", key, expected, encoder.encode(`passphrase:${candidate}`));
}

export async function issueSession(secret: string, schedule: string, now: Date) {
  const expiry = Math.floor(now.getTime() / 1000) + sessionSeconds;
  const signature = new Uint8Array(await crypto.subtle.sign(
    "HMAC", await signingKey(secret), encoder.encode(`session:${schedule}:${expiry}`),
  ));
  const encoded = btoa(String.fromCharCode(...signature)).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
  return `${cookieName}=${expiry}.${encoded}; Path=/; Max-Age=${sessionSeconds}; Secure; HttpOnly; SameSite=Lax`;
}

export async function hasSession(request: Request, secret: string, schedule: string, now: Date) {
  const cookie = request.headers.get("Cookie")?.split(";").map((value) => value.trim())
    .find((value) => value.startsWith(`${cookieName}=`));
  const parts = /^(\d{1,12})\.([A-Za-z0-9_-]{43})$/.exec(cookie?.slice(cookieName.length + 1) ?? "");
  if (!parts || Number(parts[1]) <= Math.floor(now.getTime() / 1000)) {
    return false;
  }

  const [, expiry, encoded] = parts;
  const signature = Uint8Array.from(atob(encoded.replaceAll("-", "+").replaceAll("_", "/")), (byte) => byte.charCodeAt(0));
  return crypto.subtle.verify(
    "HMAC", await signingKey(secret), signature, encoder.encode(`session:${schedule}:${expiry}`),
  );
}
