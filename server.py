"""AINFT Account Manager - MCP server for payee-side x402 challenges."""

import base64
import json
import logging
import time
import uuid
import asyncio
from enum import Enum
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

import httpx
from mcp.server.fastmcp import Context, FastMCP
from starlette.responses import JSONResponse

from src.config import network_config, settings

try:
    from bankofai.x402.http import (
        HTTPFacilitatorClient,
        FacilitatorConfig,
        decode_payment_signature_header,
    )
    from bankofai.x402.schemas import PaymentRequirements
except ImportError:
    import sys

    fallback = Path(__file__).resolve().parent.parent / "x402" / "python" / "x402" / "src"
    if fallback.exists():
        sys.path.insert(0, str(fallback))
    from bankofai.x402.http import (
        HTTPFacilitatorClient,
        FacilitatorConfig,
        decode_payment_signature_header,
    )
    from bankofai.x402.schemas import PaymentRequirements


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "ainft-account-manager",
    stateless_http=True,
    host=settings.host,
    port=settings.port,
)

if network_config.chain_family == "tron":
    network_id = f"tron:{settings.network}"
elif network_config.chain_family == "eip155":
    network_id = f"eip155:{network_config.chain_id}"
else:
    raise RuntimeError(f"Unsupported chain family: {network_config.chain_family}")

PAYMENT_REQUIRED_HEADER = "PAYMENT-REQUIRED"
PAYMENT_SIGNATURE_HEADER = "PAYMENT-SIGNATURE"
PAYMENT_RESPONSE_HEADER = "PAYMENT-RESPONSE"
BILL_URL = f"{network_config.ainft_web_url.rstrip('/')}/purchase"

_facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.x402_facilitator_url))


def _build_trc20_enum() -> type[Enum]:
    native_symbol = "TRX" if network_config.chain_family == "tron" else "BNB"
    token_map = {
        symbol: symbol
        for symbol, cfg in network_config.tokens.items()
        if symbol.upper() != native_symbol and cfg.get("address")
    }
    if not token_map:
        raise RuntimeError("No x402 token contracts configured for current network")
    return Enum("TRC20Token", token_map, type=str)


TRC20Token = _build_trc20_enum()
DEFAULT_TRC20_TOKEN = "USDT" if "USDT" in TRC20Token.__members__ else next(iter(TRC20Token.__members__))


def _encode_payment_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def _payment_failure_details(exc: Exception) -> dict[str, str]:
    raw = str(exc).strip() or exc.__class__.__name__
    stage = "unknown"
    reason = raw
    if raw.startswith("facilitator verify failed:"):
        stage = "verify"
        reason = raw.split(":", 1)[1].strip() or "invalid_payment_signature"
    elif raw.startswith("facilitator settle failed:"):
        stage = "settle"
        reason = raw.split(":", 1)[1].strip() or "transaction_failed_on_chain"
    return {"stage": stage, "reason": reason, "raw": raw}


def _tx_explorer_url(tx_hash: str) -> str:
    base = network_config.explorer.rstrip("/")
    if network_config.chain_family == "tron":
        return f"{base}/#/transaction/{tx_hash}"
    return f"{base}/tx/{tx_hash}"


def _to_smallest_unit(amount: str, decimals: int) -> int:
    try:
        amount_dec = Decimal(amount)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {amount}") from exc

    if amount_dec <= 0:
        raise ValueError("Amount must be greater than 0.")

    multiplier = Decimal(10) ** decimals
    smallest = amount_dec * multiplier
    if smallest != smallest.to_integral_value():
        raise ValueError(f"Amount precision exceeds token decimals ({decimals}).")
    return int(smallest)


async def _build_trc20_recharge_challenge(amount: str, token: str, resource_url: str) -> dict[str, Any]:
    token_symbol = token.upper().strip()
    token_cfg = network_config.get_token_info(token_symbol)
    if not token_cfg:
        supported = ", ".join(sorted(network_config.tokens.keys()))
        raise ValueError(f"Unsupported token: {token_symbol}. Supported: {supported}")

    decimals = int(token_cfg["decimals"])
    amount_smallest = _to_smallest_unit(amount, decimals)
    minimum_smallest = int(token_cfg["minimum"])
    if amount_smallest < minimum_smallest:
        raise ValueError(
            "Amount below minimum. "
            f"token={token_symbol}, minimum={minimum_smallest} (smallest unit)."
        )

    if token_symbol in {"TRX", "BNB"}:
        raise ValueError(f"Native coin {token_symbol} is not supported by this MCP service")

    scheme = "exact_permit"
    asset = token_cfg.get("address")
    if not asset:
        raise ValueError(f"Token contract address missing in config: {token_symbol}")

    accept_item: dict[str, Any] = {
        "scheme": scheme,
        "network": network_id,
        "amount": str(amount_smallest),
        "asset": asset,
        "payTo": network_config.ainft_deposit_address,
    }

    challenge = {
        "x402Version": 2,
        "error": "Payment Required",
        "resource": {
            "url": resource_url,
            "description": "AINFT recharge payment challenge",
            "mimeType": "application/json",
        },
        "accepts": [accept_item],
        "extensions": {
            "paymentPermitContext": {
                "meta": {
                    "kind": "PAYMENT_ONLY",
                    "paymentId": "0x" + uuid.uuid4().hex[:32],
                    "nonce": str(uuid.uuid4().int),
                    "validAfter": int(time.time()),
                    "validBefore": int(time.time()) + 3600,
                }
            }
        },
    }
    logger.info(
        "Generated x402 challenge token=%s amount=%s network=%s pay_to=%s resource=%s",
        token_symbol,
        amount_smallest,
        network_id,
        network_config.ainft_deposit_address,
        resource_url,
    )
    return challenge


def _build_success_payload(
    *,
    tx_hash: str,
    token: str,
    amount: str,
    settlement: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    tx_url = _tx_explorer_url(tx_hash) if tx_hash else ""
    return {
        "status": "paid",
        "recharge_status": "success",
        "mode": mode,
        "message": (
            f"Recharge successful. View your bill at {BILL_URL}. "
            f"Transaction: {tx_url}"
        ) if tx_url else f"Recharge successful. View your bill at {BILL_URL}",
        "bill_url": BILL_URL,
        "transaction_hash": tx_hash,
        "transaction_url": tx_url,
        "token": token.upper(),
        "amount": amount,
        "pay_to": network_config.ainft_deposit_address,
        "network": network_id,
        "verified": True,
        "settlement": settlement,
    }


def _to_payment_requirements(challenge: dict[str, Any]) -> PaymentRequirements:
    accepted = challenge["accepts"][0]
    return PaymentRequirements(
        scheme=accepted["scheme"],
        network=accepted["network"],
        amount=accepted["amount"],
        asset=accepted["asset"],
        payTo=accepted["payTo"],
        maxTimeoutSeconds=3600,
    )


async def _settle_with_facilitator(payment_signature: str, challenge: dict[str, Any]) -> dict[str, Any]:
    requirements = _to_payment_requirements(challenge)
    payload = decode_payment_signature_header(payment_signature)

    verify_result = await _facilitator.verify(payload, requirements)
    if not verify_result.is_valid:
        raise ValueError(f"facilitator verify failed: {verify_result.invalid_reason}")

    settle_result = await _facilitator.settle(payload, requirements)
    if not settle_result.success:
        raise ValueError(f"facilitator settle failed: {settle_result.error_reason}")
    return settle_result.model_dump(by_alias=True)


async def _confirm_topup_completion(tx_hash: str) -> dict[str, Any]:
    merchant_id = (settings.ainft_merchant_id or "").strip()
    merchant_key = (settings.ainft_merchant_key or "").strip()
    if not merchant_id or not merchant_key:
        return {
            "enabled": False,
            "status": "skipped",
            "reason": "missing_ainft_merchant_credentials",
        }

    base = network_config.ainft_api_url.rstrip("/")
    endpoint = (settings.ainft_topup_confirm_url or f"{base}/m/credit/recharge").strip()
    confirm_chain = (network_config.confirm_chain or "").strip()
    if not confirm_chain:
        return {
            "enabled": False,
            "status": "skipped",
            "reason": "confirmation_chain_not_configured",
        }
    timeout_sec = max(1.0, settings.ainft_topup_confirm_timeout_ms / 1000.0)
    retries = max(1, int(settings.ainft_topup_confirm_retries))
    interval_sec = max(0.0, settings.ainft_topup_confirm_interval_ms / 1000.0)

    headers = {
        "content-type": "application/json",
        "accept": "application/json",
        "X-Merchant-Id": merchant_id,
        "X-Merchant-Key": merchant_key,
    }
    payload = {
        "chain": confirm_chain,
        "tx_hash": tx_hash,
    }

    last_http_status: int | None = None
    last_body: Any = None
    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        for i in range(retries):
            try:
                resp = await client.post(endpoint, json=payload, headers=headers)
                last_http_status = resp.status_code
                text = resp.text
                try:
                    body = resp.json() if text else {}
                except Exception:
                    body = {"raw": text}
                last_body = body

                if resp.status_code == 200 and isinstance(body, dict):
                    status = body.get("status")
                    if status == "paid":
                        return {
                            "enabled": True,
                            "status": "confirmed",
                            "http_status": resp.status_code,
                            "attempt": i + 1,
                            "endpoint": endpoint,
                            "result": body,
                        }
                    if status == "pending":
                        last_body = body

                if i < retries - 1:
                    await asyncio.sleep(interval_sec)
            except Exception as exc:
                last_body = {"error": str(exc)}
                if i < retries - 1:
                    await asyncio.sleep(interval_sec)

    return {
        "enabled": True,
        "status": "not_confirmed",
        "endpoint": endpoint,
        "attempts": retries,
        "http_status": last_http_status,
        "last_response": last_body,
    }


async def _build_success_payload_with_confirmation(
    *,
    tx_hash: str,
    token: str,
    amount: str,
    settlement: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    payload = _build_success_payload(
        tx_hash=tx_hash,
        token=token,
        amount=amount,
        settlement=settlement,
        mode=mode,
    )
    payload["topup_confirmation"] = await _confirm_topup_completion(tx_hash)
    return payload


class MCPRecharge402Middleware:
    """ASGI middleware: return real HTTP 402 for unpaid MCP recharge calls."""

    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        if scope.get("path") != "/mcp":
            await self.app(scope, receive, send)
            return

        body = b""
        captured_messages: list[dict[str, Any]] = []
        while True:
            message = await receive()
            captured_messages.append(message)
            if message.get("type") != "http.request":
                break
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break

        headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])}
        payment_signature = headers.get(PAYMENT_SIGNATURE_HEADER.lower())

        intercept = False
        tool_name = ""
        amount = ""
        token = "USDT"
        rpc_id: Any = None
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            rpc_id = payload.get("id")
            params = payload.get("params") or {}
            arguments = params.get("arguments") or {}
            tool_name = str(params.get("name", ""))
            if payload.get("method") == "tools/call" and tool_name in {"ainft_pay_trc20", "ainft_pay_erc20", "recharge"}:
                amount = str(arguments.get("amount", ""))
                token = str(arguments.get("token", "USDT"))
                # native coin flows do not go through x402 middleware.
                intercept = token.upper().strip() not in {"TRX", "BNB"}
        except Exception:
            intercept = False

        if intercept:
            def _rpc_result(result: dict[str, Any]) -> bytes:
                return json.dumps(
                    {"jsonrpc": "2.0", "id": rpc_id, "result": result},
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")

            def _rpc_error(code: int, message: str, data: dict[str, Any] | None = None) -> bytes:
                err: dict[str, Any] = {"code": code, "message": message}
                if data is not None:
                    err["data"] = data
                return json.dumps(
                    {"jsonrpc": "2.0", "id": rpc_id, "error": err},
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")

            try:
                challenge = await _build_trc20_recharge_challenge(
                    amount=amount,
                    token=token,
                    resource_url=f"/mcp tools/call {tool_name}",
                )
            except Exception as exc:
                fallback = _rpc_error(
                    code=-32602,
                    message="Invalid params",
                    data={"error": str(exc)},
                )
                await send(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": fallback})
                return

            if not payment_signature:
                response_body = _rpc_error(
                    code=-32002,
                    message="Payment Required",
                    data={"x402": challenge},
                )
                await send(
                    {
                        "type": "http.response.start",
                        "status": 402,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (PAYMENT_REQUIRED_HEADER.lower().encode("ascii"), _encode_payment_payload(challenge).encode("ascii")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": response_body})
                return

            try:
                settle_result = await _settle_with_facilitator(payment_signature, challenge)
                tx_hash = str(settle_result.get("transaction", ""))
                success = await _build_success_payload_with_confirmation(
                    tx_hash=tx_hash,
                    token=token,
                    amount=amount,
                    settlement=settle_result,
                    mode="trc20_x402",
                )
                response_body = _rpc_result(success)
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (PAYMENT_RESPONSE_HEADER.lower().encode("ascii"), _encode_payment_payload(success).encode("ascii")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": response_body})
            except Exception as exc:
                details = _payment_failure_details(exc)
                response_body = _rpc_error(
                    code=-32003,
                    message="Payment verification failed",
                    data={
                        "error": "payment_verification_failed",
                        "failure_stage": details["stage"],
                        "failure_reason": details["reason"],
                        "detail": details["raw"],
                        "message": "Provided payment is invalid or settlement failed. Create a new payment and retry.",
                    },
                )
                await send(
                    {
                        "type": "http.response.start",
                        "status": 400,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": response_body})
            return

        async def replay_receive():
            if captured_messages:
                return captured_messages.pop(0)
            return await receive()

        await self.app(scope, replay_receive, send)


@mcp.tool()
async def ainft_pay_trc20(
    amount: str,
    token: TRC20Token = TRC20Token[DEFAULT_TRC20_TOKEN],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Token recharge tool for AINFT over x402.

    TRON networks use TRC20 assets; EVM networks should prefer `ainft_pay_erc20`.
    Note: real x402 HTTP 402/headers are enforced by MCPRecharge402Middleware.
    """
    payment_signature = None
    if ctx and ctx.request_context.request is not None:
        payment_signature = ctx.request_context.request.headers.get(PAYMENT_SIGNATURE_HEADER)

    token_symbol = token.value

    challenge = await _build_trc20_recharge_challenge(
        amount=amount,
        token=token_symbol,
        resource_url="/mcp tools/call ainft_pay_trc20",
    )
    if payment_signature:
        try:
            settle_result = await _settle_with_facilitator(payment_signature, challenge)
        except Exception as exc:
            details = _payment_failure_details(exc)
            return {
                "status": "payment_verification_failed",
                "error": "payment_verification_failed",
                "failure_stage": details["stage"],
                "failure_reason": details["reason"],
                "detail": details["raw"],
                "message": "Provided payment is invalid or settlement failed. Create a new payment and retry.",
            }
        tx_hash = str(settle_result.get("transaction", ""))
        return await _build_success_payload_with_confirmation(
            tx_hash=tx_hash,
            token=token_symbol,
            amount=amount,
            settlement=settle_result,
            mode="trc20_x402",
        )
    return {
        "status": "payment_required",
        "message": "Payment required. Call this tool through MCP HTTP /mcp to receive standard x402 402 headers.",
        "x402": challenge,
        "retry_hint": "Retry the same MCP tool call with PAYMENT-SIGNATURE header after payment.",
    }


@mcp.tool()
async def ainft_pay_erc20(
    amount: str,
    token: TRC20Token = TRC20Token[DEFAULT_TRC20_TOKEN],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """ERC20 recharge tool for AINFT over x402 (EVM networks)."""
    if network_config.chain_family != "eip155":
        return {
            "status": "unsupported_network",
            "message": f"Current network {settings.network} is not an EVM network.",
        }
    return await ainft_pay_trc20(amount=amount, token=token, ctx=ctx)


@mcp.tool()
async def recharge(
    amount: str,
    token: str = "USDT",
    txid: str = "",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Deprecated compatibility alias. Use ainft_pay_trc20 / ainft_pay_erc20 instead."""
    token_symbol = token.upper().strip()
    if token_symbol not in TRC20Token.__members__:
        supported = ", ".join(TRC20Token.__members__.keys())
        return {
            "status": "invalid_token",
            "message": (
                f"Unsupported token: {token_symbol}. "
                f"Supported x402 tokens on this network: {supported}"
            ),
        }
    if network_config.chain_family == "eip155":
        return await ainft_pay_erc20(amount=amount, token=TRC20Token[token_symbol], ctx=ctx)
    return await ainft_pay_trc20(amount=amount, token=TRC20Token[token_symbol], ctx=ctx)


@mcp.tool()
def get_balance(account_id: str = "") -> dict[str, Any]:
    """Deprecated in server; moved to local ainft-skill."""
    return {
        "account_id": account_id,
        "status": "moved_to_skill",
        "message": "This query is handled in local ainft-skill using user API key.",
        "ainft_skill": {
            "queries": ["balance", "quota"],
            "auth": "Authorization: Bearer <AINFT_API_KEY>",
        },
    }


@mcp.custom_route("/x402/recharge", methods=["POST"])
async def x402_recharge(request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    amount = str(payload.get("amount", ""))
    token = str(payload.get("token", "USDT"))
    payment_signature = request.headers.get(PAYMENT_SIGNATURE_HEADER)

    if token.upper().strip() in {"TRX", "BNB"}:
        return JSONResponse(
            content={
                "error": "unsupported_via_x402",
                "message": "Native TRX and BNB recharge flows are disabled. Use supported x402 tokens only.",
            },
            status_code=400,
        )

    if not payment_signature:
        challenge = await _build_trc20_recharge_challenge(
            amount=amount,
            token=token,
            resource_url=str(request.url),
        )
        return JSONResponse(
            content=challenge,
            status_code=402,
            headers={PAYMENT_REQUIRED_HEADER: _encode_payment_payload(challenge)},
        )

    challenge = await _build_trc20_recharge_challenge(
        amount=amount,
        token=token,
        resource_url=str(request.url),
    )
    try:
        settle_result = await _settle_with_facilitator(payment_signature, challenge)
    except Exception as exc:
        details = _payment_failure_details(exc)
        return JSONResponse(
            content={
                "error": "payment_verification_failed",
                "failure_stage": details["stage"],
                "failure_reason": details["reason"],
                "detail": details["raw"],
                "message": "Provided payment is invalid or settlement failed. Create a new payment and retry.",
            },
            status_code=400,
        )

    tx_hash = str(settle_result.get("transaction", ""))
    success = await _build_success_payload_with_confirmation(
        tx_hash=tx_hash,
        token=token,
        amount=amount,
        settlement=settle_result,
        mode="trc20_x402",
    )
    return JSONResponse(
        content=success,
        status_code=200,
        headers={PAYMENT_RESPONSE_HEADER: _encode_payment_payload(success)},
    )


@mcp.custom_route("/x402/trc20/recharge", methods=["POST"])
async def x402_trc20_recharge(request) -> JSONResponse:
    """Alias route for explicit TRC20 x402 payment flow."""
    return await x402_recharge(request)


if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("AINFT Account Manager MCP Server Starting")
    logger.info("Network: %s", network_config.name)
    logger.info("AINFT Deposit Address: %s", network_config.ainft_deposit_address)
    logger.info("Tools: ainft_pay_trc20, ainft_pay_erc20, recharge(compat), get_balance(redirect)")
    logger.info("MCP Streamable HTTP Endpoint: http://%s:%s/mcp", settings.host, settings.port)
    logger.info("x402 HTTP Endpoint: http://%s:%s/x402/recharge", settings.host, settings.port)
    logger.info("x402 TRC20 HTTP Endpoint: http://%s:%s/x402/trc20/recharge", settings.host, settings.port)
    logger.info("=" * 60)

    app = MCPRecharge402Middleware(mcp.streamable_http_app())
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)
