# AINFT Merchant Agent

AINFT top-up merchant agent — accepts on-chain payments from AI Agents and credits AINFT accounts.

AI Agents call top-up tools via [MCP](https://modelcontextprotocol.io/). For TRC20 tokens, the service uses the [x402](https://github.com/BofAI/x402) protocol to automatically handle the challenge-sign-settle loop. For native TRX, the agent transfers on-chain and submits the txid for verification.

## Payment Flow

```
┌──────────┐        ┌───────────────────┐        ┌─────────────┐        ┌──────┐
│ AI Agent │        │ Merchant Agent    │        │ Facilitator │        │ TRON │
│ (payer)  │        │ (this service)    │        │             │        │      │
└────┬─────┘        └────────┬──────────┘        └──────┬──────┘        └──┬───┘
     │  call ainft_pay_trc20 │                          │                  │
     │ ─────────────────────>│                          │                  │
     │  402 + x402 challenge │                          │                  │
     │ <─────────────────────│                          │                  │
     │                       │                          │                  │
     │  sign & retry with    │                          │                  │
     │  PAYMENT-SIGNATURE    │                          │                  │
     │ ─────────────────────>│  verify + settle         │                  │
     │                       │ ────────────────────────>│  on-chain tx     │
     │                       │                          │ ────────────────>│
     │                       │  settlement result       │                  │
     │                       │ <────────────────────────│                  │
     │  200 + tx hash        │                          │                  │
     │ <─────────────────────│                          │                  │
```

| Method | Tool | Protocol | Description |
|--------|------|----------|-------------|
| TRC20 token | `ainft_pay_trc20` | x402 | Automatic 402 challenge → sign → settle |
| Native TRX | `ainft_pay_trx` | On-chain verify | Agent transfers TRX, then submits txid |

## Quick Start

```bash
git clone https://github.com/BofAI/ainft-merchant-agent.git
cd ainft-merchant-agent

cp .env.example .env        # Set NETWORK=nile for testing

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python server.py
```

MCP endpoint available at `http://0.0.0.0:8000/mcp`.

### Docker

```bash
cp .env.example .env
./scripts/deploy.sh up       # Build and start
./scripts/deploy.sh smoke    # Verify service is available
./scripts/deploy.sh logs     # Follow logs
./scripts/deploy.sh down     # Stop
```

## API

### Top-up Tools (MCP)

**`ainft_pay_trc20(amount, token="USDT")`** — TRC20 top-up

```bash
curl -i -X POST http://127.0.0.1:8000/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"ainft_pay_trc20","arguments":{"amount":"1","token":"USDT"}}}'
# → 402 Payment Required (with x402 challenge)
```

**`ainft_pay_trx(amount, txid="")`** — Native TRX top-up

```bash
# 1) Get transfer instructions
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"ainft_pay_trx","arguments":{"amount":"1"}}}'

# 2) After on-chain transfer, submit txid for verification
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":"2","method":"tools/call","params":{"name":"ainft_pay_trx","arguments":{"amount":"1","txid":"<TXID>"}}}'
```

### HTTP Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /mcp` | MCP streamable HTTP (primary endpoint, with x402 middleware) |
| `POST /x402/recharge` | REST x402 top-up |
| `POST /x402/trc20/recharge` | Alias for the above |

### Deprecated

- `recharge(amount, token, txid)` — Compatibility alias; use `ainft_pay_trc20` / `ainft_pay_trx` directly
- `get_balance()` — Moved to local ainft-skill

## Configuration

Copy `.env.example` to `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `NETWORK` | `mainnet` | `mainnet` or `nile` |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Listen port |
| `LOG_LEVEL` | `info` | Log level |
| `X402_FACILITATOR_URL` | `https://facilitator.bankofai.io` | x402 settlement service |
| `TRON_RPC_URL` | `https://api.trongrid.io` | TRON RPC (overrides network default) |

Network addresses, token contracts, and minimum top-up amounts are defined in [`config/networks.json`](config/networks.json).

## Supported Networks & Tokens

| Network | Chain ID | Tokens |
|---------|----------|--------|
| TRON Mainnet | `728126428` | TRX, USDT, USDD, USDC, NFT |
| TRON Nile (testnet) | `3448148188` | TRX, USDT, USDD |

## Project Structure

```
server.py                    # Entry point: top-up tools + x402 middleware + HTTP routes
src/config.py                # Config loader (.env + networks.json)
config/networks.json         # Network config (addresses, tokens, minimums)
scripts/
├── deploy.sh                # Docker deployment script
├── start_agent.sh           # Local startup script
└── register_8004.py         # ERC-8004 on-chain registration
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the production deployment guide.

## ERC-8004 Registration

On-chain agent discovery registration is independent from the runtime service. See [docs/REGISTRATION.md](docs/REGISTRATION.md).

## Related Projects

- [x402](https://github.com/BofAI/x402) — HTTP 402 payment protocol (Python & TypeScript SDKs)
- [AINFT](https://ainft.com) — AI NFT platform

## License

[MIT](LICENSE)
