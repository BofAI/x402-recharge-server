import express from "express";
import type { Request, Response } from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";
import {
  decodePaymentSignatureHeader,
  encodePaymentRequiredHeader,
  encodePaymentResponseHeader
} from "@bankofai/x402-core/http";
import {
  buildRechargeChallenge,
  DEFAULT_TRC20_TOKEN,
  normalizeToken,
  PAYMENT_REQUIRED_HEADER,
  PAYMENT_RESPONSE_HEADER,
  PAYMENT_SIGNATURE_HEADER,
  isSettlementPendingError,
  paymentFailureDetails,
  settleWithFacilitator
} from "./payments.js";
import { buildPendingPayload, buildSuccessPayload, queryBalance, queryRechargeStatus } from "./bankofai.js";
import { networkConfig, settings } from "./config.js";

const app = express();
const rateLimitBucket: number[] = [];

app.disable("x-powered-by");
app.use(express.json({ limit: settings.requestBodyMaxBytes }));

function isRateLimited(): boolean {
  const limit = settings.rateLimitPerMinute;
  if (limit <= 0) {
    return false;
  }
  const now = Date.now() / 1000;
  const cutoff = now - 60;
  while (rateLimitBucket.length > 0 && rateLimitBucket[0] < cutoff) {
    rateLimitBucket.shift();
  }
  if (rateLimitBucket.length >= limit) {
    return true;
  }
  rateLimitBucket.push(now);
  return false;
}

function requestResourceUrl(req: Request): string {
  const publicBaseUrl = settings.publicResourceBaseUrl.trim().replace(/\/+$/, "");
  if (publicBaseUrl) {
    return `${publicBaseUrl}${req.originalUrl}`;
  }
  const host = req.get("host") ?? "";
  const hostname = (() => {
    if (host.startsWith("[")) {
      return host.slice(0, host.indexOf("]") + 1).toLowerCase();
    }
    return host.split(":")[0]?.toLowerCase();
  })();
  if (!["localhost", "127.0.0.1", "::1", "[::1]"].includes(hostname)) {
    throw new Error("PUBLIC_RESOURCE_BASE_URL is required for non-local requests");
  }
  return `${req.protocol}://${req.get("host")}${req.originalUrl}`;
}

function configuredResourceUrl(path: string): string {
  const publicBaseUrl = settings.publicResourceBaseUrl.trim().replace(/\/+$/, "");
  if (publicBaseUrl) {
    return `${publicBaseUrl}${path}`;
  }
  return `http://127.0.0.1:${settings.port}${path}`;
}

function publicPaymentFailure(details: ReturnType<typeof paymentFailureDetails>): Record<string, unknown> {
  const reason = details.stage === "verify"
    ? "invalid_payment_signature"
    : details.stage === "settle"
      ? "payment_settlement_failed"
      : "invalid_payment";
  return {
    error: "payment_verification_failed",
    failure_stage: details.stage,
    failure_reason: reason,
    detail: reason,
    message: details.stage === "settle"
      ? "Payment settlement failed. Do not retry automatically; check transaction status before creating a new payment."
      : "Provided payment is invalid. Create a new payment and retry."
  };
}

function rpcResult(id: unknown, result: Record<string, unknown>): Record<string, unknown> {
  return { jsonrpc: "2.0", id, result };
}

function rpcError(id: unknown, code: number, message: string, data?: Record<string, unknown>): Record<string, unknown> {
  const error: Record<string, unknown> = { code, message };
  if (data) {
    error.data = data;
  }
  return { jsonrpc: "2.0", id, error };
}

function isRechargeToolCall(body: unknown): { id: unknown; amount: string; token: string } | undefined {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return undefined;
  }
  const payload = body as Record<string, unknown>;
  if (payload.method !== "tools/call") {
    return undefined;
  }
  const params = payload.params;
  if (!params || typeof params !== "object" || Array.isArray(params)) {
    return undefined;
  }
  const paramsRecord = params as Record<string, unknown>;
  if (paramsRecord.name !== "recharge") {
    return undefined;
  }
  const args = paramsRecord.arguments && typeof paramsRecord.arguments === "object" && !Array.isArray(paramsRecord.arguments)
    ? paramsRecord.arguments as Record<string, unknown>
    : {};
  return {
    id: payload.id,
    amount: String(args.amount ?? ""),
    token: String(args.token ?? DEFAULT_TRC20_TOKEN)
  };
}

async function paidRecharge(amount: string, token: string, paymentSignature: string, resourceUrl: string): Promise<Record<string, unknown>> {
  const tokenSymbol = normalizeToken(token);
  const challenge = await buildRechargeChallenge(amount, tokenSymbol, resourceUrl);
  const { settlement, requirements, walletAddress } = await settleWithFacilitator(paymentSignature, challenge);
  const txHash = String(settlement.transaction ?? "");
  const bankofaiRecharge = await queryRechargeStatus(txHash, String(requirements.network));
  const bankofaiBalance = await queryBalance(walletAddress, String(requirements.network));
  return buildSuccessPayload({
    txHash,
    token: tokenSymbol,
    amount,
    settlement,
    mode: "trc20_x402",
    requirements,
    bankofaiRecharge,
    bankofaiBalance
  });
}

async function pendingRecharge(error: unknown, token: string, amount: string): Promise<Record<string, unknown> | undefined> {
  if (!isSettlementPendingError(error)) {
    return undefined;
  }
  const txHash = String(error.settlement.transaction ?? "");
  const bankofaiRecharge = await queryRechargeStatus(txHash, String(error.requirements.network));
  return buildPendingPayload({
    txHash,
    token,
    amount,
    settlement: error.settlement,
    mode: "trc20_x402",
    requirements: error.requirements,
    bankofaiRecharge
  });
}

function createMcpServer(): McpServer {
  const server = new McpServer({
    name: "x402-recharge-server",
    version: "2.0.0"
  });

  server.registerTool(
    "recharge",
    {
      title: "Recharge",
      description: "Recharge BANK OF AI with supported TRON/BSC tokens through x402.",
      inputSchema: {
        amount: z.string(),
        token: z.string().default(DEFAULT_TRC20_TOKEN)
      }
    },
    async ({ amount, token }, extra) => {
      const headers = extra.requestInfo?.headers as Record<string, string | string[] | undefined> | undefined;
      const paymentSignature = headers?.[PAYMENT_SIGNATURE_HEADER.toLowerCase()] ?? headers?.[PAYMENT_SIGNATURE_HEADER];
      const signature = Array.isArray(paymentSignature) ? paymentSignature[0] : paymentSignature;
      if (signature) {
        try {
          const success = await paidRecharge(String(amount), String(token), signature, configuredResourceUrl("/mcp"));
          return {
            content: [{ type: "text", text: JSON.stringify(success) }],
            structuredContent: success
          };
        } catch (error) {
          const pending = await pendingRecharge(error, String(token), String(amount));
          if (pending) {
            return {
              content: [{ type: "text", text: JSON.stringify(pending) }],
              structuredContent: pending
            };
          }
          const details = paymentFailureDetails(error);
          return {
            isError: true,
            content: [{
              type: "text",
              text: JSON.stringify({
                status: "payment_verification_failed",
                ...publicPaymentFailure(details)
              })
            }]
          };
        }
      }

      const tokenSymbol = normalizeToken(String(token));
      const challenge = await buildRechargeChallenge(String(amount), tokenSymbol, configuredResourceUrl("/mcp"));
      const result = {
        status: "payment_required",
        message: "Payment required. Call this tool through MCP HTTP /mcp to receive standard x402 402 headers.",
        x402: challenge,
        retry_hint: "Retry the same MCP tool call with PAYMENT-SIGNATURE header after payment."
      };
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        structuredContent: result
      };
    }
  );

  return server;
}

app.get("/", (_req, res) => {
  res.status(200).json({
    status: "ok",
    service: "x402-recharge-server",
    version: "2.0.0",
    message: "BANK OF AI x402 Recharge MCP Server is running."
  });
});

app.get("/health", (_req, res) => {
  res.status(200).json({
    status: "ok",
    service: "x402-recharge-server",
    version: "2.0.0"
  });
});

app.post("/mcp", async (req: Request, res: Response) => {
  if (isRateLimited()) {
    res.status(429).json({ error: "rate_limited" });
    return;
  }

  const rechargeCall = isRechargeToolCall(req.body);
  if (rechargeCall) {
    let challenge;
    try {
      challenge = await buildRechargeChallenge(
        rechargeCall.amount,
        rechargeCall.token,
        requestResourceUrl(req)
      );
    } catch (error) {
      res.status(400).json(rpcError(rechargeCall.id, -32602, "Invalid params", {
        error: error instanceof Error && error.message.includes("PUBLIC_RESOURCE_BASE_URL")
          ? "Server is missing PUBLIC_RESOURCE_BASE_URL"
          : error instanceof Error ? error.message : String(error)
      }));
      return;
    }

    const paymentSignature = req.header(PAYMENT_SIGNATURE_HEADER);
    if (!paymentSignature) {
      res
        .status(402)
        .set(PAYMENT_REQUIRED_HEADER, encodePaymentRequiredHeader(challenge))
        .json(rpcError(rechargeCall.id, -32002, "Payment Required", { x402: challenge }));
      return;
    }

    try {
      const { settlement, requirements, walletAddress } = await settleWithFacilitator(paymentSignature, challenge);
      const txHash = String(settlement.transaction ?? "");
      const bankofaiRecharge = await queryRechargeStatus(txHash, String(requirements.network));
      const bankofaiBalance = await queryBalance(walletAddress, String(requirements.network));
      const success = buildSuccessPayload({
        txHash,
        token: rechargeCall.token,
        amount: rechargeCall.amount,
        settlement,
        mode: "trc20_x402",
        requirements,
        bankofaiRecharge,
        bankofaiBalance
      });
      res
        .status(200)
        .set(PAYMENT_RESPONSE_HEADER, encodePaymentResponseHeader(settlement))
        .json(rpcResult(rechargeCall.id, success));
    } catch (error) {
      const pending = await pendingRecharge(error, rechargeCall.token, rechargeCall.amount);
      if (pending) {
        res.status(202).json(rpcResult(rechargeCall.id, pending));
        return;
      }
      const details = paymentFailureDetails(error);
      res.status(400).json(rpcError(rechargeCall.id, -32003, "Payment verification failed", {
        ...publicPaymentFailure(details)
      }));
    }
    return;
  }

  const server = createMcpServer();
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  try {
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
    res.on("close", () => {
      void transport.close();
      void server.close();
    });
  } catch (error) {
    console.error("Error handling MCP request:", error);
    if (!res.headersSent) {
      res.status(500).json(rpcError(null, -32603, "Internal server error"));
    }
  }
});

app.get("/mcp", (_req, res) => {
  res.status(405).json(rpcError(null, -32000, "Method not allowed."));
});

app.delete("/mcp", (_req, res) => {
  res.status(405).json(rpcError(null, -32000, "Method not allowed."));
});

async function handleX402Recharge(req: Request, res: Response): Promise<void> {
  if (isRateLimited()) {
    res.status(429).json({ error: "rate_limited" });
    return;
  }

  const amount = String(req.body?.amount ?? "");
  const token = String(req.body?.token ?? DEFAULT_TRC20_TOKEN);
  let tokenSymbol: string;
  let challenge;
  try {
    tokenSymbol = normalizeToken(token);
    challenge = await buildRechargeChallenge(amount, tokenSymbol, requestResourceUrl(req));
  } catch (error) {
    res.status(400).json({
      error: "invalid_params",
      message: error instanceof Error && error.message.includes("PUBLIC_RESOURCE_BASE_URL")
        ? "Server is missing PUBLIC_RESOURCE_BASE_URL"
        : error instanceof Error ? error.message : String(error)
    });
    return;
  }

  const paymentSignature = req.header(PAYMENT_SIGNATURE_HEADER);
  if (!paymentSignature) {
    res
      .status(402)
      .set(PAYMENT_REQUIRED_HEADER, encodePaymentRequiredHeader(challenge))
      .json(challenge);
    return;
  }

  try {
    decodePaymentSignatureHeader(paymentSignature);
    const { settlement, requirements, walletAddress } = await settleWithFacilitator(paymentSignature, challenge);
    const txHash = String(settlement.transaction ?? "");
    const bankofaiRecharge = await queryRechargeStatus(txHash, String(requirements.network));
    const bankofaiBalance = await queryBalance(walletAddress, String(requirements.network));
    const success = buildSuccessPayload({
      txHash,
      token: tokenSymbol,
      amount,
      settlement,
      mode: "trc20_x402",
      requirements,
      bankofaiRecharge,
      bankofaiBalance
    });
    res
      .status(200)
      .set(PAYMENT_RESPONSE_HEADER, encodePaymentResponseHeader(settlement))
      .json(success);
  } catch (error) {
    const pending = await pendingRecharge(error, tokenSymbol, amount);
    if (pending) {
      res.status(202).json(pending);
      return;
    }
    const details = paymentFailureDetails(error);
    res.status(400).json({
      ...publicPaymentFailure(details)
    });
  }
}

app.post("/x402/recharge", (req, res) => {
  void handleX402Recharge(req, res);
});

app.post("/x402/trc20/recharge", (req, res) => {
  void handleX402Recharge(req, res);
});

app.use((error: unknown, _req: Request, res: Response, _next: express.NextFunction) => {
  if (error && typeof error === "object" && "type" in error && error.type === "entity.too.large") {
    res.status(413).json({ error: "request_too_large" });
    return;
  }
  console.error("Unhandled request error:", error);
  res.status(500).json({ error: "internal_server_error" });
});

const httpServer = app.listen(settings.port, settings.host, () => {
  console.info("=".repeat(60));
  console.info("BANK OF AI Payment MCP Server Starting");
  console.info("Environment: %s", settings.bankofaiEnv);
  console.info("Network: %s", networkConfig.name);
  console.info("BANK OF AI Deposit Address: %s", networkConfig.bankofaiDepositAddress);
  console.info("Tools: recharge");
  console.info("MCP Streamable HTTP Endpoint: http://%s:%s/mcp", settings.host, settings.port);
  console.info("x402 HTTP Endpoint: http://%s:%s/x402/recharge", settings.host, settings.port);
  console.info("x402 TRC20 HTTP Endpoint: http://%s:%s/x402/trc20/recharge", settings.host, settings.port);
  console.info("=".repeat(60));
});

httpServer.on("error", (error) => {
  console.error("Failed to start server:", error);
  process.exitCode = 1;
});

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => {
    httpServer.close(() => {
      process.exit(0);
    });
  });
}
