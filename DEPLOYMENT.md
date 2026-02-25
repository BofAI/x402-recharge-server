# Deployment Runbook

## Prerequisites

- Docker 24+
- Docker Compose v2

## 1. Configure Environment

```bash
cp .env.example .env
```

Required runtime values:

- `NETWORK=mainnet`
- `HOST=0.0.0.0`
- `PORT=8000`
- `LOG_LEVEL=info`

Optional runtime values:

```bash
TRONGRID_API_KEY=<optional>
```

## 2. Deploy (Single Entry)

```bash
./scripts/deploy.sh up
```

## 3. Verify

```bash
./scripts/deploy.sh smoke
```

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
- Registration update fails:
  - Check `AGENT_OPERATOR_KEY` in `.env`.
  - Follow [REGISTRATION.md](docs/REGISTRATION.md).
