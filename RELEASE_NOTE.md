# v1.1.0 Release Notes

**Date:** 2026-03-15

## Overview

BANK OF AI Payment Agent now exposes a single MCP recharge tool, `recharge`, and supports TRC20 tokens only.

## Highlights

**Single MCP Tool** — Agents now call `recharge(amount, token)` for all supported recharges.

**TRC20 Automatic Payment** — When an agent calls `recharge`, the service returns HTTP 402 with an x402 challenge. After the agent signs and retries, the service verifies and settles on-chain via the Facilitator. Fully automatic for x402-compatible clients.

**Environment-Based Deployment** — Runtime configuration now uses `BANKOFAI_ENV=dev|prod`. `dev` is for local verification, and `prod` is for TRON mainnet production recharge.

## Supported Mainnet Tokens

| Token | Network |
|-------|---------|
| USDT | TRON Mainnet |
| USDD | TRON Mainnet |
| USDC | TRON Mainnet |
| NFT | TRON Mainnet |

## Getting Started

```bash
git clone https://github.com/BofAI/x402-recharge-server.git
cd x402-recharge-server
cp .env.example .env
pip install -r requirements.txt
python server.py
```

See [README.md](README.md) for full documentation.

## Known Limitations

- No automated test suite yet (smoke test available via `./scripts/deploy.sh smoke`)
- `shasta` testnet is intentionally unsupported
