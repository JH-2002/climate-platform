# Imagem de desenvolvimento. O build de produção é definido na Fase 11 (hardening).
FROM node:22-alpine

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json* ./
# npm ci quando existe lockfile (reprodutível); npm install só na primeiríssima execução.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]
