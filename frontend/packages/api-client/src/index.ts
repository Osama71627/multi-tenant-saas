import createClient from "openapi-fetch";

import type { paths } from "./generated/schema";

/**
 * `baseUrl: "/api/bff"` deliberately mirrors the real Django path
 * 1:1 -- every generated path already starts with "/api/v1/...", and
 * `apps/dashboard/app/api/bff/[...path]/route.ts`'s catch-all forwards
 * the captured segments verbatim to `${BACKEND_INTERNAL_URL}` with zero
 * rewriting. This is what keeps the generated types directly usable: no
 * custom path-transform layer that could silently drift from the real
 * schema.
 *
 * Browser code (client components) calls this; it never talks to Django
 * directly (docs/ARCHITECTURE.md's BFF diagram: B->>N, never B->>D) --
 * cookies (the access token) go along automatically since this is a
 * same-origin call.
 */
export function createApiClient() {
  return createClient<paths>({ baseUrl: "/api/bff" });
}

export type { paths } from "./generated/schema";
export type { components } from "./generated/schema";
