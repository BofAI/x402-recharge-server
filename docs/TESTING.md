# Payment Test Plan

This document covers payment-only verification for the BANK OF AI x402 recharge service.

## Build Under Test

```text
docker.io/bankofai/x402-recharge-agent:dev
docker.io/bankofai/x402-recharge-agent:2.0.0-dev.6
```

Digest:

```text
sha256:9bf4da10fc6265237ff15a3f3ee66e62c22b329a2132bc46b58cada26d329086
```

## Payment Environment

```dotenv
PUBLIC_RESOURCE_BASE_URL=https://tn-recharge.bankofai.io
X402_FACILITATOR_URL=https://facilitator-v2.bankofai.io
```

`X402_FACILITATOR_API_KEY` is optional and can be empty or omitted.

Do not inject `BANKOFAI_ENV=dev`. This test validates mainnet payment routes.

## Expected Payment Routes

For `USDT`, the payment challenge must include:

- TRON mainnet: `tron:mainnet`
- BNB Chain mainnet: `eip155:56`

Expected receiver addresses:

- TRON: `TNMxHxRTFrPHuVqe4BHE59fGfDMfpLxXrb`
- BNB Chain: `0x0c80ac6bcd78dfd1ab8d711c75dfe2c891f23214`

## 1. Facilitator Payment Route Check

```bash
curl -sS https://facilitator-v2.bankofai.io/supported \
  | jq -r '.kinds[]? | select(.scheme=="exact") | .network'
```

Expected output includes:

```text
tron:mainnet
eip155:56
```

## 2. HTTP x402 Payment Challenge

```bash
curl -i https://tn-recharge.bankofai.io/x402/recharge \
  -H 'content-type: application/json' \
  -d '{"amount":"1","token":"USDT"}'
```

Expected:

- HTTP `402`
- Header `payment-required` exists
- Body contains `"error":"Payment Required"`
- `resource.url` is `https://tn-recharge.bankofai.io/x402/recharge`
- `accepts` contains `tron:mainnet`
- `accepts` contains `eip155:56`
- TRON `payTo` is `TNMxHxRTFrPHuVqe4BHE59fGfDMfpLxXrb`
- BNB Chain `payTo` is `0x0c80ac6bcd78dfd1ab8d711c75dfe2c891f23214`

## 3. MCP Recharge Payment Challenge

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

## 4. Optional Paid Settlement Test

Run this only with a funded wallet and a valid x402 client.

Expected:

- Client receives `402 Payment Required`
- Client signs a payment for one accepted route
- Retry request includes the x402 payment header
- Service calls facilitator `verify`
- Service calls facilitator `settle`
- Final response is successful and contains settlement details

Failure conditions to capture:

- `insufficient_funds`
- `invalid_payment_signature`
- `facilitator verify failed`
- `facilitator settle failed`
