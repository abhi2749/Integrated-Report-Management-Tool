#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

command -v docker >/dev/null 2>&1 || { echo "Docker is required. Install/start Docker and retry." >&2; exit 1; }
for required in docker-compose.yml backend/Dockerfile frontend-ui/Dockerfile frontend-ui/nginx.conf; do
  [ -f "$required" ] || { echo "Required application file '$required' is missing from the package." >&2; exit 1; }
done

docker info >/dev/null
docker compose version >/dev/null
docker compose config --quiet

rebuild=0
no_browser="${NO_BROWSER:-}"
for arg in "$@"; do
  case "$arg" in
    --rebuild) rebuild=1 ;;
    --no-browser) no_browser=1 ;;
    *) echo "Unknown launcher option: $arg (use --rebuild or --no-browser)." >&2; exit 2 ;;
  esac
done

echo "=== Integrated Report Management Tool ==="
echo "Starting application with Docker-managed host ports..."
if [ "$rebuild" -eq 1 ]; then
  docker compose up -d --build
else
  docker compose up -d
fi

deadline=$(( $(date +%s) + 180 ))
healthy=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  backend_id="$(docker compose ps -q backend 2>/dev/null || true)"
  frontend_id="$(docker compose ps -q frontend 2>/dev/null || true)"
  backend_state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$backend_id" 2>/dev/null || true)"
  frontend_state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$frontend_id" 2>/dev/null || true)"
  if [ "$backend_state" = healthy ] && [ "$frontend_state" = healthy ]; then
    healthy=1
    break
  fi
  sleep 2
done
if [ "$healthy" -ne 1 ]; then
  docker compose ps
  echo "Application containers did not become healthy within 3 minutes." >&2
  exit 1
fi

frontend="$(docker compose port frontend 80 | tr -d '\r')"
backend="$(docker compose port backend 8000 2>/dev/null | tr -d '\r' || true)"
[ -n "$frontend" ] || { echo "Frontend host port could not be discovered." >&2; exit 1; }
echo "Frontend: http://$frontend"
if [ -n "$backend" ]; then echo "Backend:  http://$backend"; else echo "Backend:  (internal / not published)"; fi
case "$no_browser" in
  1|true|TRUE) ;;
  *)
    url="http://$frontend"
    if command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then open "$url" >/dev/null 2>&1 || true
    fi
    ;;
esac
