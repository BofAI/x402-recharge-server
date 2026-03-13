#!/bin/bash
set -a
[ -f ../.env ] && source ../.env
set +a

# Defaults
export PORT=${PORT:-8000}
export AINFT_DEPOSIT_ADDRESS="TJWdoJk8KyrfxZ2iDUqz7fwpXaMkNqPehx" 
export X402_FACILITATOR_URL="http://localhost:8011"

npm run start
