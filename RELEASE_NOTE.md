# v1.1.0 Release Notes

**Date:** 2026-03-15

## Overview

BANK OF AI Payment Agent now exposes a single MCP recharge tool, `recharge`, and runs on the TypeScript x402 SDK.

## Highlights

**Single MCP Tool** — Agents now call `recharge(amount, token)` for all supported recharges.

**Automatic Payment** — When an agent calls `recharge`, the service returns HTTP 402 with an x402 challenge. After the agent signs and retries, the service verifies and settles on-chain via the Facilitator. Fully automatic for x402-compatible clients.

**Mainnet Deployment** — Runtime configuration defaults to mainnet payment routes with `X402_FACILITATOR_URL=https://facilitator-v2.bankofai.io`.

## Supported Mainnet Tokens

| Token | Network |
|-------|---------|
| USDT | TRON Mainnet |
| USDD | TRON Mainnet |
| USDT | BSC Mainnet |

## Getting Started

```bash
git clone https://github.com/BofAI/x402-recharge-server.git
cd x402-recharge-server
cp .env.example .env
npm install
npm run build
npm start
```

See [README.md](README.md) for full documentation.

## Known Limitations

- Smoke test available via `./scripts/deploy.sh smoke`
- Testnet payment routes are intentionally not advertised by the server
