# BofAI Payment Agent

BofAI Payment Agent is the MCP payment service used by BofAI to receive x402-based recharges.

Its public role is simple:

- expose one MCP tool: `recharge(amount, token)`
- return x402 payment challenges
- support stablecoin recharge on supported production chains

In the full product flow, a companion skill can route end-user recharge requests to this MCP service.

This payment agent is used for BANK OF AI account recharge.
BANK OF AI product entry: [https://chat.bankofai.io/chat](https://chat.bankofai.io/chat)

## Supported Routes

Current supported payment routes:

| Network | Tokens |
|---|---|
| TRON mainnet | USDT, USDD |
| BSC mainnet | USDT only |

Production MCP endpoint:

```text
https://recharge.bankofai.io/mcp
```

## MCP Clients

**Claude Desktop / Claude Code / Cursor:**

```json
{
  "mcpServers": {
    "x402-recharge-server": {
      "url": "https://recharge.bankofai.io/mcp"
    }
  }
}
```

**Antigravity:**

```json
{
  "mcpServers": {
    "x402-recharge-server": {
      "serverUrl": "https://recharge.bankofai.io/mcp"
    }
  }
}
```

**OpenCode:**

```json
{
  "mcp": {
    "x402-recharge-server": {
      "type": "remote",
      "url": "https://recharge.bankofai.io/mcp"
    }
  }
}
```

## Quick Start

### Local

```bash
git clone https://github.com/BofAI/x402-recharge-server.git
cd x402-recharge-server
cp .env.example .env

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

Local MCP endpoint:

```text
http://127.0.0.1:8000/mcp
```

### Docker

```bash
cp .env.example .env
./scripts/deploy.sh up
./scripts/deploy.sh smoke
./scripts/deploy.sh logs
```

### Quick Check

```bash
curl -i http://127.0.0.1:8000/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":"check-402","method":"tools/call","params":{"name":"recharge","arguments":{"amount":"1","token":"USDT"}}}'
```

Expected:

- `402 Payment Required`
- `TRON mainnet` route for `USDT`
- `BSC mainnet` route for `USDT`

## How It Is Used

An AI agent calls:

```text
recharge(amount, token)
```

The service returns an x402 challenge. A compatible client signs the payment and retries the request. After settlement succeeds, the service returns the payment result and transaction reference.

## Current Agent Registration

| Chain | Network | Identity Registry | Agent ID | Status |
|---|---|---|---:|---|
| TRON | mainnet | `TFLvivMdKsk6v2GrwyD2apEr9dU1w7p7Fy` | `8` | active |
| BSC | mainnet | `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` | `56:43970` | active |

## Deployment

Operational deployment steps are in:

- [DEPLOYMENT.md](DEPLOYMENT.md)

## License

[MIT](LICENSE)
