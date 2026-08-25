#!/usr/bin/env node
/**
 * docs/ARCHITECTURE.md section 7.5: "الملف مثبّت في Git تحت
 * backend/schema/openapi.json" is the ONE contract source; this script
 * (`pnpm generate:api` at the repo root) regenerates
 * packages/api-client/src/generated/schema.d.ts from it via
 * openapi-typescript. CI re-runs this and diffs the result -- an
 * uncommitted regeneration is a build failure, not a silent drift
 * (point 5 of that same section: "استحالة انحراف العقد بصمت").
 *
 * Uses openapi-typescript's programmatic API directly rather than
 * shelling out to its CLI -- no child process/shell involved at all, so
 * there's no argument-escaping surface to worry about.
 */
import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import openapiTS, { astToString } from "openapi-typescript";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "../../../..");
const schemaPath = resolve(repoRoot, "backend/schema/openapi.json");
const outPath = resolve(__dirname, "../src/generated/schema.d.ts");

if (!existsSync(schemaPath)) {
  console.error(
    `No OpenAPI schema found at ${schemaPath}.\n` +
      "Generate it first: cd backend && python manage.py spectacular " +
      "--format openapi-json --file schema/openapi.json"
  );
  process.exit(1);
}

const ast = await openapiTS(new URL(`file://${schemaPath.replace(/\\/g, "/")}`));
const output = astToString(ast);

await mkdir(dirname(outPath), { recursive: true });
await writeFile(outPath, output);

console.log(`Generated ${outPath} from ${schemaPath}`);
