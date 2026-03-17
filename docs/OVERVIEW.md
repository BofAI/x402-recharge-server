# BofAI Payments Overview

This page is the public-facing overview for the BofAI payment capability.

## What Users See

Users mainly interact with the `skill`.

The skill is responsible for:

- turning natural-language top-up requests into MCP calls
- handling local account queries
- routing payment requests to the payment agent

Skill reference:

- [AINFT skill](/Users/bobo/code/skills/skills/ainft-skill/SKILL.md)

## What Integrators See

Integrators mainly connect to the `agent`.

The agent is responsible for:

- exposing the remote MCP endpoint
- returning x402 payment challenges
- supporting the approved payment routes

Current production routes:

- TRON mainnet: `USDT`, `USDD`
- BSC mainnet: `USDT` only

Agent entry points:

- MCP: `https://ainft-agent.bankofai.io/mcp`
- Website: `https://www.bankofai.io/`
- Chat: `https://chat.bankofai.io/chat`

## Public Launch Checklist

Before public launch, make sure all of the following are done:

- README is updated and aligned with production scope
- skill documentation is published
- agent documentation is published
- ERC-8004 registration is completed on TRON mainnet
- ERC-8004 registration is completed on BSC mainnet
- the BSC-side agent record is also submitted to the relevant scan/indexer page
- the TRON-side agent record is submitted to the relevant scan/indexer page if required by the listing process

## Related Docs

- [README.md](/Users/bobo/code/skills/ainft-merchant-agent/README.md)
- [REGISTRATION.md](/Users/bobo/code/skills/ainft-merchant-agent/docs/REGISTRATION.md)
- [DEPLOYMENT.md](/Users/bobo/code/skills/ainft-merchant-agent/DEPLOYMENT.md)
