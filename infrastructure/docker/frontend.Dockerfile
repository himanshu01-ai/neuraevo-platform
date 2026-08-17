# syntax=docker/dockerfile:1
#
# NeuraEvo frontend — Next.js 15 (SSR) on Node 22 (package.json: engines.node >=22).
#
# Vercel is the recommended host for the frontend (see docs/deployment.md); this
# image exists so the frontend can also run on any container platform without
# vendor lock-in. Build context is ./frontend:
#   docker build -f infrastructure/docker/frontend.Dockerfile \
#     --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com/api/v1 ./frontend
#
# Multi-stage: install deps -> build -> a slim runtime carrying production deps
# and the compiled .next output only.

# --- deps: full install for the build ---------------------------------------
FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- build: compile the Next.js app -----------------------------------------
FROM node:22-bookworm-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* values are inlined into the client bundle at build time, so the
# backend API URL must be present here — not only at runtime. Pass the real URL
# as a build argument in production; the default matches lib/env.ts so a build
# without the arg still succeeds (an empty value would fail its .url() check).
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
RUN npm run build

# --- runtime: production dependencies + built output ------------------------
FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Production dependencies only.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Compiled app and its runtime config (no public/ — the app has none).
COPY --from=build /app/.next ./.next
COPY --from=build /app/next.config.mjs ./next.config.mjs

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 nextjs \
    && chown -R nextjs:nextjs /app
USER nextjs

EXPOSE 3000

# `next start` honours $PORT; bind all interfaces so the platform can route.
CMD ["sh", "-c", "node_modules/.bin/next start -H 0.0.0.0 -p ${PORT:-3000}"]
