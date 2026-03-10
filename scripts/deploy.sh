#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

SERVICE_NAME="ainft-merchant-agent"
PORT="${PORT:-8000}"

usage() {
  cat <<'EOF'
Usage: scripts/deploy.sh <command>

Commands:
  up        Build and start container
  down      Stop and remove container
  restart   Restart running container
  logs      Follow service logs
  status    Show service status
  smoke     Run MCP deposit availability check
EOF
}

require_compose() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required"
    exit 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "docker compose v2 is required"
    exit 1
  fi
}

ensure_env() {
  if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env created from template. Review values and rerun."
    exit 1
  fi
}

smoke_test() {
  local tools
  tools="$(curl -fsS "http://127.0.0.1:${PORT}/mcp" \
    -H 'content-type: application/json' \
    -H 'accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  )"

  echo "$tools" | grep -q '"ainft_pay_trc20"'
  echo "$tools" | grep -q '"ainft_pay_erc20"'
  echo "smoke check passed: MCP tools/list includes ainft_pay_trc20 and ainft_pay_erc20"
}

main() {
  local cmd="${1:-}"
  if [ -z "$cmd" ]; then
    usage
    exit 1
  fi

  require_compose
  ensure_env

  case "$cmd" in
    up)
      docker compose up -d --build
      echo "service started: ${SERVICE_NAME}"
      ;;
    down)
      docker compose down
      echo "service stopped: ${SERVICE_NAME}"
      ;;
    restart)
      docker compose restart "${SERVICE_NAME}"
      echo "service restarted: ${SERVICE_NAME}"
      ;;
    logs)
      docker compose logs -f "${SERVICE_NAME}"
      ;;
    status)
      docker compose ps
      ;;
    smoke)
      smoke_test
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
