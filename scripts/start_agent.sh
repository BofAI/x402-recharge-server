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

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11+ is required"
  exit 1
fi

if [ ! -d venv ]; then
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo "Starting AINFT Merchant Agent"
echo "MCP endpoint: http://0.0.0.0:${PORT:-8000}/mcp"

python server.py
