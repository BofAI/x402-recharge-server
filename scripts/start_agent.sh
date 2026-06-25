#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env created from template. Review values and rerun."
  exit 1
fi

source .env

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 22+ is required"
  exit 1
fi

NODE_MAJOR="$(node -p "Number(process.versions.node.split('.')[0])")"
if [ "$NODE_MAJOR" -lt 22 ]; then
  echo "Node.js 22+ is required; found $(node -v)"
  exit 1
fi

if [ ! -d node_modules ]; then
  npm install
fi

npm run build

echo "Starting BANK OF AI Payment Agent"
echo "BANKOFAI_ENV: ${BANKOFAI_ENV:-prod}"
echo "MCP endpoint: http://0.0.0.0:${PORT:-8000}/mcp"

npm start
