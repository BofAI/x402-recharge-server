# AINFT Merchant Agent

AINFT Merchant Agent is a Python MCP server that handles payee-side token top-up flows for AINFT. It exposes x402-protected tools, verifies payment, and then calls the AINFT merchant confirmation API to finalize the recharge.

## Overview

This repository is the server-side component behind AINFT recharge flows. It is intended for operators who need to:

- run an MCP endpoint for AINFT top-up
- accept x402 payment challenges and paid retries
- support TRON and BSC runtime configurations
- publish the agent through ERC-8004 discovery metadata

## How It Works

At a high level, the runtime flow is:

1. A client calls an MCP tool such as `ainft_pay_trc20`.
2. The server returns `402 Payment Required` when payment has not been attached.
3. The client retries with a valid x402 payment header.
4. The service verifies and settles the payment through the configured facilitator.
5. The service calls the AINFT merchant confirmation API to complete the top-up.
6. The MCP response returns settlement details and top-up confirmation status.

ERC-8004 registration is a separate operational step. It does not affect runtime startup and is only used for on-chain agent discovery.

## MCP Tools

- `ainft_pay_trc20(amount, token="USDT")`
  Primary recharge tool. On TRON it supports USDT and USDD. On BSC it exposes the network-aware token enum returned by `tools/list`.
- `ainft_pay_erc20(amount, token="USDT")`
  Explicit EVM/BSC alias for recharge flows.
- `recharge(amount, token="USDT", txid="")`
  Deprecated compatibility alias. It forwards to the chain-appropriate recharge tool.
- `get_balance(account_id="")`
  Deprecated on the merchant server. Balance lookup moved to the local `ainft-skill`.

## Endpoints

- MCP streamable HTTP: `http://<host>:<port>/mcp`
- Optional recharge route: `http://<host>:<port>/x402/recharge`
- Optional TRC20 alias: `http://<host>:<port>/x402/trc20/recharge`

## Supported Environments

External environments should be described as:

- `ainft dev`
- `ainft prod`

Runtime chain selection remains separate:

- `mainnet`
- `nile`
- `bsc`
- `bsc-testnet`

Only `ainft dev` and `ainft prod` should be presented as public environment labels. Chain names are implementation details used by the service configuration.

## Prerequisites

- Python `>=3.11`
- `pip`
- Node.js if you want to run the optional x402 client example
- Docker 24+ if you want to use the container deployment flow

Recommended local setup:

```bash
cd ainft-merchant-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you also need ERC-8004 registration helpers:

```bash
pip install git+https://github.com/BofAI/8004-sdk.git#subdirectory=python
```

## Quick Start

```bash
cd ainft-merchant-agent
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
NETWORK=mainnet HOST=0.0.0.0 PORT=8000 python3 server.py
```

Once the server is up, the main MCP endpoint is available at `http://127.0.0.1:8000/mcp`.

## Example x402 Verification

Check that an unpaid request returns `402 Payment Required`:

```bash
curl -i -X POST 'http://127.0.0.1:8000/mcp' \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":"check-402","method":"tools/call","params":{"name":"ainft_pay_trc20","arguments":{"amount":"1","token":"USDT"}}}'
```

Run a paid retry with the current x402 pay CLI.
Install it first if needed:

```bash
npm install -g @bankofai/x402-mcp
```

Then execute:

```bash
x402 pay http://127.0.0.1:8000/mcp \
  -X POST \
  -d '{"jsonrpc":"2.0","id":"pay-1","method":"tools/call","params":{"name":"ainft_pay_trc20","arguments":{"amount":"1","token":"USDT"}}}' \
  --network mainnet
```

Expected result: final response `status: 200` with a settlement transaction hash and top-up confirmation payload.

## Configuration

Set the following values in `.env`:

- `AINFT_ENV=dev|prod`
- `NETWORK=mainnet|nile|bsc|bsc-testnet`
- `HOST=0.0.0.0`
- `PORT=8000`
- `LOG_LEVEL=info`
- `AINFT_API_URL=<optional explicit override>`
- `AINFT_WEB_URL=<optional explicit override>`
- `X402_FACILITATOR_URL=https://facilitator.bankofai.io`
- `AINFT_MERCHANT_ID=<merchant id>`
- `AINFT_MERCHANT_KEY=<merchant key>`
- `AINFT_TOPUP_CONFIRM_URL=<optional>`
- `AINFT_TOPUP_CONFIRM_RETRIES=4`

Network addresses and token metadata are loaded from `config/networks.json`.

Recommended external mapping:

- `ainft dev`
  API base should point to `https://chat-dev.ainft.com`
- `ainft prod`
  API base should point to the production AINFT domain

## Top-Up Confirmation

After payment succeeds, the service automatically calls the merchant confirmation API, which defaults to `m/credit/recharge`.

- Auth headers: `X-Merchant-Id` and `X-Merchant-Key`
- Request body: `{"chain":"<network specific>","tx_hash":"<txid>"}`
- Response: attached under `topup_confirmation`

Currently verified chain confirmation values:

- TRON Mainnet: `eip155:728126428`
- TRON Nile: `tron:nile`
- BSC Mainnet: `eip155:56`
- BSC Testnet: skipped because the current AINFT merchant confirmation API does not support it

## Deployment

Container deployment notes live in [DEPLOYMENT.md](DEPLOYMENT.md).

## ERC-8004 Registration

On-chain registration is a separate workflow from service startup:

1. Render bootstrap metadata.
2. Upload the metadata to IPFS or HTTPS.
3. Register the agent and save the returned `agent_id`.
4. Render final metadata with the real `agent_id`.
5. Upload the final metadata.
6. Update the existing agent URI.

The rendered registration metadata includes:
- `image` / icon URL
- `tags`
- MCP payment metadata with `paymentProtocol: "x402"`

You can override the defaults with:
- `AINFT_REGISTRATION_IMAGE=https://...` or `ipfs://...`
- `AINFT_REGISTRATION_TAGS=ainft,mcp,x402,tron,bsc,payments`

See [docs/REGISTRATION.md](docs/REGISTRATION.md) for the complete flow.

## Security

Read [SECURITY.md](SECURITY.md) before handling merchant credentials, operator keys, or Pinata tokens.

## Contributing

Contribution guidelines live in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This repository is released under the [MIT License](LICENSE).
