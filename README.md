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
| BSC mainnet | USDT |

Production MCP endpoint:

```text
https://ainft-agent.bankofai.io/mcp
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

## Deployment

Operational deployment steps are in:

- [DEPLOYMENT.md](/Users/bobo/code/skills/ainft-merchant-agent/DEPLOYMENT.md)

## License

[MIT](/Users/bobo/code/skills/ainft-merchant-agent/LICENSE)
