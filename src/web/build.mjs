import { cp } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const [mode, ...extra] = process.argv.slice(2);
if (!["demo", "production"].includes(mode) || extra.length) {
  console.error("Usage: pnpm build:web <demo|production>");
  process.exit(2);
}

const output = resolve("dist", mode);
await cp(fileURLToPath(new URL("./public/", import.meta.url)), output, { recursive: true });
console.log(`Built calendar pages in dist/${mode}`);
