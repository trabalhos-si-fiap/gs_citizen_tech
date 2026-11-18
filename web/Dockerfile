# syntax=docker/dockerfile:1
# ---- build: compila o Angular em modo produção ----
FROM node:22.21-alpine3.22 AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund --ignore-scripts
COPY angular.json tsconfig.json tsconfig.app.json ./
COPY src ./src
RUN npx ng build --configuration production

# ---- runtime: nginx sem root servindo apenas os arquivos estáticos ----
FROM nginxinc/nginx-unprivileged:1.29-alpine AS runtime
# Correções de segurança do Alpine; curl não é usado (healthcheck usa wget).
USER root
RUN apk upgrade --no-cache \
    && apk del --no-cache curl
COPY --chown=root:root nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=root:root /src/dist/reclame-ja-web/browser /usr/share/nginx/html
USER 101
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "--spider", "http://127.0.0.1:8080/healthz"]
