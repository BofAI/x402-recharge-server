# v2.0.1 Release Notes

**Date:** 2026-07-21

## Overview

BANK OF AI Payment Agent now exposes a single MCP recharge tool, `recharge`, and runs on the TypeScript x402 SDK.

## Highlights

**Single MCP Tool** — Agents now call `recharge(amount, token)` for all supported recharges.

**Automatic Payment** — When an agent calls `recharge`, the service returns HTTP 402 with an x402 challenge. After the agent signs and retries, the service verifies and settles on-chain via the Facilitator. Fully automatic for x402-compatible clients.

**SDK 1.0.1** — Payment handling uses the released `@bankofai/x402-core`, `@bankofai/x402-evm`, and `@bankofai/x402-tron` version `1.0.1` packages.

**Mainnet Deployment** — Runtime configuration defaults to mainnet payment routes with `X402_FACILITATOR_URL=https://facilitator.bankofai.io`.

**Canonical Networks** — TRON mainnet challenges use `tron:0x2b6653dc`; BSC mainnet challenges use `eip155:56`.

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
