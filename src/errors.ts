export type PaymentFailureStage = "decode" | "verify" | "settle" | "duplicate" | "unknown";

export class PaymentFlowError extends Error {
  readonly stage: PaymentFailureStage;
  readonly reason: string;
  readonly cause?: unknown;

  constructor(stage: PaymentFailureStage, reason: string, message?: string, cause?: unknown) {
    super(message ?? reason);
    this.name = "PaymentFlowError";
    this.stage = stage;
    this.reason = reason;
    this.cause = cause;
  }
}

export function paymentFlowErrorDetails(error: unknown): { stage: PaymentFailureStage; reason: string; raw: string } {
  if (error instanceof PaymentFlowError) {
    return {
      stage: error.stage,
      reason: error.reason,
      raw: error.message
    };
  }
  const raw = error instanceof Error ? error.message : String(error || "unknown");
  return { stage: "unknown", reason: "invalid_payment", raw };
}

export function publicPaymentFailure(error: unknown): Record<string, unknown> {
  const details = paymentFlowErrorDetails(error);
  const reason = details.stage === "verify" || details.stage === "decode"
    ? "invalid_payment_signature"
    : details.stage === "settle"
      ? "payment_settlement_failed"
      : details.stage === "duplicate"
        ? "payment_already_processing"
        : "invalid_payment";
  return {
    error: "payment_verification_failed",
    failure_stage: details.stage,
    failure_reason: reason,
    detail: reason,
    message: details.stage === "settle"
      ? "Payment settlement failed. Do not retry automatically; check transaction status before creating a new payment."
      : details.stage === "duplicate"
        ? "Payment is already being processed. Wait for the existing attempt to finish before retrying."
        : "Provided payment is invalid. Create a new payment and retry."
  };
}
