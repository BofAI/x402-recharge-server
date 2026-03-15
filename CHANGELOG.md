# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-03-15

### Changed

- Consolidated MCP top-up interface to a single `recharge(amount, token)` tool
- Restricted merchant-agent top-ups to supported TRC20 tokens only
- Updated MCP middleware and smoke checks to target `recharge` only
- Switched deployment configuration to `AINFT_ENV=dev|prod` with `dev -> Nile` and `prod -> Mainnet`

### Removed

- Native TRX top-up flow (`ainft_pay_trx`)
- Alternate MCP top-up tool name (`ainft_pay_trc20`)
- Merchant-agent `get_balance` MCP tool

## [1.0.0] - 2026-03-06

Initial release of AINFT Merchant Agent.

### Added

- TRC20 top-up (`ainft_pay_trc20`): automatic x402 402-challenge → sign → on-chain settlement
- Native TRX top-up (`ainft_pay_trx`): on-chain transfer + txid verification
- x402 middleware (`MCPRecharge402Middleware`): intercepts MCP calls and injects HTTP 402 flow
- REST top-up endpoints: `/x402/recharge`, `/x402/trc20/recharge`
- Multi-network support: mainnet and Nile testnet (driven by `config/networks.json`)
- Token support: USDT, USDD, USDC, NFT (mainnet); USDT, USDD (Nile)
- ERC-8004 on-chain registration script (`scripts/register_8004.py`)
- Docker deployment + one-command ops script (`scripts/deploy.sh`)
