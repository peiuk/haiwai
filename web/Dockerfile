# 前端：先构建，再用 nginx 提供页面并把 /api 转给后端（见 nginx.conf）。
FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
# web/.env（VITE_SUPPORT_CONTACT 等）要在构建前写好，见 .env.example
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
