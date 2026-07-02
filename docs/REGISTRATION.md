# ERC-8004 Registration Guide

This document is only for publishing and registering the BofAI payment agent metadata.

## Registration Scope

Prepare and register the agent on:

- TRON mainnet
- BSC mainnet

## Current Registrations

| Chain | Network | Identity Registry | Agent ID | Status |
|---|---|---|---:|---|
| TRON | mainnet | `TFLvivMdKsk6v2GrwyD2apEr9dU1w7p7Fy` | `8` | active |
| BSC | mainnet | `0x8004A169FB4a3325136EB29fA0ceB6D2e539a432` | `56:43970` | active |

This agent is used for BANK OF AI account recharge over MCP + x402.
BANK OF AI product entry: [https://chat.bankofai.io/chat](https://chat.bankofai.io/chat)

## Metadata Files

Registration metadata should be generated or prepared per chain, then hosted on HTTPS or IPFS before registration.

## Operator Keys

Supported env vars:

- `TRON_AGENT_OPERATOR_KEY`
- `BSC_AGENT_OPERATOR_KEY`
- fallback: `AGENT_OPERATOR_KEY`

## Registration Updates

The TypeScript recharge server no longer ships an on-chain registration script.
Use the BANK OF AI registration tooling to register or update agent metadata.

## Default Identity Registries

TRON mainnet:

```text
TFLvivMdKsk6v2GrwyD2apEr9dU1w7p7Fy
```

BSC mainnet:

```text
0x8004A169FB4a3325136EB29fA0ceB6D2e539a432
```

## Public Listing

On-chain registration is one part of launch. Public discoverability usually needs an additional listing/indexing step.

- After TRON registration, submit the TRON-side agent record to the target scan/indexer if that listing flow requires it.
- After BSC registration, submit the BSC-side agent record and metadata URI to the target scan/indexer.

## Notes

- The metadata endpoint currently points to `https://recharge.bankofai.io/mcp`.
- Recommended image URL: `https://cdn.bankofai.io/x8004/%E7%99%BD%E5%BA%95.jpg`
- Public brand in metadata is `BofAI`.
