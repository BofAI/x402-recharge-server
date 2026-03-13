import "dotenv/config";
import express from "express";
import cors from "cors";
import { HTTPFacilitatorClient, x402ResourceServer } from "@bankofai/x402-core/server";
import { ExactTronScheme } from "@bankofai/x402-tvm/exact/server";
import { ExactEvmScheme } from "@bankofai/x402-evm/exact/server";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { z } from "zod";
import crypto from "crypto";

// Environment configurations
const PORT = Number(process.env.PORT ?? 8000);
const HOST = process.env.HOST ?? "0.0.0.0";
const PAY_TO_ADDRESS = (process.env.AINFT_DEPOSIT_ADDRESS ?? process.env.PAY_TO_ADDRESS) as string;
const BSC_PAY_TO_ADDRESS = (process.env.BSC_PAY_TO ?? "0x0B5D66620843DBA7eeb6819043c54484e92B5bD4") as string;
const FACILITATOR_URL = process.env.X402_FACILITATOR_URL ?? "http://localhost:8011";

if (!PAY_TO_ADDRESS) {
    console.error("Error: AINFT_DEPOSIT_ADDRESS or PAY_TO_ADDRESS is required");
    process.exit(1);
}

function getPayToAddress(network: string): string {
    return network.startsWith("eip155:") ? BSC_PAY_TO_ADDRESS : PAY_TO_ADDRESS;
}

// Map token symbols to contracts (Simplified for testnet/demo)
const TRON_TOKENS: Record<string, string> = {
    USDT: "TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf", // Nile USDT
};

const BSC_TOKENS: Record<string, `0x${string}`> = {
    USDT: "0x337610d27c682E347C9cD60BD4b3b107C9d34dDd", // BSC Testnet USDT
};

function getTokenAddress(network: string, token: string): string | null {
    const tokenUpper = token.toUpperCase();
    if (network.startsWith("tron:")) {
        return TRON_TOKENS[tokenUpper] || null;
    } else if (network.startsWith("eip155:")) {
        return BSC_TOKENS[tokenUpper] || null;
    }
    return null;
}

// Convert human readable amount to smallest atomic unit
// For simplicity we assume 6 decimals for USDT on Tron and 18 for BSC (typical, but adapt as needed)
function parseAmount(network: string, token: string, amountStr: string): string {
    const amountNum = parseFloat(amountStr);
    if (isNaN(amountNum) || amountNum <= 0) throw new Error("Invalid amount");

    // In a real app, fetch decimals from contract or config
    const isEVM = network.startsWith("eip155:");
    const decimals = isEVM ? 18 : 6;

    // Use BigInt for precise atomic conversion
    const multiplier = BigInt(10 ** decimals);
    // Simple conversion for demo, handle floating point carefully in prod
    const atomic = BigInt(Math.floor(amountNum * Number(multiplier)));
    return atomic.toString();
}

async function main() {
    const app = express();
    app.use(cors());
    app.use(express.json());

    const facilitatorClient = new HTTPFacilitatorClient({ url: FACILITATOR_URL });
    const server = new x402ResourceServer(facilitatorClient);

    // Register TRON networks
    server.register("tron:nile", new ExactTronScheme());
    server.register("tron:mainnet", new ExactTronScheme());

    // Register BSC networks
    server.register("eip155:97", new ExactEvmScheme());
    server.register("eip155:56", new ExactEvmScheme());

    try {
        await server.initialize();
        console.log(`[mcp] Synced with facilitator at ${FACILITATOR_URL}`);
    } catch (error) {
        console.warn(`[mcp] Could not sync with facilitator upfront: ${error}`);
        console.log("Will attempt lazy initialization on first request.");
    }


    // --- MCP Setup ---
    const mcpServer = new McpServer({
        name: "ainft-account-manager-ts",
        version: "1.0.0",
    });

    // Dummy tool just to have an MCP feature to expose
    mcpServer.tool("ping", "Free health check", {}, async () => ({
        content: [{ type: "text", text: "pong" }],
    }));

    // Define a single standard tool, but we will protect it in the HTTP layer
    mcpServer.tool(
        "ainft_pay",
        "Request an x402 token recharge challenge",
        {
            amount: z.string().describe("Amount to recharge"),
            token: z.string().default("USDT").describe("Token symbol to use"),
        },
        async (args: { amount: string; token: string }) => {
            // In the normal MCP flow, the 402 exception would be thrown here if unpaid,
            // or bypassed if paid. But since we use an express middleware/route for 
            // /x402/recharge, this tool just returns a success if it somehow gets called directly.
            return {
                content: [{ type: "text", text: `Recharge simulation passed for ${args.amount} ${args.token}` }],
            };
        }
    );

    const transports = new Map<string, SSEServerTransport>();

    // Expose MCP SSE endpoint
    app.get("/mcp", async (_req, res) => {
        const transport = new SSEServerTransport("/mcp/messages", res);
        const sessionId = crypto.randomUUID();
        transports.set(sessionId, transport);
        res.on("close", () => transports.delete(sessionId));
        await mcpServer.connect(transport);
    });

    app.post("/mcp/messages", async (req, res) => {
        const transport = Array.from(transports.values())[0];
        if (!transport) {
            res.status(400).json({ error: "No active SSE connection" });
            return;
        }
        await transport.handlePostMessage(req, res, req.body);
    });


    // --- REST /x402/recharge Protocol Endpoint ---
    // This endpoint accepts an arbitrary payment and returns exactly 402 Payment Required
    // or 200 Success if a valid PAYMENT-SIGNATURE is provided.
    app.post("/x402/recharge", async (req, res) => {
        const amount = req.body?.amount || req.query.amount;
        const token = (req.body?.token || req.query.token || "USDT") as string;
        const network = (req.body?.network || req.query.network || "tron:nile") as string;

        if (!amount) {
            return res.status(400).json({ error: "amount is required" });
        }

        const tokenAddress = getTokenAddress(network, token);
        if (!tokenAddress) {
            return res.status(400).json({ error: `Unsupported token ${token} on network ${network}` });
        }

        let atomicAmount: string;
        try {
            atomicAmount = parseAmount(network, token, String(amount));
        } catch (e) {
            return res.status(400).json({ error: "Invalid amount format" });
        }

        // Build requirements dynamically based on the requested amount
        let accepts;
        try {
            accepts = await server.buildPaymentRequirements({
                scheme: "exact",
                network: network as any, // "tron:nile" | "eip155:97" | etc
                payTo: getPayToAddress(network),
                price: {
                    amount: atomicAmount,
                    asset: tokenAddress as string,
                    extra: {
                        name: "Tether USD",
                        version: "1"
                    }
                }
            });
        } catch (error: any) {
            return res.status(400).json({ error: "Failed to build payment requirements", details: error.message });
        }

        const challenge = {
            x402Version: 2,
            error: "Payment Required",
            resource: {
                url: req.originalUrl,
                description: "AINFT recharge payment challenge",
            },
            accepts
        };

        const signature = req.headers["payment-signature"] as string;

        if (!signature) {
            const encoded = Buffer.from(JSON.stringify(challenge)).toString("base64");
            res.setHeader("PAYMENT-REQUIRED", encoded);
            return res.status(402).json(challenge);
        }

        // Settle the payment
        try {
            const payload = JSON.parse(Buffer.from(signature, 'base64').toString('utf8'));
            const verification = await server.verifyPayment(payload, challenge.accepts[0] as any);
            if (!verification.isValid) {
                return res.status(400).json({ error: "Payment verification failed", details: verification.invalidReason });
            }

            const settlement = await server.settlePayment(payload, challenge.accepts[0] as any);
            if (!settlement.success) {
                return res.status(400).json({ error: "Payment settlement failed", details: settlement.errorReason });
            }

            // Paid successfully!
            const successPayload = {
                status: "paid",
                recharge_status: "success",
                message: "Recharge successful.",
                transaction_hash: settlement.transaction,
                amount: amount,
                token: token.toUpperCase(),
                network: network,
                pay_to: PAY_TO_ADDRESS,
                verified: true,
                settlement: settlement
            };

            return res.status(200).json(successPayload);

        } catch (error: any) {
            console.error("Payment processing error:", error);
            return res.status(400).json({ error: "Invalid payment format or internal error", details: error.message });
        }

    });

    app.listen(PORT, HOST, () => {
        console.log("=".repeat(60));
        console.log("AINFT Merchant Agent (TS) - Started");
        console.log("=".repeat(60));
        console.log(`  Port:        ${PORT}`);
        console.log(`  Facilitator: ${FACILITATOR_URL}`);
        console.log(`  Pay To:      ${PAY_TO_ADDRESS}`);
        console.log(`  MCP SSE:     http://${HOST}:${PORT}/mcp`);
        console.log(`  x402:        http://${HOST}:${PORT}/x402/recharge`);
        console.log("=".repeat(60));
    });
}

main().catch((error) => {
    console.error("Fatal error:", error);
    process.exit(1);
});
