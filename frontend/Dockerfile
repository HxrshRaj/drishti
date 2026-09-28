FROM node:22-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# NEXT_PUBLIC_* vars are inlined into the client bundle at BUILD time, not
# read at container runtime — they must be build args, and must be URLs
# reachable from the operator's browser (typically the host's localhost
# port mapping), not Docker-internal service names.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_GATEWAY_BASE_URL=http://localhost:8100
ARG NEXT_PUBLIC_INFERENCE_MODE=live
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_GATEWAY_BASE_URL=$NEXT_PUBLIC_GATEWAY_BASE_URL \
    NEXT_PUBLIC_INFERENCE_MODE=$NEXT_PUBLIC_INFERENCE_MODE
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
