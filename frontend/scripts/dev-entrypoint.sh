#!/bin/sh
# Entrada do contêiner de desenvolvimento (spec 014). O node_modules fica num volume do Docker,
# que não acompanha a imagem: quando o package-lock.json muda, as dependências são atualizadas
# aqui, antes de subir o servidor.
set -e
stamp=node_modules/.lock-hash
want=$(sha256sum package-lock.json | cut -d' ' -f1)
if [ ! -f "$stamp" ] || [ "$(cat "$stamp")" != "$want" ]; then
  echo "package-lock.json mudou: atualizando as dependências..."
  npm install --no-audit --no-fund
  echo "$want" > "$stamp"
fi
exec npm run dev
