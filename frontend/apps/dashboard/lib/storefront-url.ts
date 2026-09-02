/**
 * Builds the URL to a merchant's REAL, live storefront from their
 * store's `primary_domain` (apps.stores.serializers.StoreDetailSerializer
 * -- a real `StoreDomain` row, not a frontend-reconstructed guess, see
 * that field's own docstring for why). Used by the dashboard's
 * "Preview store" actions to open the actual storefront in a new tab,
 * instead of the internal fixture-data preview at .../preview (which
 * still exists and is still correct for its own separate job: theme
 * browsing before a real Store exists at all, e.g. the public
 * marketplace preview -- this helper is not used there).
 *
 * Hardcodes `http:` and a build-time port, same reasoning as
 * apps/storefront/lib/backend.ts's `serverBackendOrigin()`: this
 * project is local-dev/staging only so far, no TLS termination for
 * `*.lvh.me` exists anywhere yet -- a real production origin scheme is
 * a separate, not-yet-designed concern.
 */
const STOREFRONT_PORT = process.env.NEXT_PUBLIC_STOREFRONT_PORT ?? "4000";

export function storefrontUrl(primaryDomain: string): string {
  return `http://${primaryDomain}:${STOREFRONT_PORT}`;
}
