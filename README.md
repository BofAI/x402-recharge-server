# AINFT Merchant Agent

AINFT top-up merchant agent — accepts TRC20 on-chain payments from AI Agents and credits AINFT accounts.

AI Agents call the recharge tool via [MCP](https://modelcontextprotocol.io/). The service uses the [x402](https://github.com/BofAI/x402) protocol to automatically handle the challenge-sign-settle loop for supported TRC20 tokens.

## Payment Flow

```
┌──────────┐        ┌───────────────────┐        ┌─────────────┐        ┌──────┐
│ AI Agent │        │ Merchant Agent    │        │ Facilitator │        │ TRON │
│ (payer)  │        │ (this service)    │        │             │        │      │
└────┬─────┘        └────────┬──────────┘        └──────┬──────┘        └──┬───┘
     │    call recharge      │                          │                  │
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
| TRC20 token | `recharge` | x402 | Automatic 402 challenge → sign → settle |

## MCP Server

Production endpoint:

```
https://ainft-agent.bankofai.io/mcp
```

### Connect from AI Agents

**Claude Desktop / Claude Code / Cursor:**

```json
{
  "mcpServers": {
    "ainft-merchant-agent": {
      "url": "https://ainft-agent.bankofai.io/mcp"
    }
  }
}
```

**Antigravity:**

```json
{
  "mcpServers": {
    "ainft-merchant-agent": {
      "serverUrl": "https://ainft-agent.bankofai.io/mcp"
    }
  }
}
```

**OpenCode:**

```json
{
  "mcp": {
    "ainft-merchant-agent": {
      "type": "remote",
      "url": "https://ainft-agent.bankofai.io/mcp"
    }
  }
}
```

## Quick Start

```bash
git clone https://github.com/BofAI/ainft-merchant-agent.git
cd ainft-merchant-agent

cp .env.example .env        # Defaults to AINFT_ENV=dev for Nile x402 testing

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python server.py
```

Local endpoint: `http://0.0.0.0:8000/mcp`.

### Docker

```bash
cp .env.example .env
./scripts/deploy.sh up       # Build and start
./scripts/deploy.sh smoke    # Verify service is available
./scripts/deploy.sh logs     # Follow logs
./scripts/deploy.sh down     # Stop
```

For production recharge on TRON mainnet, change `.env` before deploy:

```dotenv
AINFT_ENV=prod
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
```

The service will then load the mainnet deposit address and TRC20 token contracts from [`config/networks.json`](config/networks.json).

## API

### Top-up Tool (MCP)

**`recharge(amount, token="USDT")`** — TRC20 top-up

```bash
curl -i -X POST http://127.0.0.1:8000/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"recharge","arguments":{"amount":"1","token":"USDT"}}}'
# → 402 Payment Required (with x402 challenge)
```

### HTTP Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /mcp` | MCP streamable HTTP (primary endpoint, with x402 middleware) |
| `POST /x402/recharge` | REST x402 top-up |
| `POST /x402/trc20/recharge` | Alias for the above |

### Deprecated

- None. Use `recharge(amount, token)` for all supported top-ups.

## Configuration

Copy `.env.example` to `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `AINFT_ENV` | `dev` | `dev` uses Nile, `prod` uses TRON mainnet |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Listen port |
| `LOG_LEVEL` | `info` | Log level |
| `X402_FACILITATOR_URL` | `https://facilitator.bankofai.io` | x402 settlement service |

Network addresses, token contracts, and minimum top-up amounts are defined in [`config/networks.json`](config/networks.json).

## Supported Networks & Tokens

| Network | Chain ID | Tokens |
|---------|----------|--------|
| TRON Nile (testnet) | `3448148188` | USDT, USDD |
| TRON Mainnet | `728126428` | USDT, USDD, USDC, NFT |

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
