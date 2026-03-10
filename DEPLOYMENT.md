# Deployment Runbook

## Prerequisites

- Docker 24+
- Docker Compose v2
- Be explicit about whether the current external environment is `ainft dev` or `ainft prod`

## Environment Model

Only two external environments should be used:

- `ainft dev`
- `ainft prod`

Where:

- `dev` usually points to `chat-dev`
- `prod` points to the production domain
- `NETWORK=mainnet|nile|bsc|bsc-testnet` is only an internal service runtime parameter
- If recharge addresses are production-chain addresses, local dev should still prefer `NETWORK=mainnet` / `NETWORK=bsc`

## 1. Configure Environment

```bash
cp .env.example .env
```

Required runtime values:

- `AINFT_ENV=dev|prod`
- `NETWORK=mainnet|nile|bsc|bsc-testnet`
- `HOST=0.0.0.0`
- `PORT=8000`
- `LOG_LEVEL=info`
- `AINFT_MERCHANT_ID=<merchant id>` (recommended; the service will call the post-payment confirmation API automatically)
- `AINFT_MERCHANT_KEY=<merchant key>`

## 2. Deploy (Single Entry)

```bash
./scripts/deploy.sh up
```

Examples:

```bash
AINFT_ENV=dev NETWORK=mainnet ./scripts/deploy.sh up
```

```bash
AINFT_ENV=prod NETWORK=mainnet ./scripts/deploy.sh up
```

## 3. Verify

```bash
./scripts/deploy.sh smoke
```

Basic x402 challenge check:

```bash
curl -i -X POST 'http://127.0.0.1:8000/mcp' \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":"check-402","method":"tools/call","params":{"name":"ainft_pay_trc20","arguments":{"amount":"1","token":"USDT"}}}'
```

Expected: `HTTP/1.1 402 Payment Required`.

## 4. Logs and Restart

```bash
./scripts/deploy.sh logs
```

```bash
./scripts/deploy.sh restart
```

## 5. Stop

```bash
./scripts/deploy.sh down
```

## Production Notes

- Expose only MCP endpoint (`/mcp`) behind HTTPS reverse proxy (Nginx/Caddy/Traefik).
- Host registration metadata separately (public HTTPS URL or IPFS URL), then register/update URI on-chain.
- Do not expose private keys in image or repository.

## Troubleshooting

- Smoke test fails:
  - Run `./scripts/deploy.sh status` and confirm container is `Up`.
  - Run `./scripts/deploy.sh logs` and check startup errors.
  - Verify local port mapping `8000:8000` is not occupied by another process.
- MCP client cannot connect:
  - Confirm reverse proxy forwards `/mcp` and supports streaming responses.
  - Confirm TLS certificate is valid on public endpoint.
- x402 payment does not complete:
- Confirm the selected chain is correct. For local dev, use `NETWORK=mainnet` when recharge addresses are production-chain addresses.
  - `ainft dev` does not mean testnet; if the business recharge addresses live on mainnet, the service should use mainnet chain configuration.
  - Confirm payer wallet has the required token and native gas on the selected chain.
  - Confirm facilitator URL is reachable and unchanged.
- BSC testnet topup confirmation is skipped:
  - This is expected with current AINFT merchant API behavior.
  - `eip155:97` currently returns `unsupported_chain` from the confirmation endpoint.
- Registration update fails:
  - Check `AGENT_OPERATOR_KEY` in `.env`.
  - Follow [REGISTRATION.md](docs/REGISTRATION.md).
