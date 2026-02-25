# AINFT Merchant Agent

MCP service for AINFT recharge challenge generation on TRON mainnet.

## Features

- `recharge(amount, token)`:
  - returns an x402 challenge payload
  - includes `status_code=402`
  - includes `headers.PAYMENT-REQUIRED`
  - uses fixed AINFT mainnet deposit address as `payTo`
- `get_balance(account_id)`:
  - returns AINFT balance query entry URLs

## Runtime Endpoints

- MCP streamable-http: `http://0.0.0.0:8000/mcp`

## Local Run

```bash
cd /Users/bobo/code/skills/ainft-merchant-agent
pip install -r requirements.txt
python server.py
```

## Docker Deployment

```bash
cd /Users/bobo/code/skills/ainft-merchant-agent
./scripts/deploy.sh up
./scripts/deploy.sh smoke
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment commands.

## Configuration

Set values in `.env`:

- `NETWORK=mainnet`
- `HOST=0.0.0.0`
- `PORT=8000`
- `LOG_LEVEL=info`

Network addresses and token minimums are loaded from `config/networks.json`.


## Registration (Optional, Separate Step)

Service runtime and chain registration are separate concerns.

Start service:

```bash
./run.sh
```

Register or update on ERC-8004:

```bash
python scripts/register_8004.py --uri https://your-public-host/ainft-merchant-registration-v1.json
```

```bash
python scripts/register_8004.py --agent-id 103 --uri ipfs://<cid>/registration.json
```

See [REGISTRATION.md](docs/REGISTRATION.md) for full registration workflow and rollback.
