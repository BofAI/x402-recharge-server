import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");

type TokenConfig = {
  symbol: string;
  address?: string;
  decimals: number;
  minimum: string;
};

type RawNetworkConfig = {
  name: string;
  paymentNetwork?: string;
  rpcUrl: string;
  explorer: string;
  chainId: string;
  bankofaiDepositAddress?: string;
  ainftDepositAddress?: string;
  bankofaiApiUrl?: string;
  ainftApiUrl?: string;
  bankofaiWebUrl?: string;
  ainftWebUrl?: string;
  erc8004Registry: string;
  tokens: Record<string, TokenConfig>;
};

export type NetworkConfigs = Record<string, RawNetworkConfig>;

function envString(name: string, fallback = ""): string {
  return process.env[name] ?? fallback;
}

function envNumber(name: string, fallback: number): number {
  const raw = process.env[name];
  if (raw === undefined || raw.trim() === "") {
    return fallback;
  }
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    throw new Error(`Invalid numeric env var ${name}: ${raw}`);
  }
  return parsed;
}

function defaultFacilitatorUrl(bankofaiEnv: string): string {
  return bankofaiEnv.toLowerCase().trim() === "dev"
    ? "https://tn-facilitator.bankofai.io"
    : "https://facilitator.bankofai.io";
}

const bankofaiEnv = envString("BANKOFAI_ENV", "dev");
const x402FacilitatorUrl = bankofaiEnv.toLowerCase().trim() === "dev"
  ? defaultFacilitatorUrl(bankofaiEnv)
  : envString("X402_FACILITATOR_URL", defaultFacilitatorUrl(bankofaiEnv));

export const settings = {
  bankofaiEnv,
  tronRpcUrl: envString("TRON_RPC_URL", ""),
  host: envString("HOST", "0.0.0.0"),
  port: envNumber("PORT", 8000),
  logLevel: envString("LOG_LEVEL", "info"),
  x402FacilitatorUrl,
  facilitatorApiKey: envString("FACILITATOR_API_KEY", ""),
  facilitatorTimeoutSeconds: envNumber("FACILITATOR_TIMEOUT_SECONDS", 10),
  facilitatorVerifyRetries: envNumber("FACILITATOR_VERIFY_RETRIES", 1),
  facilitatorRetryBackoffSeconds: envNumber("FACILITATOR_RETRY_BACKOFF_SECONDS", 0.5),
  facilitatorSettleTimeoutSeconds: envNumber("FACILITATOR_SETTLE_TIMEOUT_SECONDS", 120),
  bankofaiMerchantId: envString("BANKOFAI_MERCHANT_ID", ""),
  bankofaiMerchantKey: envString("BANKOFAI_MERCHANT_KEY", ""),
  bankofaiApiTimeoutSeconds: envNumber("BANKOFAI_API_TIMEOUT_SECONDS", 10),
  rateLimitPerMinute: envNumber("RATE_LIMIT_PER_MINUTE", 120),
  requestBodyMaxBytes: envNumber("REQUEST_BODY_MAX_BYTES", 1_048_576)
};

export function activeNetworkName(): string {
  const env = settings.bankofaiEnv.toLowerCase().trim();
  if (env === "dev") {
    return "nile";
  }
  if (env === "prod") {
    return "mainnet";
  }
  throw new Error(`Invalid BANKOFAI_ENV: ${settings.bankofaiEnv}. Expected: dev | prod`);
}

export const networkConfigs: NetworkConfigs = JSON.parse(
  fs.readFileSync(path.join(rootDir, "config", "networks.json"), "utf8")
) as NetworkConfigs;

export class NetworkConfig {
  readonly network: string;
  private readonly config: RawNetworkConfig;

  constructor(network: string, allConfigs: NetworkConfigs = networkConfigs) {
    const config = allConfigs[network];
    if (!config) {
      throw new Error(`Invalid network: ${network}. Available: ${Object.keys(allConfigs).join(", ")}`);
    }
    this.network = network;
    this.config = config;
  }

  get name(): string {
    return this.config.name;
  }

  get rpcUrl(): string {
    if (this.paymentNetwork.startsWith("tron:") && settings.tronRpcUrl.trim()) {
      return settings.tronRpcUrl.trim();
    }
    return this.config.rpcUrl;
  }

  get explorer(): string {
    return this.config.explorer;
  }

  get paymentNetwork(): string {
    return this.config.paymentNetwork ?? this.network;
  }

  get chainId(): string {
    return this.config.chainId;
  }

  get bankofaiDepositAddress(): string {
    return this.config.bankofaiDepositAddress ?? this.config.ainftDepositAddress ?? "";
  }

  get bankofaiApiUrl(): string {
    return this.config.bankofaiApiUrl ?? this.config.ainftApiUrl ?? "";
  }

  get bankofaiWebUrl(): string {
    return this.config.bankofaiWebUrl ?? this.config.ainftWebUrl ?? "";
  }

  get tokens(): Record<string, TokenConfig> {
    return this.config.tokens;
  }

  getTokenInfo(symbol: string): TokenConfig | undefined {
    return this.tokens[symbol.toUpperCase()];
  }
}

export const networkConfig = new NetworkConfig(activeNetworkName(), networkConfigs);
