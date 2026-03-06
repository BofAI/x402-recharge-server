# AINFT Merchant Agent

Python MCP payee agent for AINFT top-up.  
Server-side responsibilities:
- `ainft_pay_trc20`: TRC20 recharge via x402 (`HTTP 402` challenge + paid retry)
- `ainft_pay_trx`: TRX native transfer verification (no x402)

## Current Status

- Supported runtime networks: `mainnet`, `nile`
- Verified full x402 payment loop: `nile + USDT`
- `shasta` is intentionally not supported in current build

## MCP Tools

- `ainft_pay_trc20(amount, token="USDT")`
  - supports TRC20 tokens only (e.g. USDT/USDD)
  - token enum is exposed in MCP `tools/list` schema (network-aware)
  - unpaid call returns `402 Payment Required`
  - header includes `PAYMENT-REQUIRED` (x402 challenge)
  - paid retry returns `200` on successful verify/settle
- `ainft_pay_trx(amount, txid="")`
  - does not use x402
  - first call returns native transfer instructions
  - second call (with `txid` or `X-TRX-TXID`) verifies transfer and returns success
- `recharge(amount, token="USDT", txid="")`
  - deprecated compatibility alias:
    - `token != TRX` -> forwards to `ainft_pay_trc20`
    - `token == TRX` -> forwards to `ainft_pay_trx`
- `get_balance(account_id="")`
  - deprecated on server side; moved to local `ainft-skill`

## Endpoints

- MCP streamable HTTP: `http://<host>:<port>/mcp`
- Optional HTTP route: `http://<host>:<port>/x402/recharge`
- Optional alias route: `http://<host>:<port>/x402/trc20/recharge`

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
  --data '{"jsonrpc":"2.0","id":"check-402","method":"tools/call","params":{"name":"ainft_pay_trc20","arguments":{"amount":"1","token":"USDT"}}}'
```

2) Run full auto-pay test with x402 client:

```bash
node ../skills/x402-payment/dist/x402_invoke.js \
  --url http://127.0.0.1:8000/mcp \
  --method POST \
  --input '{"jsonrpc":"2.0","id":"pay-1","method":"tools/call","params":{"name":"ainft_pay_trc20","arguments":{"amount":"1","token":"USDT"}}}' \
  --network nile
```

Expected: final response `status: 200` with settlement transaction hash.

## TRX Native Verification Example

1) Get transfer instructions:

```bash
curl -s -X POST 'http://127.0.0.1:8000/mcp' \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":"trx-1","method":"tools/call","params":{"name":"ainft_pay_trx","arguments":{"amount":"1"}}}'
```

2) After sending TRX on-chain, verify with txid:

```bash
curl -s -X POST 'http://127.0.0.1:8000/mcp' \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":"trx-2","method":"tools/call","params":{"name":"ainft_pay_trx","arguments":{"amount":"1","txid":"<TRX_TXID>"}}}'
```

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
