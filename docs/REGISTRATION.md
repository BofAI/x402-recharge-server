# ERC-8004 Registration Guide

This guide covers on-chain discovery registration only. It is separate from starting the merchant MCP service.

## Overview

The recommended registration flow has two phases:

1. Publish bootstrap metadata and create a new agent on-chain.
2. Publish final metadata with the real `agent_id`, then update the existing agent URI.

This split keeps first registration simple and gives you a clean final metadata document after the chain-assigned identifier is known.

## What You Need

- Python `>=3.11`
- a virtual environment
- runtime dependencies from `requirements.txt`
- the ERC-8004 SDK
- `AGENT_OPERATOR_KEY` in `.env`
- a public metadata URI hosted on IPFS or HTTPS
- optional but recommended: `PINATA_JWT` in `.env` for direct Pinata uploads

If you want a minimal registration-only template, start from `.env.registration.example`.

Example setup:

```bash
cd ainft-merchant-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install git+https://github.com/BofAI/8004-sdk.git#subdirectory=python
```

## Required Environment Variables

At minimum, make sure `.env` includes:

- `NETWORK=mainnet|nile`
- `AGENT_OPERATOR_KEY=<operator private key>`
- `AINFT_PUBLIC_MCP_ENDPOINT=https://your-domain/mcp`

Optional but common:

- `PINATA_JWT=<pinata jwt>`
- `AINFT_WEB_URL=https://chat.ainft.com`
- `ERC8004_AGENT_ID=<existing agent id for updates>`

## Step 1: Render Bootstrap Metadata

Render bootstrap metadata without an embedded `agent_id`:

```bash
cd ainft-merchant-agent
python3 scripts/render_registration.py \
  --mode bootstrap \
  --output docs/ainft-merchant-registration.bootstrap.json
```

The bootstrap JSON should already contain:

- the public MCP endpoint
- the published tool list
- trust and active status fields
- `image` / icon URL
- `tags`
- MCP payment metadata with `paymentProtocol: "x402"`

Optional overrides:

```bash
export AINFT_REGISTRATION_IMAGE="ipfs://<cid>/logo.png"
export AINFT_REGISTRATION_TAGS="ainft,mcp,x402,tron,bsc,payments"
```

## Step 2: Upload Bootstrap Metadata

Upload the bootstrap JSON to IPFS or HTTPS.

Pinata example:

```bash
cd ainft-merchant-agent
python3 scripts/upload_to_pinata.py docs/ainft-merchant-registration.bootstrap.json
```

If you only want the URI:

```bash
cd ainft-merchant-agent
python3 scripts/upload_to_pinata.py docs/ainft-merchant-registration.bootstrap.json --format uri
```

Typical output:

- `ipfs://<cid>`
- `https://your-domain/ainft-merchant-registration-bootstrap.json`

## Step 3: Register the Agent

Use the bootstrap URI to create a new on-chain agent:

```bash
cd ainft-merchant-agent
python3 scripts/register_8004.py --uri ipfs://<bootstrap-cid>
```

Expected output includes:

- `tx_hash`
- `agent_id`
- `agent_uri`

Save the returned `agent_id`. You will need it for all later updates. It is also reasonable to write it back into `.env` as `ERC8004_AGENT_ID=<agent_id>`.

## Step 4: Render Final Metadata

Once you have the real `agent_id`, render the final metadata:

```bash
cd ainft-merchant-agent
python3 scripts/render_registration.py \
  --mode final \
  --agent-id <agent_id> \
  --output docs/ainft-merchant-registration.final.json
```

This final document is the version you should keep as the canonical public registration payload.

## Step 5: Upload Final Metadata

Upload the final JSON and keep the new URI.

Pinata example:

```bash
cd ainft-merchant-agent
python3 scripts/upload_to_pinata.py docs/ainft-merchant-registration.final.json
```

## Step 6: Update the Existing Agent URI

Point the existing agent to the final metadata:

```bash
cd ainft-merchant-agent
python3 scripts/update_8004.py --agent-id <agent_id> --uri ipfs://<final-cid>
```

If `ERC8004_AGENT_ID` already exists in `.env`, `--agent-id` can be omitted.

## Rollback

If you publish a bad metadata URI, immediately update the agent back to the last known good URI:

```bash
python3 scripts/update_8004.py --agent-id <agent_id> --uri <previous_good_uri>
```

## Operational Notes

- Runtime startup never needs `AGENT_OPERATOR_KEY`.
- Keep operator keys and Pinata credentials out of Docker images and source control.
- `upload_to_pinata.py` uploads a single JSON file and returns `ipfs://<cid>`.
- If you manually upload a folder instead of a single file, `ipfs://<cid>/registration.json` is also valid.
- Current registration helpers target the TRON registration flow used by this repository.
- `register_8004.py` can still accept `shasta` RPC settings for raw chain calls, but this repository is not documented as a shasta runtime deployment target.
