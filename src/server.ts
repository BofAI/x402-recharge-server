import express from "express";
import type { Request, Response } from "express";
import type { SettleResponse } from "@bankofai/x402-core/types";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";
import {
  encodePaymentRequiredHeader,
  encodePaymentResponseHeader
} from "@bankofai/x402-core/http";
import {
  PAYMENT_REQUIRED_HEADER,
  PAYMENT_RESPONSE_HEADER,
  PAYMENT_SIGNATURE_HEADER
} from "./payments.js";
import { networkConfig, settings } from "./config.js";
import { logger } from "./logger.js";
import { FixedWindowRateLimiter } from "./rate-limit.js";
import {
  DEFAULT_TRC20_TOKEN,
  createRechargeChallenge,
  publicInvalidParams,
  publicPaymentFailure,
  settleRecharge
} from "./recharge.js";

const app = express();
const rateLimiter = new FixedWindowRateLimiter(settings.rateLimitPerMinute);

app.disable("x-powered-by");
if (settings.trustProxyHops > 0) {
  app.set("trust proxy", settings.trustProxyHops);
}
app.use(express.json({ limit: settings.requestBodyMaxBytes }));

function rateLimitKey(req: Request): string {
  return req.ip || req.socket.remoteAddress || "unknown";
}

function rejectIfRateLimited(req: Request, res: Response): boolean {
  const result = rateLimiter.consume(rateLimitKey(req));
  if (result.allowed) {
    return false;
  }
  res.status(429).json({ error: "rate_limited" });
  return true;
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

function settlementFromPayload(payload: Record<string, unknown>): SettleResponse {
  return payload.settlement as SettleResponse;
}

function responseStatus(payload: Record<string, unknown>): number {
  return payload.status === "payment_pending" ? 202 : 200;
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
          const success = await settleRecharge({
            amount: String(amount),
            token: String(token),
            paymentSignature: signature,
            resourceUrl: configuredResourceUrl("/mcp")
          });
          return {
            content: [{ type: "text", text: JSON.stringify(success) }],
            structuredContent: success
          };
        } catch (error) {
          return {
            isError: true,
            content: [{
              type: "text",
              text: JSON.stringify({
                status: "payment_verification_failed",
                ...publicPaymentFailure(error)
              })
            }]
          };
        }
      }

      const { challenge } = await createRechargeChallenge({
        amount: String(amount),
        token: String(token),
        resourceUrl: configuredResourceUrl("/mcp")
      });
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
  if (rejectIfRateLimited(req, res)) {
    return;
  }

  const rechargeCall = isRechargeToolCall(req.body);
  if (rechargeCall) {
    let challenge;
    try {
      challenge = (await createRechargeChallenge({
        amount: rechargeCall.amount,
        token: rechargeCall.token,
        resourceUrl: requestResourceUrl(req)
      })).challenge;
    } catch (error) {
      res.status(400).json(rpcError(rechargeCall.id, -32602, "Invalid params", {
        error: publicInvalidParams(error)
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
      const success = await settleRecharge({
        amount: rechargeCall.amount,
        token: rechargeCall.token,
        paymentSignature,
        resourceUrl: requestResourceUrl(req)
      });
      res
        .status(responseStatus(success))
        .set(PAYMENT_RESPONSE_HEADER, encodePaymentResponseHeader(settlementFromPayload(success)))
        .json(rpcResult(rechargeCall.id, success));
    } catch (error) {
      res.status(400).json(rpcError(rechargeCall.id, -32003, "Payment verification failed", {
        ...publicPaymentFailure(error)
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
    logger.error("error handling MCP request", logger.errorFields(error));
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
  if (rejectIfRateLimited(req, res)) {
    return;
  }

  const amount = String(req.body?.amount ?? "");
  const token = String(req.body?.token ?? DEFAULT_TRC20_TOKEN);
  let challenge;
  try {
    challenge = (await createRechargeChallenge({ amount, token, resourceUrl: requestResourceUrl(req) })).challenge;
  } catch (error) {
    res.status(400).json({
      error: "invalid_params",
      message: publicInvalidParams(error)
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
    const success = await settleRecharge({
      amount,
      token,
      paymentSignature,
      resourceUrl: requestResourceUrl(req)
    });
    res
      .status(responseStatus(success))
      .set(PAYMENT_RESPONSE_HEADER, encodePaymentResponseHeader(settlementFromPayload(success)))
      .json(success);
  } catch (error) {
    res.status(400).json({
      ...publicPaymentFailure(error)
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
  logger.error("unhandled request error", logger.errorFields(error));
  res.status(500).json({ error: "internal_server_error" });
});

const httpServer = app.listen(settings.port, settings.host, () => {
  logger.info("BANK OF AI Payment MCP Server Starting", {
    environment: settings.bankofaiEnv,
    network: networkConfig.name,
    depositAddress: networkConfig.bankofaiDepositAddress,
    mcpEndpoint: `http://${settings.host}:${settings.port}/mcp`,
    x402Endpoint: `http://${settings.host}:${settings.port}/x402/recharge`
  });
});

httpServer.on("error", (error) => {
  logger.error("failed to start server", logger.errorFields(error));
  process.exitCode = 1;
});

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => {
    httpServer.close(() => {
      process.exit(0);
    });
  });
}
