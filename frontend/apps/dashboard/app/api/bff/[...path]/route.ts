import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  CSRF_COOKIE,
  CSRF_HEADER,
  accessTokenCookieOptions,
  refreshTokenCookieOptions,
  backendProxy,
  csrfTokensMatch,
  refreshWithMutex,
  BackendAuthError,
} from "@saas/auth";
import { NextRequest, NextResponse } from "next/server";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

/**
 * The generic authenticated proxy -- docs/ARCHITECTURE.md section 6.2's
 * sequence diagram step "B->>N: GET /api/bff/products (cookie تلقائي)".
 * `baseUrl: "/api/bff"` in packages/api-client mirrors real Django paths
 * 1:1, so `params.path` here IS the real "/api/v1/..." path, forwarded
 * verbatim -- no per-resource route needed for every backend endpoint.
 *
 * On a 401 from Django (expired access token), refreshes ONCE via the
 * SAME in-process mutex `/api/bff/refresh` uses (not an internal HTTP
 * call to that route -- calling `refreshWithMutex` directly here avoids
 * a redundant round trip and lets this same response carry the updated
 * cookies), then retries the original request exactly once. A second
 * 401 after a successful refresh is treated as genuinely unauthorized,
 * not retried again (never an infinite loop).
 */
async function handle(request: NextRequest, path: string[]): Promise<NextResponse> {
  const method = request.method;
  const fullPath = path.join("/");

  if (!SAFE_METHODS.has(method)) {
    const cookieToken = request.cookies.get(CSRF_COOKIE)?.value;
    const headerToken = request.headers.get(CSRF_HEADER);
    if (!csrfTokensMatch(cookieToken, headerToken)) {
      return NextResponse.json({ detail: "CSRF token missing or invalid." }, { status: 403 });
    }
  }

  const contentType = request.headers.get("content-type");
  const body = SAFE_METHODS.has(method) ? undefined : await request.arrayBuffer();

  const accessToken = request.cookies.get(ACCESS_TOKEN_COOKIE)?.value ?? null;

  let upstream = await backendProxy(fullPath, { method, accessToken, body, contentType });
  let refreshedCookies: { access: string; refresh: string } | null = null;

  if (upstream.status === 401 && accessToken) {
    const refreshToken = request.cookies.get(REFRESH_TOKEN_COOKIE)?.value;
    if (refreshToken) {
      try {
        const tokens = await refreshWithMutex(refreshToken);
        refreshedCookies = tokens;
        upstream = await backendProxy(fullPath, {
          method,
          accessToken: tokens.access,
          body,
          contentType,
        });
      } catch (error) {
        if (!(error instanceof BackendAuthError)) throw error;
        // Refresh itself failed (expired/reused/blacklisted) -- fall
        // through with the original 401, cookies get cleared below.
      }
    }
  }

  const responseBody = await upstream.arrayBuffer();
  const response = new NextResponse(responseBody, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
    },
  });

  if (refreshedCookies) {
    response.cookies.set(ACCESS_TOKEN_COOKIE, refreshedCookies.access, accessTokenCookieOptions());
    response.cookies.set(
      REFRESH_TOKEN_COOKIE,
      refreshedCookies.refresh,
      refreshTokenCookieOptions()
    );
  } else if (upstream.status === 401) {
    response.cookies.delete({ name: ACCESS_TOKEN_COOKIE, path: "/" });
    response.cookies.delete({ name: REFRESH_TOKEN_COOKIE, path: "/api/bff/refresh" });
  }

  return response;
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: RouteContext) {
  return handle(request, (await context.params).path);
}
export async function POST(request: NextRequest, context: RouteContext) {
  return handle(request, (await context.params).path);
}
export async function PATCH(request: NextRequest, context: RouteContext) {
  return handle(request, (await context.params).path);
}
export async function PUT(request: NextRequest, context: RouteContext) {
  return handle(request, (await context.params).path);
}
export async function DELETE(request: NextRequest, context: RouteContext) {
  return handle(request, (await context.params).path);
}
