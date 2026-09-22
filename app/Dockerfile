# ---------- Build stage ----------
FROM node:20-alpine AS build
WORKDIR /app

# Install deps (cache-friendly)
COPY package.json package-lock.json* ./
RUN npm install

# Build
COPY . .
RUN npm run build

# ---------- Runtime stage ----------
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

# Custom nginx config (listens on 8080, runs as uid 101)
COPY deploy/nginx.conf /etc/nginx/nginx.conf

# Static build output
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["/bin/sh", "-c", "wget -qO- http://127.0.0.1:8080/healthz >/dev/null 2>&1 || exit 1"]
