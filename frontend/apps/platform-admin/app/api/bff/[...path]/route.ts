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
 * Generic authenticated proxy, same shape as apps/dashboard's -- forwards
 * `params.path` verbatim to Django (so it covers `/api/v1/platform/*`
 * with no per-endpoint route needed), refreshes once on a 401, retries
 * once, never loops.
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
