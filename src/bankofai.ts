import type { PaymentRequirements, SettleResponse } from "@bankofai/x402-core/types";
import { bankofaiChainId, BILL_URL, findNetworkConfigByPaymentNetwork, txExplorerUrl } from "./payments.js";
import { settings } from "./config.js";

type BankofaiPayload = Record<string, unknown>;

async function fetchJson(url: string, init: RequestInit, timeoutSeconds: number): Promise<{ status: number; body: unknown }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), Math.max(1, timeoutSeconds) * 1000);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    const text = await response.text();
    let body: unknown = {};
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = { raw: text };
      }
    }
    return { status: response.status, body };
  } finally {
    clearTimeout(timer);
  }
}

function dataPayload(body: unknown): BankofaiPayload | undefined {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return undefined;
  }
  const record = body as Record<string, unknown>;
  const payload = record.data ?? record;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return undefined;
  }
  return payload as BankofaiPayload;
}

export async function queryRechargeStatus(txHash: string, paymentNetwork: string): Promise<BankofaiPayload | undefined> {
  const merchantId = settings.bankofaiMerchantId.trim();
  const merchantKey = settings.bankofaiMerchantKey.trim();
  if (!merchantId || !merchantKey || !txHash) {
    return undefined;
  }

  const cfg = findNetworkConfigByPaymentNetwork(paymentNetwork);
  const url = `${cfg.bankofaiApiUrl.replace(/\/+$/, "")}/m/credit/recharge`;
  try {
    const response = await fetchJson(
      url,
      {
        method: "POST",
        headers: {
          "X-Merchant-Id": merchantId,
          "X-Merchant-Key": merchantKey,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          chain: bankofaiChainId(paymentNetwork),
          tx_hash: txHash
        })
      },
      settings.bankofaiApiTimeoutSeconds
    );
    if (response.status !== 200) {
      console.warn(
        "BANK OF AI recharge status query returned non-200 tx=%s network=%s status=%s body=%j",
        txHash,
        paymentNetwork,
        response.status,
        response.body
      );
      return undefined;
    }
    return dataPayload(response.body);
  } catch (error) {
    console.warn(
      "BANK OF AI recharge status query failed tx=%s network=%s error=%s",
      txHash,
      paymentNetwork,
      error instanceof Error ? error.message : String(error)
    );
    return undefined;
  }
}

export async function queryBalance(walletAddress: string, paymentNetwork: string): Promise<BankofaiPayload | undefined> {
  const merchantId = settings.bankofaiMerchantId.trim();
  const merchantKey = settings.bankofaiMerchantKey.trim();
  if (!merchantId || !merchantKey || !walletAddress) {
    return undefined;
  }

  const cfg = findNetworkConfigByPaymentNetwork(paymentNetwork);
  const url = new URL(`${cfg.bankofaiApiUrl.replace(/\/+$/, "")}/m/credit/balance`);
  url.searchParams.set("wallet_address", walletAddress);
  try {
    const response = await fetchJson(
      url.toString(),
      {
        method: "GET",
        headers: {
          "X-Merchant-Id": merchantId,
          "X-Merchant-Key": merchantKey
        }
      },
      settings.bankofaiApiTimeoutSeconds
    );
    if (response.status !== 200) {
      console.warn(
        "BANK OF AI balance query returned non-200 address=%s network=%s status=%s body=%j",
        walletAddress,
        paymentNetwork,
        response.status,
        response.body
      );
      return undefined;
    }
    return dataPayload(response.body);
  } catch (error) {
    console.warn(
      "BANK OF AI balance query failed address=%s network=%s error=%s",
      walletAddress,
      paymentNetwork,
      error instanceof Error ? error.message : String(error)
    );
    return undefined;
  }
}

export function buildSuccessPayload(input: {
  txHash: string;
  token: string;
  amount: string;
  settlement: SettleResponse;
  mode: string;
  requirements: PaymentRequirements;
  bankofaiRecharge?: BankofaiPayload;
  bankofaiBalance?: BankofaiPayload;
}): Record<string, unknown> {
  const txUrl = input.txHash ? txExplorerUrl(input.txHash, String(input.requirements.network)) : "";
  const payload: Record<string, unknown> = {
    status: "paid",
    payment_status: "settled",
    recharge_status: "unconfirmed",
    mode: input.mode,
    message: txUrl
      ? `Recharge successful. View your bill at ${BILL_URL}. Transaction: ${txUrl}`
      : `Recharge successful. View your bill at ${BILL_URL}`,
    bill_url: BILL_URL,
    transaction_hash: input.txHash,
    transaction_url: txUrl,
    token: input.token.toUpperCase(),
    amount: input.amount,
    pay_to: input.requirements.payTo,
    network: input.requirements.network,
    verified: true,
    settlement: input.settlement
  };

  if (input.bankofaiRecharge) {
    payload.bankofai_recharge = input.bankofaiRecharge;
    const status = String(input.bankofaiRecharge.status ?? "").trim().toLowerCase();
    if (status) {
      payload.recharge_status = status;
    }
  }

  if (input.bankofaiBalance) {
    payload.bankofai_balance = input.bankofaiBalance;
    const balance = input.bankofaiBalance.balance;
    if (balance !== undefined && balance !== null) {
      payload.message = `${payload.message} Current balance: ${String(balance)}`;
    }
  }

  return payload;
}

export function buildPendingPayload(input: {
  txHash: string;
  token: string;
  amount: string;
  settlement: SettleResponse;
  mode: string;
  requirements: PaymentRequirements;
  bankofaiRecharge?: BankofaiPayload;
}): Record<string, unknown> {
  const txUrl = input.txHash ? txExplorerUrl(input.txHash, String(input.requirements.network)) : "";
  const payload: Record<string, unknown> = {
    status: "payment_pending",
    recharge_status: "pending",
    mode: input.mode,
    message: txUrl
      ? `Payment transaction was submitted but is not final yet. Do not retry payment. Wait for confirmation. Transaction: ${txUrl}`
      : "Payment transaction was submitted but is not final yet. Do not retry payment. Wait for confirmation.",
    retry_payment: false,
    transaction_hash: input.txHash,
    transaction_url: txUrl,
    token: input.token.toUpperCase(),
    amount: input.amount,
    pay_to: input.requirements.payTo,
    network: input.requirements.network,
    verified: true,
    settlement: input.settlement,
    failure_stage: "settle",
    failure_reason: input.settlement.errorReason ?? "invalid_transaction_state",
    detail: input.settlement.errorMessage
      ? `facilitator settle pending: ${input.settlement.errorReason}: ${input.settlement.errorMessage}`
      : `facilitator settle pending: ${input.settlement.errorReason ?? "invalid_transaction_state"}`
  };

  if (input.bankofaiRecharge) {
    payload.bankofai_recharge = input.bankofaiRecharge;
    const status = String(input.bankofaiRecharge.status ?? "").trim().toLowerCase();
    if (status) {
      payload.recharge_status = status;
    }
  }

  return payload;
}
