# Deployment Runbook

## Prerequisites

- Docker 24+
- Docker Compose v2
- Verified payment target network: `nile` (recommended for testing)

## 1. Configure Environment

```bash
cp .env.example .env
```

Required runtime values:

- `NETWORK=mainnet|nile` (for x402 testing, use `nile`)
- `HOST=0.0.0.0`
- `PORT=8000`
- `LOG_LEVEL=info`

## 2. Deploy (Single Entry)

```bash
./scripts/deploy.sh up
```

## 3. Verify

```bash
./scripts/deploy.sh smoke
```

Basic x402 challenge check:

```bash
curl -i -X POST 'http://127.0.0.1:8000/mcp' \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":"check-402","method":"tools/call","params":{"name":"recharge","arguments":{"amount":"1","token":"USDT"}}}'
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
  - Confirm `NETWORK=nile`.
  - Confirm payer wallet has Nile USDT + TRX gas.
  - Confirm facilitator URL is reachable and unchanged.
- Registration update fails:
  - Check `AGENT_OPERATOR_KEY` in `.env`.
  - Follow [REGISTRATION.md](docs/REGISTRATION.md).
