# ERC-8004 Registration Guide

This document is only for on-chain discovery registration.
It is independent from runtime service startup.

## Prerequisites

- Start from `.env.registration.example` if you want a minimal registration-only env template.
- Running MCP service is optional, but recommended for validation.
- `AGENT_OPERATOR_KEY` is set in `.env`.
- A public metadata URI can be hosted on HTTPS or IPFS.
- Optional but recommended: `PINATA_JWT` is set in `.env` so the repo can upload metadata to Pinata directly.

## 1. Render Bootstrap Registration JSON

Render a bootstrap file with no `agentId` yet:

```bash
cd ainft-merchant-agent
python3 scripts/render_registration.py \
  --mode bootstrap \
  --output docs/ainft-merchant-registration.bootstrap.json
```

Then upload that JSON file to IPFS or HTTPS.

With Pinata:

```bash
cd ainft-merchant-agent
python3 scripts/upload_to_pinata.py docs/ainft-merchant-registration.bootstrap.json
```

Or if you want only the URI for shell piping:

```bash
cd ainft-merchant-agent
python3 scripts/upload_to_pinata.py docs/ainft-merchant-registration.bootstrap.json --format uri
```

Example output URI:

- `https://your-domain/ainft-merchant-registration-v1.json`
- `ipfs://<cid>`

The bootstrap file should contain your public MCP endpoint (`https://.../mcp`) and tool list.

## 2. First Registration

```bash
cd ainft-merchant-agent
python3 scripts/register_8004.py --uri ipfs://<bootstrap-cid>
```

If you used the Pinata helper above, the URI will usually be `ipfs://<bootstrap-cid>` instead of `ipfs://<bootstrap-cid>/registration.json`.

Output includes:

- `tx_hash`
- `agent_id`
- `agent_uri`

Save `agent_id` for future updates.

If you want, write it back into `.env` as `ERC8004_AGENT_ID=<agent_id>`.

## 3. Render Final Registration JSON

Now render the final registration file with the real `agent_id` embedded:

```bash
cd ainft-merchant-agent
python3 scripts/render_registration.py \
  --mode final \
  --agent-id <agent_id> \
  --output docs/ainft-merchant-registration.final.json
```

Upload that file to IPFS or HTTPS and keep the new URI.

With Pinata:

```bash
cd ainft-merchant-agent
python3 scripts/upload_to_pinata.py docs/ainft-merchant-registration.final.json
```

## 4. Update Existing Agent URI

```bash
cd ainft-merchant-agent
python3 scripts/update_8004.py --agent-id <agent_id> --uri ipfs://<final-cid>
```

If `ERC8004_AGENT_ID` is already set in `.env`, `--agent-id` can be omitted.

## 5. Rollback

If a bad metadata URI was published, immediately update again with the last known good URI:

```bash
python3 scripts/update_8004.py --agent-id <agent_id> --uri <previous_good_uri>
```

## Notes

- Runtime service never needs `AGENT_OPERATOR_KEY`.
- Keep operator private keys out of Docker image and source control.
- `upload_to_pinata.py` uploads a single JSON file and returns `ipfs://<cid>`.
- If you manually upload a folder instead of a single file, `ipfs://<cid>/registration.json` is also valid.
- Registration helpers currently target TRON `mainnet` and `nile` metadata layouts.
- `register_8004.py` still accepts TRON `shasta` RPC settings for raw chain write operations, but the service itself is not documented as supporting shasta runtime.
