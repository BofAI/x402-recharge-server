import crypto from "node:crypto";
import type { Network, PaymentPayload, PaymentRequired, PaymentRequirements, SettleResponse } from "@bankofai/x402-core/types";
import { HTTPFacilitatorClient } from "@bankofai/x402-core/http";
import { decodePaymentSignatureHeader } from "@bankofai/x402-core/http";
import { getToken, TRON_MAINNET, TRON_NILE } from "@bankofai/x402-tron";
import { getDefaultAsset } from "@bankofai/x402-evm";
import { NetworkConfig, networkConfig, networkConfigs, settings } from "./config.js";

const ALLOWED_TRC20_TOKENS = new Set(["USDT", "USDD"]);
const BSC_ALLOWED_TOKENS = new Set(["USDT"]);
const EXACT_SCHEME = "exact";
const GASFREE_SCHEME = "exact_gasfree";
const MIN_RECHARGE_AMOUNT = "1";
const MAX_RECHARGE_AMOUNT = "20000";

export const PAYMENT_REQUIRED_HEADER = "PAYMENT-REQUIRED";
export const PAYMENT_SIGNATURE_HEADER = "PAYMENT-SIGNATURE";
export const PAYMENT_RESPONSE_HEADER = "PAYMENT-RESPONSE";
export const BILL_URL = `${networkConfig.bankofaiWebUrl.replace(/\/+$/, "")}/purchase`;

export type PaymentFailureDetails = {
  stage: string;
  reason: string;
  raw: string;
};

export type SettlementResult = {
  settlement: SettleResponse;
  requirements: PaymentRequirements;
  walletAddress: string;
};

const facilitator = new HTTPFacilitatorClient({
  url: settings.x402FacilitatorUrl,
  createAuthHeaders: async () => {
    const headers: Record<string, string> = settings.facilitatorApiKey ? { "X-API-KEY": settings.facilitatorApiKey } : {};
    return {
      verify: headers,
      settle: headers,
      supported: headers
    };
  }
});

function supportedPaymentNetworkConfigs(): NetworkConfig[] {
  const configs = [networkConfig];
  if (settings.bankofaiEnv.toLowerCase().trim() === "dev" && networkConfigs.bsc_testnet) {
    configs.push(new NetworkConfig("bsc_testnet", networkConfigs));
  }
  if (settings.bankofaiEnv.toLowerCase().trim() === "prod" && networkConfigs.bsc_mainnet) {
    configs.push(new NetworkConfig("bsc_mainnet", networkConfigs));
  }
  return configs;
}

export function supportedTokens(): string[] {
  const tokens = new Set<string>();
  for (const cfg of supportedPaymentNetworkConfigs()) {
    for (const [symbol, tokenCfg] of Object.entries(cfg.tokens)) {
      if (ALLOWED_TRC20_TOKENS.has(symbol.toUpperCase()) && tokenCfg.address) {
        tokens.add(symbol.toUpperCase());
      }
    }
  }
  return [...tokens].sort();
}

export const DEFAULT_TRC20_TOKEN = supportedTokens().includes("USDT") ? "USDT" : supportedTokens()[0];

export function normalizeToken(token: string | undefined): string {
  const tokenSymbol = (token || DEFAULT_TRC20_TOKEN).toUpperCase().trim();
  const allowed = supportedTokens();
  if (!allowed.includes(tokenSymbol)) {
    throw new Error(`Unsupported TRC20 token: ${tokenSymbol}. Supported: ${allowed.join(", ")}`);
  }
  return tokenSymbol;
}

function parseDecimal(raw: string): { sign: 1 | -1; intPart: string; fracPart: string } {
  const trimmed = raw.trim();
  const match = trimmed.match(/^([+-])?(\d+)(?:\.(\d+))?$/);
  if (!match) {
    throw new Error(`Invalid amount: ${raw}`);
  }
  return {
    sign: match[1] === "-" ? -1 : 1,
    intPart: match[2].replace(/^0+(?=\d)/, ""),
    fracPart: match[3] ?? ""
  };
}

function compareDecimal(a: string, b: string): number {
  const left = parseDecimal(a);
  const right = parseDecimal(b);
  if (left.sign !== right.sign) {
    return left.sign > right.sign ? 1 : -1;
  }
  const sign = left.sign;
  if (left.intPart.length !== right.intPart.length) {
    return left.intPart.length > right.intPart.length ? sign : -sign;
  }
  if (left.intPart !== right.intPart) {
    return left.intPart > right.intPart ? sign : -sign;
  }
  const maxFrac = Math.max(left.fracPart.length, right.fracPart.length);
  const leftFrac = left.fracPart.padEnd(maxFrac, "0");
  const rightFrac = right.fracPart.padEnd(maxFrac, "0");
  if (leftFrac === rightFrac) {
    return 0;
  }
  return leftFrac > rightFrac ? sign : -sign;
}

function parseRechargeAmount(amount: string): string {
  parseDecimal(amount);
  if (compareDecimal(amount, MIN_RECHARGE_AMOUNT) < 0 || compareDecimal(amount, MAX_RECHARGE_AMOUNT) > 0) {
    throw new Error(`Amount must be between ${MIN_RECHARGE_AMOUNT} and ${MAX_RECHARGE_AMOUNT}.`);
  }
  return amount.trim();
}

function decimalToSmallestUnit(amount: string, decimals: number): bigint {
  const parsed = parseDecimal(amount);
  if (parsed.sign < 0) {
    throw new Error(`Invalid amount: ${amount}`);
  }
  if (parsed.fracPart.length > decimals) {
    throw new Error(`Amount precision exceeds token decimals (${decimals}).`);
  }
  const paddedFrac = parsed.fracPart.padEnd(decimals, "0");
  return BigInt(`${parsed.intPart}${paddedFrac}` || "0");
}

function sdkTronNetwork(paymentNetwork: string): Network {
  if (paymentNetwork === "tron:mainnet") {
    return TRON_MAINNET as Network;
  }
  if (paymentNetwork === "tron:nile") {
    return TRON_NILE as Network;
  }
  return paymentNetwork as Network;
}

function facilitatorNetworkCandidates(paymentNetwork: string): Network[] {
  const candidates = [paymentNetwork as Network];
  const sdkNetwork = sdkTronNetwork(paymentNetwork);
  if (!candidates.includes(sdkNetwork)) {
    candidates.push(sdkNetwork);
  }
  return candidates;
}

function paymentExtra(cfg: NetworkConfig, tokenSymbol: string, scheme: string): Record<string, unknown> {
  if (cfg.paymentNetwork.startsWith("tron:")) {
    const token = getToken(sdkTronNetwork(cfg.paymentNetwork), tokenSymbol);
    if (!token) {
      return {};
    }
    if (scheme === GASFREE_SCHEME) {
      return {
        name: token.name,
        ...(token.version !== undefined ? { version: token.version } : {})
      };
    }
    const includeTip712Domain = !token.assetTransferMethod || Boolean(token.supportsEip2612);
    return {
      ...(includeTip712Domain && token.version !== undefined ? { name: token.name, version: token.version } : {}),
      ...(token.assetTransferMethod ? { assetTransferMethod: token.assetTransferMethod } : {})
    };
  }
  if (cfg.paymentNetwork.startsWith("eip155:")) {
    const asset = getDefaultAsset(cfg.paymentNetwork as Network);
    return asset.assetTransferMethod ? { assetTransferMethod: asset.assetTransferMethod } : {};
  }
  return {};
}

export function paymentFailureDetails(error: unknown): PaymentFailureDetails {
  const raw = error instanceof Error ? error.message : String(error || "unknown");
  if (raw.startsWith("facilitator verify failed:")) {
    return {
      stage: "verify",
      reason: raw.split(":", 2)[1]?.trim() || "invalid_payment_signature",
      raw
    };
  }
  if (raw.startsWith("facilitator settle failed:")) {
    return {
      stage: "settle",
      reason: raw.split(":", 2)[1]?.trim() || "transaction_failed_on_chain",
      raw
    };
  }
  return { stage: "unknown", reason: raw, raw };
}

function timeoutSignal(seconds: number): AbortSignal {
  return AbortSignal.timeout(Math.max(1, seconds) * 1000);
}

async function withTimeout<T>(promise: Promise<T>, seconds: number, label: string): Promise<T> {
  let timer: NodeJS.Timeout | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label}: timeout`)), Math.max(1, seconds) * 1000);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}

export async function buildRechargeChallenge(amount: string, token: string, resourceUrl: string): Promise<PaymentRequired> {
  const tokenSymbol = normalizeToken(token);
  const amountText = parseRechargeAmount(amount);
  const accepts: PaymentRequirements[] = [];

  for (const cfg of supportedPaymentNetworkConfigs()) {
    if (cfg.paymentNetwork.startsWith("eip155:") && !BSC_ALLOWED_TOKENS.has(tokenSymbol)) {
      continue;
    }
    const tokenCfg = cfg.getTokenInfo(tokenSymbol);
    if (!tokenCfg?.address) {
      continue;
    }

    let amountSmallest: bigint;
    try {
      amountSmallest = decimalToSmallestUnit(amountText, tokenCfg.decimals);
    } catch (error) {
      console.warn(
        "Skipping payment route token=%s network=%s amount=%s: %s",
        tokenSymbol,
        cfg.paymentNetwork,
        amountText,
        error instanceof Error ? error.message : String(error)
      );
      continue;
    }

    if (amountSmallest < BigInt(tokenCfg.minimum)) {
      console.warn(
        "Skipping payment route token=%s network=%s amount=%s: below minimum smallest=%s minimum=%s",
        tokenSymbol,
        cfg.paymentNetwork,
        amountText,
        amountSmallest.toString(),
        tokenCfg.minimum
      );
      continue;
    }

    const schemes = cfg.paymentNetwork.startsWith("tron:")
      ? [EXACT_SCHEME, GASFREE_SCHEME]
      : [EXACT_SCHEME];
    for (const scheme of schemes) {
      accepts.push({
        scheme,
        network: cfg.paymentNetwork as Network,
        amount: amountSmallest.toString(),
        asset: tokenCfg.address,
        payTo: cfg.bankofaiDepositAddress,
        maxTimeoutSeconds: 3600,
        extra: paymentExtra(cfg, tokenSymbol, scheme)
      });
    }
  }

  if (accepts.length === 0) {
    throw new Error(`Token config missing for supported token: ${tokenSymbol}`);
  }

  const supported = await withTimeout(
    facilitator.getSupported(),
    settings.facilitatorTimeoutSeconds,
    "facilitator supported failed"
  ).catch((error) => {
    throw new Error(error instanceof Error && error.message.includes("timeout")
      ? "facilitator supported failed: timeout"
      : "facilitator supported failed: upstream_error");
  });

  const supportedKinds = supported.kinds ?? [];
  const filteredAccepts = accepts.flatMap((accept) => {
    const supportedKind = supportedKinds.find((kind) =>
      kind.scheme === accept.scheme && facilitatorNetworkCandidates(String(accept.network)).includes(kind.network)
    );
    if (!supportedKind) {
      console.warn(
        "Skipping unsupported payment route token=%s network=%s asset=%s because facilitator supported response did not include it",
        tokenSymbol,
        accept.network,
        accept.asset
      );
      return [];
    }
    return [{
      ...accept,
      network: supportedKind.network,
      extra: {
        ...(supportedKind.extra ?? {}),
        ...(accept.extra ?? {})
      }
    }];
  });

  if (filteredAccepts.length === 0) {
    throw new Error(`No supported payment routes available for token: ${tokenSymbol}`);
  }

  const extensions: Record<string, unknown> = {
    paymentPermitContext: {
      meta: {
        kind: "PAYMENT_ONLY",
        paymentId: `0x${crypto.randomBytes(16).toString("hex")}`,
        nonce: crypto.randomUUID().replace(/-/g, ""),
        validAfter: Math.floor(Date.now() / 1000),
        validBefore: Math.floor(Date.now() / 1000) + 3600
      }
    }
  };
  if (supported.extensions?.includes("erc20ApprovalGasSponsoring")) {
    extensions.erc20ApprovalGasSponsoring = {};
  }

  return {
    x402Version: 2,
    error: "Payment Required",
    resource: {
      url: resourceUrl,
      description: "BANK OF AI recharge payment challenge",
      mimeType: "application/json"
    },
    accepts: filteredAccepts,
    extensions
  };
}

function selectedRequirementFromPayload(payload: PaymentPayload, challenge: PaymentRequired): PaymentRequirements {
  const accepted = payload.accepted;
  const selected = challenge.accepts.find((item) =>
    item.scheme === accepted.scheme &&
    String(item.network) === String(accepted.network) &&
    String(item.amount) === String(accepted.amount) &&
    String(item.asset) === String(accepted.asset) &&
    String(item.payTo) === String(accepted.payTo)
  );
  if (!selected) {
    throw new Error("facilitator verify failed: payment does not match any accepted requirement");
  }
  return selected;
}

function paymentWalletAddress(payload: PaymentPayload): string {
  const payment = payload.payload as Record<string, unknown>;
  const gasfree = payment.gasfree as Record<string, unknown> | undefined;
  if (typeof gasfree?.user === "string") {
    return gasfree.user;
  }
  const permit = payment.paymentPermit as Record<string, unknown> | undefined;
  if (typeof permit?.buyer === "string") {
    return permit.buyer;
  }
  const permit2 = payment.permit2Authorization as Record<string, unknown> | undefined;
  if (typeof permit2?.from === "string") {
    return permit2.from;
  }
  const authorization = payment.authorization as Record<string, unknown> | undefined;
  if (typeof authorization?.from === "string") {
    return authorization.from;
  }
  return "";
}

export async function settleWithFacilitator(paymentSignature: string, challenge: PaymentRequired): Promise<SettlementResult> {
  const payload = decodePaymentSignatureHeader(paymentSignature);
  const walletAddress = paymentWalletAddress(payload);
  const requirements = selectedRequirementFromPayload(payload, challenge);

  let verifyResult;
  let lastError: Error | undefined;
  for (let attempt = 0; attempt <= settings.facilitatorVerifyRetries; attempt += 1) {
    try {
      verifyResult = await withTimeout(
        facilitator.verify(payload, requirements),
        settings.facilitatorTimeoutSeconds,
        "facilitator verify failed"
      );
      lastError = undefined;
      break;
    } catch (error) {
      const message = error instanceof Error && error.message.includes("timeout")
        ? "facilitator verify failed: timeout"
        : "facilitator verify failed: upstream_error";
      lastError = new Error(message);
      if (attempt < settings.facilitatorVerifyRetries) {
        await new Promise((resolve) => setTimeout(resolve, settings.facilitatorRetryBackoffSeconds * 1000));
      }
    }
  }
  if (lastError) {
    throw lastError;
  }
  if (!verifyResult?.isValid) {
    throw new Error(`facilitator verify failed: ${verifyResult?.invalidReason ?? "invalid_payment_signature"}`);
  }

  let settlement: SettleResponse;
  try {
    settlement = await withTimeout(
      facilitator.settle(payload, requirements),
      settings.facilitatorSettleTimeoutSeconds,
      "facilitator settle failed"
    );
  } catch (error) {
    throw new Error(error instanceof Error && error.message.includes("timeout")
      ? "facilitator settle failed: timeout"
      : "facilitator settle failed: upstream_error");
  }
  if (!settlement.success) {
    const reason = settlement.errorReason ?? "transaction_failed_on_chain";
    const detail = settlement.errorMessage ? `${reason}: ${settlement.errorMessage}` : reason;
    throw new Error(`facilitator settle failed: ${detail}`);
  }
  return { settlement, requirements, walletAddress };
}

export function findNetworkConfigByPaymentNetwork(paymentNetwork: string): NetworkConfig {
  for (const cfg of supportedPaymentNetworkConfigs()) {
    if (
      String(cfg.paymentNetwork) === String(paymentNetwork) ||
      String(sdkTronNetwork(cfg.paymentNetwork)) === String(paymentNetwork)
    ) {
      return cfg;
    }
  }
  throw new Error(`Unsupported payment network: ${paymentNetwork}`);
}

export function txExplorerUrl(txHash: string, paymentNetwork: string): string {
  const base = findNetworkConfigByPaymentNetwork(paymentNetwork).explorer.replace(/\/+$/, "");
  if (paymentNetwork.startsWith("eip155:")) {
    return `${base}/tx/${txHash}`;
  }
  return `${base}/#/transaction/${txHash}`;
}

export function bankofaiChainId(paymentNetwork: string): string {
  if (paymentNetwork === TRON_MAINNET || paymentNetwork === "tron:mainnet") {
    return "eip155:728126428";
  }
  if (paymentNetwork === TRON_NILE || paymentNetwork === "tron:nile") {
    return "eip155:3448148188";
  }
  if (paymentNetwork === "eip155:56") {
    return "eip155:56";
  }
  if (paymentNetwork === "eip155:97") {
    return "eip155:97";
  }
  throw new Error(`Unsupported chain mapping for payment network: ${paymentNetwork}`);
}
