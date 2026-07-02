import assert from "node:assert/strict";
import test from "node:test";
import { PaymentFlowError, publicPaymentFailure } from "../src/errors.js";

test("public payment failure masks verify details", () => {
  const error = new PaymentFlowError("verify", "upstream stack trace", "internal facilitator message");

  assert.deepEqual(publicPaymentFailure(error), {
    error: "payment_verification_failed",
    failure_stage: "verify",
    failure_reason: "invalid_payment_signature",
    detail: "invalid_payment_signature",
    message: "Provided payment is invalid. Create a new payment and retry."
  });
});

test("public payment failure tells clients not to auto retry settlement", () => {
  const error = new PaymentFlowError("settle", "invalid_transaction_state");
  const payload = publicPaymentFailure(error);

  assert.equal(payload.failure_stage, "settle");
  assert.equal(payload.failure_reason, "payment_settlement_failed");
  assert.match(String(payload.message), /Do not retry automatically/);
});
