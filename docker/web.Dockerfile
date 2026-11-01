FROM nginx:1.30.6-alpine@sha256:0e52bd054126cdc040b1276c0af347aeb02a41b9cfe305d6094767ac30e97949
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontend/dist /usr/share/nginx/html
COPY LICENSE /usr/share/nginx/html/licenses/PROJECT-Apache-2.0.txt
EXPOSE 8080
