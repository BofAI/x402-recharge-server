"""AINFT Account Manager - MCP Server for x402 payment-required challenges."""

import base64
import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP

from src.config import network_config, settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize MCP server
# stateless_http=True makes streamable-http endpoints easier for external crawlers
# that do single-call JSON-RPC probing (e.g. 8004 auto_fetch).
mcp = FastMCP("ainft-account-manager", stateless_http=True)

# Network identifier
network_id = f"tron:{settings.network}"


def encode_payment_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


@mcp.tool()
def recharge(amount: str, token: str = "USDT") -> dict[str, Any]:
    """Return an x402 Payment Required challenge for AINFT recharge.

    Args:
        amount: Human-readable token amount (e.g. "1.5")
        token: Token symbol (e.g. TRX/USDT/USDD)
    Returns:
        Structured x402 challenge with status code 402 and PAYMENT-REQUIRED header.
    """
    token_symbol = token.upper().strip()
    token_cfg = network_config.get_token_info(token_symbol)
    if not token_cfg:
        raise ValueError(
            f"Unsupported token: {token_symbol}. Supported by network config: "
            f"{', '.join(sorted(network_config.tokens.keys()))}"
        )

    try:
        amount_dec = Decimal(amount)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {amount}") from exc
    if amount_dec <= 0:
        raise ValueError("Amount must be greater than 0.")

    decimals = int(token_cfg["decimals"])
    amount_smallest = int(amount_dec * (10**decimals))
    minimum_smallest = int(token_cfg["minimum"])
    if amount_smallest < minimum_smallest:
        raise ValueError(
            f"Amount below minimum. token={token_symbol}, minimum={minimum_smallest} "
            f"(smallest unit)."
        )

    # TRX is native token (no TRC20 contract address). Keep it as asset symbol and
    # use exact scheme so client-side tools that support native TRX can process it.
    if token_symbol == "TRX":
        scheme = "exact"
        asset_address = "TRX"
    else:
        scheme = "exact_permit"
        asset_address = token_cfg.get("address")
        if not asset_address:
            raise ValueError(f"Token contract address missing in config: {token_symbol}")

    challenge = {
        "x402Version": 2,
        "error": "Payment Required",
        "resource": {
            "url": f"ainft://recharge/{token_symbol.lower()}",
            "description": "AINFT recharge payment challenge",
            "mimeType": "application/json",
        },
        "accepts": [
            {
                "scheme": scheme,
                "network": network_id,
                "amount": str(amount_smallest),
                "asset": asset_address,
                "payTo": network_config.ainft_deposit_address,
            }
        ],
    }

    logger.info(
        "Generated x402 challenge: token=%s amount=%s network=%s pay_to=%s",
        token_symbol,
        amount_smallest,
        network_id,
        network_config.ainft_deposit_address,
    )
    return {
        "status_code": 402,
        "headers": {
            "PAYMENT-REQUIRED": encode_payment_payload(challenge),
        },
        "body": challenge,
        "message": "Use your x402 client tool to pay, then retry the business request.",
    }


@mcp.tool()
def get_balance(account_id: str = "") -> dict[str, str]:
    """Return AINFT balance query entry info.

    This service only provides x402 recharge challenge generation and does not
    hold user funds or maintain an authoritative AINFT balance ledger.
    """
    return {
        "account_id": account_id,
        "status": "redirect",
        "message": "Query balance from AINFT directly.",
        "ainft_web_url": network_config.ainft_web_url,
        "ainft_api_url": network_config.ainft_api_url,
    }


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("AINFT Account Manager MCP Server Starting")
    logger.info("=" * 60)
    logger.info(f"Network: {network_config.name}")
    logger.info(f"AINFT Deposit Address: {network_config.ainft_deposit_address}")
    logger.info("Tools: recharge, get_balance")
    logger.info("=" * 60)
    logger.info(f"MCP Streamable HTTP Endpoint: http://{settings.host}:{settings.port}/mcp")
    logger.info("=" * 60)

    # Run MCP server with Streamable HTTP transport
    app = mcp.streamable_http_app()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level
    )
