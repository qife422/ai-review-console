FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund --fetch-retries=10 --fetch-timeout=600000
COPY frontend ./
RUN npm run build

FROM nginx:1.30.6-alpine@sha256:0e52bd054126cdc040b1276c0af347aeb02a41b9cfe305d6094767ac30e97949
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY LICENSE /usr/share/nginx/html/licenses/PROJECT-Apache-2.0.txt
EXPOSE 8080
