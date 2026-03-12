# Security Policy

## Scope

This repository handles payment verification, merchant confirmation, and ERC-8004 registration workflows.
Treat all runtime and registration credentials as sensitive.

Sensitive values include:

- `AGENT_OPERATOR_KEY`
- `AINFT_MERCHANT_KEY`
- `PINATA_JWT`
- any wallet private key or API credential used by MCP, x402, or deployment tooling

## Supported Use

The current maintained branch is `main`.

Before reporting a bug, confirm whether it affects:

- the MCP runtime service
- x402 payment challenge / settlement flow
- merchant post-topup confirmation
- ERC-8004 registration or URI updates
- Pinata / IPFS metadata publication

## Reporting a Vulnerability

Do not open a public GitHub issue for credential leaks, auth bypasses, payment settlement bugs, or chain-write vulnerabilities.

Report privately to the maintainers with:

- affected commit or branch
- reproduction steps
- impact assessment
- whether any secret, wallet, or production endpoint is exposed

If a secure disclosure channel is not yet published for this repository, contact the maintainers directly through the organization channel used for deployment access.

## Operational Guidance

- Never commit `.env` files or private keys.
- Use dedicated low-balance operator wallets.
- Keep registration keys out of Docker images.
- Prefer separate credentials for dev/testnet and production/mainnet.
- Rotate `PINATA_JWT`, merchant keys, and operator keys after any suspected exposure.
