# syntax=docker/dockerfile:1
#
# Single parameterized Dockerfile for the three Next.js apps in this
# pnpm+turbo monorepo (storefront / dashboard / platform-admin). Build
# with the repo's `frontend/` directory as context and select the app via
# --build-arg APP=storefront|dashboard|platform-admin.
#
# Multi-stage: `turbo prune` produces a minimal per-app subset of the
# monorepo so the `installer` stage only installs what that one app
# actually needs, and Next's `output: "standalone"` (see each app's
# next.config.ts) produces a minimal self-contained server so the final
# `runner` stage ships neither devDependencies nor the rest of the
# workspace's source.

ARG NODE_VERSION=24-slim

FROM node:${NODE_VERSION} AS base
RUN corepack enable

# ---- prune: compute the minimal subset of the monorepo for one app ----
FROM base AS pruner
ARG APP
WORKDIR /app
COPY . .
RUN npx turbo prune "@saas/${APP}" --docker

# ---- install + build: only the pruned subset's dependencies ----
FROM base AS installer
ARG APP
WORKDIR /app

COPY --from=pruner /app/out/json/ .
RUN pnpm install --frozen-lockfile

COPY --from=pruner /app/out/full/ .
# NEXT_PUBLIC_* vars are inlined into the CLIENT bundle at build time --
# a browser has no process.env, so `next build` replaces every
# `process.env.NEXT_PUBLIC_X` reference with a literal string right now,
# not at container-start. Setting it only in the compose `environment:`
# (runtime) is invisible to that bundle; it must be a build ARG here.
# Real bug found running this for real: the storefront's CSP header
# (computed server-side in middleware.ts, which DOES read live
# process.env) correctly said :8443, while the browser's own inlined
# fetch calls still hard-coded the dev default :8000 -- passing, until
# something browser-side actually tried to call the backend.
ARG NEXT_PUBLIC_BACKEND_PORT
ENV NEXT_PUBLIC_BACKEND_PORT=${NEXT_PUBLIC_BACKEND_PORT}
RUN pnpm turbo run build --filter="@saas/${APP}"

# ---- runtime: non-root, standalone server output only ----
FROM node:${NODE_VERSION} AS runner
ARG APP
ENV APP_NAME=${APP}
ENV NODE_ENV=production
WORKDIR /app

# node:24-slim already has a GID 1000 group (`node`) -- use 1001 to avoid
# colliding with it instead of reusing/renaming the image's own group.
RUN groupadd --gid 1001 nextjs && useradd --uid 1001 --gid nextjs --create-home nextjs \
    && apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=installer --chown=nextjs:nextjs /app/apps/${APP}/.next/standalone ./
COPY --from=installer --chown=nextjs:nextjs /app/apps/${APP}/.next/static ./apps/${APP}/.next/static

USER nextjs

# Each app's package.json pins its own dev/start port (3000/3001/3002);
# the standalone server reads PORT at runtime, so the compose file is the
# single source of truth for which port each container listens on.
ENV PORT=3000
# Real bug found running this for real: Docker auto-injects a HOSTNAME
# env var (the container's short ID) into every container, and Next's
# standalone server.js does `process.env.HOSTNAME || "0.0.0.0"` --
# without this override it binds ONLY to the container's own bridge-
# network address, never to loopback, so the HEALTHCHECK below (and any
# `docker exec ... curl 127.0.0.1`) gets connection-refused even though
# the app is genuinely up and Caddy can still reach it via the bridge IP.
ENV HOSTNAME="0.0.0.0"
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f "http://127.0.0.1:${PORT}/" || exit 1

# The standalone entrypoint's path is fixed at build time from ${APP}, so
# it can't be a plain array CMD (no arg expansion) -- shell form is
# required here, unlike the backend's Dockerfile.
CMD node apps/${APP_NAME}/server.js
