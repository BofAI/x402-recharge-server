# AINFT Merchant Agent

Python MCP payee agent for AINFT top-up.  
Server-side responsibilities:
- `ainft_pay_trc20`: token recharge via x402 on configured network
- `ainft_pay_erc20`: explicit ERC20 recharge via x402 on BSC/EVM

## Current Status

- External environment model: `ainft dev` / `ainft prod`
- Default local dev run uses `chat-dev` API with mainnet recharge addresses
- Verified x402 token flows on local MCP
- `shasta` is intentionally not supported in current build

## Environment Model

Only two external environments should be exposed:

- `ainft dev`
  - API / merchant endpoints point to `chat-dev`
  - Recharge addresses may still use production-chain addresses when required by the business
- `ainft prod`
  - API / merchant endpoints point to the production domain
  - Recharge addresses use production configuration

Chain type is a separate dimension:

- `tron`
- `bsc`

The codebase still keeps runtime keys such as `mainnet`, `nile`, `bsc`, and `bsc-testnet`, but they should not be exposed as external environment names.

## MCP Tools

- `ainft_pay_trc20(amount, token="USDT")`
  - token x402 recharge on configured chain
  - TRON: USDT/USDD
  - BSC: USDT/USDC
  - token enum is exposed in MCP `tools/list` schema (network-aware)
  - unpaid call returns `402 Payment Required`
  - header includes `PAYMENT-REQUIRED` (x402 challenge)
  - paid retry returns `200` on successful verify/settle
- `ainft_pay_erc20(amount, token="USDT")`
  - explicit alias for EVM/BSC x402 recharge
- `recharge(amount, token="USDT", txid="")`
  - deprecated compatibility alias:
    - forwards to `ainft_pay_trc20` on TRON
    - forwards to `ainft_pay_erc20` on BSC/EVM
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
NETWORK=mainnet HOST=0.0.0.0 PORT=8000 python server.py
```

## x402 Verification (TRON Mainnet + USDT)

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
  --network mainnet
```

Expected: final response `status: 200` with settlement transaction hash.

## Configuration

Set in `.env`:

- `AINFT_ENV=dev|prod`
- `NETWORK=mainnet|nile|bsc|bsc-testnet`
- `HOST=0.0.0.0`
- `PORT=8000`
- `LOG_LEVEL=info`
- `AINFT_API_URL=<optional explicit override>`
- `AINFT_WEB_URL=<optional explicit override>`
- `X402_FACILITATOR_URL=https://facilitator.bankofai.io`
- `AINFT_MERCHANT_ID=<merchant id>` (used for the post-topup confirmation API)
- `AINFT_MERCHANT_KEY=<merchant key>`
- `AINFT_TOPUP_CONFIRM_URL=<optional>` (defaults to `<ainftApiUrl>/m/credit/recharge`)
- `AINFT_TOPUP_CONFIRM_RETRIES=4`

Network addresses and token settings come from `config/networks.json`.

Recommended external mapping:

- `ainft dev`
  - `AINFT_ENV=dev`
  - local default: `NETWORK=mainnet`
  - API base: `https://chat-dev.ainft.com`
- `ainft prod`
  - `AINFT_ENV=prod`
  - local/prod deployment should point to the production API domain
  - chain/address selection follows production config

### Address Strategy

- Dev integration currently still uses `https://chat-dev.ainft.com`
- Recharge collection addresses use production-chain addresses as required by the business
- Current production-chain collection addresses:
  - TRON: `TRKJ2Szy6uPPiiBiLW2uJUrzjr2n2Mjb43`
  - BSC: `0x7653af32ca66be11080eb447d0fb1614f05edfb9`

### Post-Topup Confirmation

After a successful payment flow, the service automatically calls the merchant confirmation API (default: `m/credit/recharge`) to finalize the top-up:

- Auth headers: `X-Merchant-Id` / `X-Merchant-Key`
- Request body: `{"chain":"<network specific>","tx_hash":"<txid>"}`
- The response is attached under the `topup_confirmation` field.

Currently verified:

- TRON Mainnet: `eip155:728126428`
- TRON Nile: `tron:nile`
- BSC Mainnet: `eip155:56`
- BSC Testnet: the AINFT merchant confirmation API does not currently support it, and the service returns `topup_confirmation.status=skipped`

Note:

- The `confirmChain` values above are internal chain confirmation parameters, not external environment names

## Deployment

Use Docker runbook in [DEPLOYMENT.md](DEPLOYMENT.md).

## Registration

ERC-8004 registration is a separate step from runtime startup.  
See [docs/REGISTRATION.md](docs/REGISTRATION.md).
