import type { PaymentRequired } from "@bankofai/x402-core/types";
import { buildPendingPayload, buildSuccessPayload, queryBalance, queryRechargeStatus } from "./bankofai.js";
import { PaymentFlowError, publicPaymentFailure } from "./errors.js";
import {
  buildRechargeChallenge,
  DEFAULT_TRC20_TOKEN,
  isSettlementPendingError,
  normalizeToken,
  settleWithFacilitator
} from "./payments.js";

export { DEFAULT_TRC20_TOKEN, publicPaymentFailure };

export type RechargeInput = {
  amount: string;
  token?: string;
  paymentSignature?: string;
  resourceUrl: string;
};

export type RechargeChallenge = {
  tokenSymbol: string;
  challenge: PaymentRequired;
};

export async function createRechargeChallenge(input: Omit<RechargeInput, "paymentSignature">): Promise<RechargeChallenge> {
  const tokenSymbol = normalizeToken(input.token ?? DEFAULT_TRC20_TOKEN);
  return {
    tokenSymbol,
    challenge: await buildRechargeChallenge(input.amount, tokenSymbol, input.resourceUrl)
  };
}

export async function settleRecharge(input: Required<RechargeInput>): Promise<Record<string, unknown>> {
  const { tokenSymbol, challenge } = await createRechargeChallenge(input);
  try {
    const { settlement, requirements, walletAddress } = await settleWithFacilitator(input.paymentSignature, challenge);
    const txHash = String(settlement.transaction ?? "");
    const bankofaiRecharge = await queryRechargeStatus(txHash, String(requirements.network));
    const bankofaiBalance = await queryBalance(walletAddress, String(requirements.network));
    return buildSuccessPayload({
      txHash,
      token: tokenSymbol,
      amount: input.amount,
      settlement,
      mode: "trc20_x402",
      requirements,
      bankofaiRecharge,
      bankofaiBalance
    });
  } catch (error) {
    if (!isSettlementPendingError(error)) {
      throw error;
    }
    const txHash = String(error.settlement.transaction ?? "");
    const bankofaiRecharge = await queryRechargeStatus(txHash, String(error.requirements.network));
    return buildPendingPayload({
      txHash,
      token: tokenSymbol,
      amount: input.amount,
      settlement: error.settlement,
      mode: "trc20_x402",
      requirements: error.requirements,
      bankofaiRecharge
    });
  }
}

export function publicInvalidParams(error: unknown): string {
  if (error instanceof Error && error.message.includes("PUBLIC_RESOURCE_BASE_URL")) {
    return "Server is missing PUBLIC_RESOURCE_BASE_URL";
  }
  if (error instanceof PaymentFlowError) {
    return error.reason;
  }
  return error instanceof Error ? error.message : String(error);
}
