# Payment Test Plan

This document covers payment-only verification for the BANK OF AI x402 recharge service.

## Build Under Test

```text
docker.io/bankofai/x402-recharge-agent:dev
docker.io/bankofai/x402-recharge-agent:2.0.0-dev.13
```

## Payment Environment

```dotenv
PUBLIC_RESOURCE_BASE_URL=https://tn-recharge.bankofai.io
X402_FACILITATOR_URL=https://tn-facilitator.bankofai.io
```

`X402_FACILITATOR_API_KEY` is optional and can be empty or omitted.

Do not inject `BANKOFAI_ENV=dev`. This test validates simultaneous mainnet and testnet payment routes.

## Expected Payment Routes

For `USDT`, the payment challenge must include:

- TRON mainnet: `tron:mainnet`
- TRON Nile testnet: `tron:nile`
- BNB Chain mainnet: `eip155:56`
- BNB Chain testnet: `eip155:97`

Expected receiver addresses:

- TRON mainnet: `TNMxHxRTFrPHuVqe4BHE59fGfDMfpLxXrb`
- TRON Nile testnet: `TNMxHxRTFrPHuVqe4BHE59fGfDMfpLxXrb`
- BNB Chain mainnet: `0x0c80ac6bcd78dfd1ab8d711c75dfe2c891f23214`
- BNB Chain testnet: `0x0c80ac6bcd78dfd1ab8d711c75dfe2c891f23214`

Expected token addresses:

- TRON mainnet USDT: `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`
- TRON Nile testnet USDT: `TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf`
- BNB Chain mainnet USDT: `0x55d398326f99059fF775485246999027B3197955`
- BNB Chain testnet USDT: `0x337610d27c682E347C9cD60BD4b3b107C9d34dDd`

## Mandatory Test Scope

Testing must include one real paid request through the TN server:

```text
https://tn-recharge.bankofai.io/x402/recharge
```

Do not use a local server for the paid test.
Do not call the facilitator directly as a replacement for the paid test.
The facilitator is only the verifier/settler behind the TN server.

## 1. Facilitator Payment Route Check

```bash
curl -sS https://tn-facilitator.bankofai.io/supported \
  | jq -r '.kinds[]? | select(.scheme=="exact") | .network'
```

Expected output includes:

```text
tron:nile
eip155:97
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
- `accepts` contains `tron:nile`
- `accepts` contains `eip155:56`
- `accepts` contains `eip155:97`
- TRON mainnet `payTo` is `TNMxHxRTFrPHuVqe4BHE59fGfDMfpLxXrb`
- TRON Nile testnet `payTo` is `TNMxHxRTFrPHuVqe4BHE59fGfDMfpLxXrb`
- BNB Chain mainnet `payTo` is `0x0c80ac6bcd78dfd1ab8d711c75dfe2c891f23214`
- BNB Chain testnet `payTo` is `0x0c80ac6bcd78dfd1ab8d711c75dfe2c891f23214`

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
- `data.x402.accepts` contains `tron:nile`
- `data.x402.accepts` contains `eip155:56`
- `data.x402.accepts` contains `eip155:97`

## 4. Required Paid Settlement Test

Run one successful paid request with a funded wallet and a valid x402 client.

Required route:

- BNB Chain testnet USDT
- Network: `eip155:97`
- Token: `0x337610d27c682E347C9cD60BD4b3b107C9d34dDd`
- Receiver: `0x0c80ac6bcd78dfd1ab8d711c75dfe2c891f23214`
- Server URL: `https://tn-recharge.bankofai.io/x402/recharge`

The test client must first request the TN server, receive HTTP `402`, sign the BSC testnet USDT payment, and retry the same TN server URL with the x402 payment header.

Expected:

- Client receives `402 Payment Required`
- Client signs a payment for `eip155:97`
- Retry request includes the x402 payment header
- Service calls facilitator `verify`
- Service calls facilitator `settle`
- Final response is successful and contains settlement details

The test is not complete until the final paid response from the TN server succeeds.

Failure conditions to capture:

- `insufficient_funds`
- `invalid_payment_signature`
- `facilitator verify failed`
- `facilitator settle failed`

If the server returns HTTP `202` with `status=payment_pending`, the payment transaction has been submitted and the tester must not retry the payment. Capture `transaction_hash`, wait for chain confirmation, and verify recharge status with the same transaction.

When a paid settlement fails, capture these response fields:

- `error`
- `failure_stage`
- `failure_reason`
- `detail`
- `message`

Also capture service logs that start with:

```text
Facilitator verify failed
Facilitator settle failed
```
