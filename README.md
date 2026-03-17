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

## Quick Start

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

## How It Is Used

An AI agent calls:

```text
recharge(amount, token)
```

The service returns an x402 challenge. A compatible client signs the payment and retries the request. After settlement succeeds, the service returns the payment result and transaction reference.

## Registration

This service is prepared for ERC-8004 registration on:

- TRON mainnet
- BSC mainnet

Registration script:

- [scripts/register_8004.py](/Users/bobo/code/skills/ainft-merchant-agent/scripts/register_8004.py)

Registration guide:

- [docs/REGISTRATION.md](/Users/bobo/code/skills/ainft-merchant-agent/docs/REGISTRATION.md)

## Documentation

Public-facing docs should cover both the skill and the agent.

- [docs/OVERVIEW.md](/Users/bobo/code/skills/ainft-merchant-agent/docs/OVERVIEW.md)
- [docs/REGISTRATION.md](/Users/bobo/code/skills/ainft-merchant-agent/docs/REGISTRATION.md)
- [DEPLOYMENT.md](/Users/bobo/code/skills/ainft-merchant-agent/DEPLOYMENT.md)

## Deployment

Operational deployment steps are in:

- [DEPLOYMENT.md](/Users/bobo/code/skills/ainft-merchant-agent/DEPLOYMENT.md)

## License

[MIT](/Users/bobo/code/skills/ainft-merchant-agent/LICENSE)
