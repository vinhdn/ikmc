FROM node@sha256:4a4884e8a44826194dff92ba316264f392056cbe243dcc9fd3551e71cea02b90 AS dependencies

WORKDIR /app
COPY server/package.json server/package-lock.json ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 make g++ \
    && npm ci --omit=dev --ignore-scripts=false \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

FROM dependencies AS test
COPY server/index.js ./
COPY server/migrations ./migrations
COPY server/data ./data
COPY server/test ./test
CMD ["npm", "test"]

FROM node@sha256:4a4884e8a44826194dff92ba316264f392056cbe243dcc9fd3551e71cea02b90

ENV NODE_ENV=production \
    PORT=3000 \
    DB_PATH=/data/ikmc.sqlite

WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY server/package.json server/index.js ./
COPY server/migrations ./migrations
COPY server/data ./data
RUN mkdir -p /data && chown -R node:node /app /data

USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "index.js"]
