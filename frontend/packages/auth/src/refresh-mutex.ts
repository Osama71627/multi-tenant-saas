import { backendRefresh, type TokenPair } from "./backend";

/**
 * docs/ARCHITECTURE.md section 6.2 specifies a Redis-backed mutex here
 * ("مutex عبر Redis لمنع التدافع") to stop a burst of concurrent
 * requests from a single expired session each independently calling
 * `/auth/refresh` and racing SimpleJWT's rotate-on-refresh (only the
 * first rotation succeeds; the rest hit `ROTATE_REFRESH_TOKENS`'s reuse
 * detection and blacklist the WHOLE token family -- a real self-inflicted
 * logout bug if left unguarded).
 *
 * MVP simplification, stated honestly rather than silently deviating:
 * this is an in-process `Promise`-keyed mutex, not Redis-backed. It is
 * fully correct for a single Node server process (what `next dev` and a
 * single self-hosted Node container both are) -- concurrent requests in
 * the SAME process genuinely share this map and only one refresh call
 * goes out. It stops being sufficient the moment the dashboard app runs
 * as multiple replicas behind a load balancer (two different processes
 * can't see each other's in-memory map) -- swapping this for a Redis
 * `SET NX` lock at that point is a contained, isolated change (this
 * function's signature doesn't need to change, only its body).
 */
const inFlightRefreshes = new Map<string, Promise<TokenPair>>();

export function refreshWithMutex(refreshToken: string): Promise<TokenPair> {
  const existing = inFlightRefreshes.get(refreshToken);
  if (existing) return existing;

  const promise = backendRefresh(refreshToken).finally(() => {
    inFlightRefreshes.delete(refreshToken);
  });
  inFlightRefreshes.set(refreshToken, promise);
  return promise;
}
