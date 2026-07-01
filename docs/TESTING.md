# Test Plan

This document is for QA/OP verification of the BANK OF AI x402 recharge MCP service.

## Build Under Test

Image:

```text
docker.io/bankofai/x402-recharge-agent:dev
docker.io/bankofai/x402-recharge-agent:2.0.0-dev.6
```

Digest:

```text
sha256:9bf4da10fc6265237ff15a3f3ee66e62c22b329a2132bc46b58cada26d329086
```

Commit:

```text
6ca331e1d7239dada71e19b9487022f06c6658b7
```

## Environment

Test domain:

```text
https://tn-recharge.bankofai.io
```

Required environment variables:

```dotenv
PUBLIC_RESOURCE_BASE_URL=https://tn-recharge.bankofai.io
X402_FACILITATOR_URL=https://facilitator-v2.bankofai.io
```

Optional environment variable:

```dotenv
X402_FACILITATOR_API_KEY=
```

Do not inject `BANKOFAI_ENV=dev` for this test. The service defaults to mainnet routes.

## Scope

Supported routes expected in the x402 challenge:

- TRON mainnet: `USDT`, `USDD`
- BNB Chain mainnet: `USDT`

For the `USDT` smoke test, the challenge must include:

- `tron:mainnet`
- `eip155:56`

## Smoke Tests

### Health

```bash
curl -i https://tn-recharge.bankofai.io/health
```

Expected:

- HTTP `200`
- Body contains `"status":"ok"`
- Body contains `"service":"x402-recharge-server"`

### MCP Tool List

```bash
curl -i https://tn-recharge.bankofai.io/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Expected:

- HTTP `200`
- Response contains tool name `recharge`

### x402 Recharge Challenge

```bash
curl -i https://tn-recharge.bankofai.io/x402/recharge \
  -H 'content-type: application/json' \
  -d '{"amount":"1","token":"USDT"}'
```

Expected:

- HTTP `402`
- Header `payment-required` exists
- Body contains `"error":"Payment Required"`
- Body contains `"resource":{"url":"https://tn-recharge.bankofai.io/x402/recharge"`
- Body contains `"network":"tron:mainnet"`
- Body contains `"network":"eip155:56"`
- TRON `payTo` is `TNMxHxRTFrPHuVqe4BHE59fGfDMfpLxXrb`
- EVM `payTo` is `0x0c80ac6bcd78dfd1ab8d711c75dfe2c891f23214`

### MCP Recharge Challenge

```bash
curl -i https://tn-recharge.bankofai.io/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":"check-402","method":"tools/call","params":{"name":"recharge","arguments":{"amount":"1","token":"USDT"}}}'
```

Expected:

- HTTP `402`
- Header `payment-required` exists
- JSON-RPC error code is `-32002`
- Error message is `Payment Required`
- `data.x402.accepts` contains `tron:mainnet`
- `data.x402.accepts` contains `eip155:56`

## Facilitator Check

```bash
curl -sS https://facilitator-v2.bankofai.io/supported \
  | jq -r '.kinds[]? | select(.scheme=="exact") | .network'
```

Expected:

```text
tron:nile
tron:mainnet
eip155:97
eip155:56
```

## Known Non-Blocking Warning

The Docker CI currently reports a GitHub Actions warning about Node.js 20 deprecation in third-party actions. The Docker build and push completed successfully.
