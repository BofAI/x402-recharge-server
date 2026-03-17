# Deployment Runbook

This document is for OP deployment only.

## Purpose

Deploy the BofAI payment MCP service in production so clients can use:

```text
https://ainft-agent.bankofai.io/mcp
```

## Production Scope

Supported routes:

- TRON mainnet: `USDT`, `USDD`
- BSC mainnet: `USDT` only

## Required Configuration

```bash
cp .env.example .env
```

Minimum production values:

```dotenv
AINFT_ENV=prod
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
X402_FACILITATOR_URL=https://facilitator.bankofai.io
FACILITATOR_API_KEY=MAIN_API_KEY
```

## Deploy

```bash
./scripts/deploy.sh up
```

## Verify

```bash
./scripts/deploy.sh smoke
./scripts/deploy.sh logs
```

Optional challenge check:

```bash
curl -i http://127.0.0.1:8000/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":"check-402","method":"tools/call","params":{"name":"recharge","arguments":{"amount":"1","token":"USDT"}}}'
```

Expected:

- HTTP `402 Payment Required`
- `TRON mainnet` route for `USDT`
- `BSC mainnet` route for `USDT`

For `USDD`, expected route is:

- `TRON mainnet`

## Registration

Deployment and 8004 registration are separate.

Use:

- [docs/REGISTRATION.md](/Users/bobo/code/skills/ainft-merchant-agent/docs/REGISTRATION.md)

## Notes

- Runtime variable names still use some legacy naming, but the public-facing service is `BofAI`.
- Do not put operator private keys into the runtime container.
