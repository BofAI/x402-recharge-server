# BofAI Payment Agent

BofAI Payment Agent is the MCP payment service used by BofAI to receive x402-based top-ups.

Its public role is simple:

- expose one MCP tool: `recharge(amount, token)`
- return x402 payment challenges
- support stablecoin top-up on supported production chains

## Business Scope

Current supported payment routes:

| Network | Tokens |
|---|---|
| TRON mainnet | USDT, USDD |
| BSC mainnet | USDT only |

## Components

This offering has two public-facing pieces:

- `Skill`: the user-facing skill that routes top-up requests and local account queries
  - [SKILL.md](/Users/bobo/code/skills/skills/ainft-skill/SKILL.md)
- `Agent`: the MCP payment service in this repository
  - [README.md](/Users/bobo/code/skills/ainft-merchant-agent/README.md)

Production MCP endpoint:

```text
https://ainft-agent.bankofai.io/mcp
```

## MCP Clients

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

### Local

```bash
git clone https://github.com/BofAI/ainft-merchant-agent.git
cd ainft-merchant-agent
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

## Documentation

Public-facing docs should cover both the skill and the agent.

- [DEPLOYMENT.md](/Users/bobo/code/skills/ainft-merchant-agent/DEPLOYMENT.md)

## Deployment

Operational deployment steps are in:

- [DEPLOYMENT.md](/Users/bobo/code/skills/ainft-merchant-agent/DEPLOYMENT.md)

## License

[MIT](/Users/bobo/code/skills/ainft-merchant-agent/LICENSE)
