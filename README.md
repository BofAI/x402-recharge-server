# AINFT Merchant Agent

Python MCP payee agent for AINFT top-up.  
At `recharge` call time, server returns x402 challenge (`HTTP 402`), then verifies/settles payment on retry.

## Current Status

- Supported runtime networks: `mainnet`, `nile`
- Verified full x402 payment loop: `nile + USDT`
- `shasta` is intentionally not supported in current build

## MCP Tools

- `recharge(amount, token="USDT")`
  - unpaid call returns `402 Payment Required`
  - header includes `PAYMENT-REQUIRED` (x402 challenge)
  - paid retry returns `200` on successful verify/settle
- `get_balance(account_id="")`
  - returns AINFT balance query entry URLs

## Endpoints

- MCP streamable HTTP: `http://<host>:<port>/mcp`
- Optional HTTP route: `http://<host>:<port>/x402/recharge`

## Quick Start

```bash
cd ainft-merchant-agent
cp .env.example .env
pip install -r requirements.txt
NETWORK=nile HOST=0.0.0.0 PORT=8000 python server.py
```

## x402 Verification (Nile + USDT)

1) Confirm unpaid request returns 402:

```bash
curl -i -X POST 'http://127.0.0.1:8000/mcp' \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":"check-402","method":"tools/call","params":{"name":"recharge","arguments":{"amount":"1","token":"USDT"}}}'
```

2) Run full auto-pay test with x402 client:

```bash
node ../skills/x402-payment/dist/x402_invoke.js \
  --url http://127.0.0.1:8000/mcp \
  --method POST \
  --input '{"jsonrpc":"2.0","id":"pay-1","method":"tools/call","params":{"name":"recharge","arguments":{"amount":"1","token":"USDT"}}}' \
  --network nile
```

Expected: final response `status: 200` with settlement transaction hash.

## Configuration

Set in `.env`:

- `NETWORK=mainnet|nile`
- `HOST=0.0.0.0`
- `PORT=8000`
- `LOG_LEVEL=info`
- `X402_FACILITATOR_URL=https://facilitator.bankofai.io`

Network addresses and token settings come from `config/networks.json`.

## Deployment

Use Docker runbook in [DEPLOYMENT.md](DEPLOYMENT.md).

## Registration

ERC-8004 registration is a separate step from runtime startup.  
See [docs/REGISTRATION.md](docs/REGISTRATION.md).
