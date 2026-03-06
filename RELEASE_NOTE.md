# v1.0.0 Release Notes

**Date:** 2026-03-06

## Overview

Initial release of AINFT Merchant Agent. AI Agents can call top-up tools via MCP to credit AINFT accounts using TRC20 tokens or native TRX transfers.

## Highlights

**TRC20 Automatic Payment** — When an agent calls `ainft_pay_trc20`, the service returns HTTP 402 with an x402 challenge. After the agent signs and retries, the service verifies and settles on-chain via the Facilitator. Fully automatic for x402-compatible clients.

**Native TRX Transfer** — An agent calls `ainft_pay_trx` to get the deposit address and amount, completes a TRX transfer on-chain, then submits the txid. The service verifies the transaction via TRON RPC.

**Multi-Network** — Supports TRON mainnet and Nile testnet. Switch via the `NETWORK` environment variable; all addresses and tokens are driven by `config/networks.json`.

## Supported Tokens

| Token | Mainnet | Nile |
|-------|---------|------|
| TRX | native | native |
| USDT | TRC20 | TRC20 |
| USDD | TRC20 | TRC20 |
| USDC | TRC20 | — |
| NFT | TRC20 | — |

## Getting Started

```bash
git clone https://github.com/BofAI/ainft-merchant-agent.git
cd ainft-merchant-agent
cp .env.example .env
pip install -r requirements.txt
NETWORK=nile python server.py
```

See [README.md](README.md) for full documentation.

## Known Limitations

- No automated test suite yet (smoke test available via `./scripts/deploy.sh smoke`)
- `shasta` testnet is intentionally unsupported
- `recharge` / `get_balance` tools are deprecated and will be removed in a future release
