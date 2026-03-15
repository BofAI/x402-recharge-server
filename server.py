"""AINFT Account Manager - MCP server for payee-side x402 challenges."""

import base64
import json
import logging
import time
import uuid
from enum import Enum
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from mcp.server.fastmcp import Context, FastMCP
from starlette.responses import JSONResponse

from src.config import network_config, settings

try:
    from bankofai.x402.encoding import decode_payment_payload
    from bankofai.x402.facilitator import FacilitatorClient
    from bankofai.x402.types import PaymentPayload, PaymentRequirements
except ImportError:
    import sys
    from pathlib import Path

    fallback = Path(__file__).resolve().parent.parent / "x402" / "python" / "x402" / "src"
    if fallback.exists():
        sys.path.insert(0, str(fallback))
    from bankofai.x402.encoding import decode_payment_payload
    from bankofai.x402.facilitator import FacilitatorClient
    from bankofai.x402.types import PaymentPayload, PaymentRequirements


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

network_id = f"tron:{settings.network}"
PAYMENT_REQUIRED_HEADER = "PAYMENT-REQUIRED"
PAYMENT_SIGNATURE_HEADER = "PAYMENT-SIGNATURE"
PAYMENT_RESPONSE_HEADER = "PAYMENT-RESPONSE"
BILL_URL = f"{network_config.ainft_web_url.rstrip('/')}/purchase"
ALLOWED_TRC20_TOKENS = {"USDT", "USDD"}


def _create_facilitator_headers() -> dict[str, dict[str, str]]:
    if not settings.facilitator_api_key:
        return {}
    return {"X-API-KEY": settings.facilitator_api_key}


_facilitator = FacilitatorClient(
    settings.x402_facilitator_url,
    headers=_create_facilitator_headers(),
)


def _build_trc20_enum() -> type[Enum]:
    token_map = {
        symbol: symbol
        for symbol, cfg in network_config.tokens.items()
        if symbol.upper() in ALLOWED_TRC20_TOKENS and cfg.get("address")
    }
    if not token_map:
        raise RuntimeError("No TRC20 tokens configured for current network")
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
    # TRON explorers commonly support /#/transaction/<txid>
    return f"{base}/#/transaction/{tx_hash}"


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


def _supported_trc20_tokens() -> str:
    return ", ".join(sorted(TRC20Token.__members__.keys()))


def _normalize_trc20_token(token: str) -> str:
    token_symbol = token.upper().strip()
    if token_symbol not in TRC20Token.__members__:
        raise ValueError(f"Unsupported TRC20 token: {token_symbol}. Supported: {_supported_trc20_tokens()}")
    return token_symbol


async def _build_trc20_recharge_challenge(amount: str, token: str, resource_url: str) -> dict[str, Any]:
    token_symbol = _normalize_trc20_token(token)
    token_cfg = network_config.get_token_info(token_symbol)
    if not token_cfg:
        raise ValueError(f"Token config missing for supported TRC20 token: {token_symbol}")

    decimals = int(token_cfg["decimals"])
    amount_smallest = _to_smallest_unit(amount, decimals)
    minimum_smallest = int(token_cfg["minimum"])
    if amount_smallest < minimum_smallest:
        raise ValueError(
            "Amount below minimum. "
            f"token={token_symbol}, minimum={minimum_smallest} (smallest unit)."
        )

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

    req = PaymentRequirements(
        scheme=accept_item["scheme"],
        network=accept_item["network"],
        amount=accept_item["amount"],
        asset=accept_item["asset"],
        payTo=accept_item["payTo"],
        maxTimeoutSeconds=3600,
    )
    fee_quotes = await _facilitator.fee_quote([req])
    if fee_quotes:
        fee = fee_quotes[0].fee.model_dump(by_alias=True)
        fee.setdefault("facilitatorId", _facilitator.facilitator_id)
        accept_item["extra"] = {"fee": fee}

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
    payload = decode_payment_payload(payment_signature, PaymentPayload)

    verify_result = await _facilitator.verify(payload, requirements)
    if not verify_result.is_valid:
        raise ValueError(f"facilitator verify failed: {verify_result.invalid_reason}")

    settle_result = await _facilitator.settle(payload, requirements)
    if not settle_result.success:
        raise ValueError(f"facilitator settle failed: {settle_result.error_reason}")
    return settle_result.model_dump(by_alias=True)


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
        token = DEFAULT_TRC20_TOKEN
        rpc_id: Any = None
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            rpc_id = payload.get("id")
            params = payload.get("params") or {}
            arguments = params.get("arguments") or {}
            tool_name = str(params.get("name", ""))
            if payload.get("method") == "tools/call" and tool_name == "recharge":
                amount = str(arguments.get("amount", ""))
                token = str(arguments.get("token", DEFAULT_TRC20_TOKEN))
                intercept = True
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
                success = _build_success_payload(
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
async def recharge(amount: str, token: str = DEFAULT_TRC20_TOKEN, ctx: Context | None = None) -> dict[str, Any]:
    """TRC20 recharge tool for AINFT (x402 required).

    Note: real x402 HTTP 402/headers are enforced by MCPRecharge402Middleware.
    """
    payment_signature = None
    if ctx and ctx.request_context.request is not None:
        payment_signature = ctx.request_context.request.headers.get(PAYMENT_SIGNATURE_HEADER)

    try:
        token_symbol = _normalize_trc20_token(token)
    except ValueError as exc:
        return {
            "status": "invalid_token",
            "message": str(exc),
        }

    challenge = await _build_trc20_recharge_challenge(
        amount=amount,
        token=token_symbol,
        resource_url="/mcp tools/call recharge",
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
        return _build_success_payload(
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


@mcp.custom_route("/x402/recharge", methods=["POST"])
async def x402_recharge(request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    amount = str(payload.get("amount", ""))
    token = str(payload.get("token", DEFAULT_TRC20_TOKEN))
    payment_signature = request.headers.get(PAYMENT_SIGNATURE_HEADER)
    try:
        token_symbol = _normalize_trc20_token(token)
        challenge = await _build_trc20_recharge_challenge(
            amount=amount,
            token=token_symbol,
            resource_url=str(request.url),
        )
    except ValueError as exc:
        return JSONResponse(
            content={
                "error": "invalid_params",
                "message": str(exc),
            },
            status_code=400,
        )

    if not payment_signature:
        return JSONResponse(
            content=challenge,
            status_code=402,
            headers={PAYMENT_REQUIRED_HEADER: _encode_payment_payload(challenge)},
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
    success = _build_success_payload(
        tx_hash=tx_hash,
        token=token_symbol,
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
    logger.info("Environment: %s", settings.ainft_env)
    logger.info("Network: %s", network_config.name)
    logger.info("AINFT Deposit Address: %s", network_config.ainft_deposit_address)
    logger.info("Tools: recharge")
    logger.info("MCP Streamable HTTP Endpoint: http://%s:%s/mcp", settings.host, settings.port)
    logger.info("x402 HTTP Endpoint: http://%s:%s/x402/recharge", settings.host, settings.port)
    logger.info("x402 TRC20 HTTP Endpoint: http://%s:%s/x402/trc20/recharge", settings.host, settings.port)
    logger.info("=" * 60)

    app = MCPRecharge402Middleware(mcp.streamable_http_app())
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)
