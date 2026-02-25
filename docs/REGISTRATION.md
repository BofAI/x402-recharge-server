# ERC-8004 Registration Guide

This document is only for on-chain discovery registration.
It is independent from runtime service startup.

## Prerequisites

- Running MCP service is optional, but recommended for validation.
- `AGENT_OPERATOR_KEY` is set in `.env`.
- A public metadata URI is ready (HTTPS or IPFS).

## 1. Prepare Registration Metadata

Host a registration JSON file outside this runtime service, for example:

- `https://your-domain/ainft-merchant-registration-v1.json`
- `ipfs://<cid>/registration.json`

The metadata should contain your MCP endpoint (`https://.../mcp`) and tool list.

## 2. Register New Agent

```bash
cd /Users/bobo/code/skills/ainft-merchant-agent
python scripts/register_8004.py --uri https://your-domain/ainft-merchant-registration-v1.json
```

Output includes:

- `tx_hash`
- `agent_id`
- `agent_uri`

Save `agent_id` for future updates.

## 3. Update Existing Agent URI

```bash
cd /Users/bobo/code/skills/ainft-merchant-agent
python scripts/register_8004.py --agent-id <agent_id> --uri ipfs://<new-cid>/registration.json
```

## 4. Rollback

If a bad metadata URI was published, immediately update again with the last known good URI:

```bash
python scripts/register_8004.py --agent-id <agent_id> --uri <previous_good_uri>
```

## Notes

- Runtime service never needs `AGENT_OPERATOR_KEY`.
- Keep operator private keys out of Docker image and source control.
- Registration network is TRON mainnet in current script.
