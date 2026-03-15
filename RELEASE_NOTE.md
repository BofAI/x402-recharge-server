# v1.1.0 Release Notes

**Date:** 2026-03-15

## Overview

AINFT Merchant Agent now exposes a single MCP top-up tool, `recharge`, and supports TRC20 tokens only.

## Highlights

**Single MCP Tool** — Agents now call `recharge(amount, token)` for all supported top-ups. The previous split between `ainft_pay_trc20` and `recharge` has been removed.

**TRC20 Automatic Payment** — When an agent calls `recharge`, the service returns HTTP 402 with an x402 challenge. After the agent signs and retries, the service verifies and settles on-chain via the Facilitator. Fully automatic for x402-compatible clients.

**Environment-Based Deployment** — Runtime configuration now uses `AINFT_ENV=dev|prod`. `dev` maps to TRON Nile for x402 testing, and `prod` maps to TRON mainnet for production recharge.

## Supported Tokens

| Token | Mainnet | Nile |
|-------|---------|------|
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
python server.py
```

See [README.md](README.md) for full documentation.

## Known Limitations

- No automated test suite yet (smoke test available via `./scripts/deploy.sh smoke`)
- `shasta` testnet is intentionally unsupported
