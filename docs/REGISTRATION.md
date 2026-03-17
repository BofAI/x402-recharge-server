# ERC-8004 Registration Guide

This document is only for publishing and registering the BofAI payment agent metadata.

## Registration Scope

Prepare and register the agent on:

- TRON mainnet
- BSC mainnet

## Metadata Files

Registration metadata should be generated or prepared per chain, then hosted on HTTPS or IPFS before registration.

## Operator Keys

Supported env vars:

- `TRON_AGENT_OPERATOR_KEY`
- `BSC_AGENT_OPERATOR_KEY`
- fallback: `AGENT_OPERATOR_KEY`

## Register On TRON Mainnet

```bash
python scripts/register_8004.py \
  --chain tron \
  --network mainnet \
  --uri ipfs://<tron-cid>
```

## Register On BSC Mainnet

```bash
python scripts/register_8004.py \
  --chain bsc \
  --network eip155:56 \
  --uri ipfs://<bsc-cid>
```

## Update Existing Agent URI

TRON:

```bash
python scripts/register_8004.py \
  --chain tron \
  --network mainnet \
  --agent-id <tron_agent_id> \
  --uri ipfs://<new-tron-cid>
```

BSC:

```bash
python scripts/register_8004.py \
  --chain bsc \
  --network eip155:56 \
  --agent-id <bsc_agent_id> \
  --uri ipfs://<new-bsc-cid>
```

## Default Identity Registries

TRON mainnet:

```text
TFLvivMdKsk6v2GrwyD2apEr9dU1w7p7Fy
```

BSC mainnet:

```text
0x8004A169FB4a3325136EB29fA0ceB6D2e539a432
```

## Notes

- The metadata endpoint currently points to `https://ainft-agent.bankofai.io/mcp`.
- Public brand in metadata is `BofAI`.
