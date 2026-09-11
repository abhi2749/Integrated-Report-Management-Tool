FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.29-alpine

# Prepare all Nginx runtime paths while the image build still has root
# privileges. The runtime container can therefore drop CHOWN capability.
RUN mkdir -p /var/cache/nginx/client_temp     /var/cache/nginx/proxy_temp     /var/cache/nginx/fastcgi_temp     /var/cache/nginx/uwsgi_temp     /var/cache/nginx/scgi_temp     /tmp/nginx     && chown -R 101:101 /var/cache/nginx /tmp/nginx     && chmod -R u+rwX /var/cache/nginx /tmp/nginx

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-main.conf /etc/nginx/nginx.conf

# Start Nginx directly. The official entrypoint performs runtime
# filesystem initialization that requires capabilities intentionally
# removed by docker-compose.
USER 101:101
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
