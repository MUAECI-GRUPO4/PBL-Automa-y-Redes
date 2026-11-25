#!/usr/bin/env bash
# Crea .env a partir de .env.example con contraseñas y token aleatorios.
# No sobrescribe un .env existente: InfluxDB guarda las claves en el primer arranque.
set -euo pipefail
cd "$(dirname "$0")"
umask 077

if [ -e .env ]; then
  echo "Ya existe .env: no se toca." >&2
  exit 1
fi

trap 'rm -f .env.tmp' EXIT
while IFS= read -r linea || [ -n "$linea" ]; do
  linea=${linea%$'\r'}
  case "$linea" in
    \#*) ;;
    *=CAMBIAR)
      secreto=$(openssl rand -hex 24)
      linea="${linea%CAMBIAR}$secreto" ;;
  esac
  printf '%s\n' "$linea"
done < .env.example > .env.tmp
mv .env.tmp .env

echo "Creado .env (no se versiona). Siguiente paso: docker compose up -d"
