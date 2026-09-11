#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
docker compose ps
frontend="$(docker compose port frontend 80 2>/dev/null | tr -d '\r' || true)"
backend="$(docker compose port backend 8000 2>/dev/null | tr -d '\r' || true)"
[ -n "$frontend" ] && echo "Frontend: http://$frontend"
[ -n "$backend" ] && echo "Backend:  http://$backend"
