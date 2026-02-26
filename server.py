"""AINFT Account Manager - MCP server for payee-side x402 challenges."""

import base64
import json
import logging
import time
import uuid
import asyncio
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

import httpx
from mcp.server.fastmcp import Context, FastMCP
from starlette.responses import JSONResponse

from src.config import network_config, settings

try:
    from bankofai.x402.address import TronAddressConverter
    from bankofai.x402.encoding import decode_payment_payload
    from bankofai.x402.facilitator import FacilitatorClient
    from bankofai.x402.types import PaymentPayload, PaymentRequirements
except ImportError:
    import sys
    from pathlib import Path

    fallback = Path(__file__).resolve().parent.parent / "x402" / "python" / "x402" / "src"
    if fallback.exists():
        sys.path.insert(0, str(fallback))
    from bankofai.x402.address import TronAddressConverter
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
TRX_TXID_HEADER = "X-TRX-TXID"
BILL_URL = "https://chat.ainft.com/purchase"

_facilitator = FacilitatorClient(settings.x402_facilitator_url)
_tron_addr = TronAddressConverter()


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


async def _build_recharge_challenge(amount: str, token: str, resource_url: str) -> dict[str, Any]:
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

    if token_symbol == "TRX":
        scheme = "exact"
        asset = "TRX"
    else:
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

    if scheme != "exact":
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


async def _tron_rpc_post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{network_config.rpc_url.rstrip('/')}{endpoint}"
    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json() if resp.content else {}


async def _verify_native_trx_transfer(
    txid: str, expected_to: str, expected_amount_sun: int
) -> tuple[bool, str]:
    if not txid:
        return False, "missing_txid"
    try:
        tx = await _tron_rpc_post("/wallet/gettransactionbyid", {"value": txid})
        if not tx or not tx.get("txID"):
            return False, "tx_not_found"

        contracts = ((tx.get("raw_data") or {}).get("contract") or [])
        if not contracts:
            return False, "missing_contract"
        c0 = contracts[0] or {}
        if c0.get("type") != "TransferContract":
            return False, f"unsupported_contract_type:{c0.get('type')}"

        value = ((c0.get("parameter") or {}).get("value") or {})
        to_hex = str(value.get("to_address", ""))
        amount = int(value.get("amount", 0))
        to_base58 = _tron_addr.normalize(to_hex) if to_hex else ""

        if to_base58 != expected_to:
            return False, f"to_mismatch:{to_base58}"
        if amount < expected_amount_sun:
            return False, f"amount_too_small:{amount}"

        # Poll for confirmation briefly; TronGrid may lag immediately after broadcast.
        for _ in range(8):
            tx_info = await _tron_rpc_post("/wallet/gettransactioninfobyid", {"value": txid})
            receipt = tx_info.get("receipt") or {}
            result = receipt.get("result")
            if result == "SUCCESS":
                return True, "ok_confirmed"
            if result and result != "SUCCESS":
                return False, f"receipt_not_success:{result}"
            await asyncio.sleep(1)

        # Fallback: accept broadcast-level success when receipt is not yet indexed.
        ret = (tx.get("ret") or [{}])[0]
        if ret.get("contractRet") == "SUCCESS":
            return True, "ok_broadcast_success"
        return False, "receipt_missing"
    except Exception as exc:
        return False, f"verify_error:{exc}"


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
        trx_txid = headers.get(TRX_TXID_HEADER.lower())

        intercept = False
        amount = ""
        token = "USDT"
        rpc_id: Any = None
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            rpc_id = payload.get("id")
            params = payload.get("params") or {}
            arguments = params.get("arguments") or {}
            if payload.get("method") == "tools/call" and params.get("name") == "recharge":
                intercept = True
                amount = str(arguments.get("amount", ""))
                token = str(arguments.get("token", "USDT"))
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
                challenge = await _build_recharge_challenge(
                    amount=amount,
                    token=token,
                    resource_url="/mcp tools/call recharge",
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
                if token.upper().strip() == "TRX" and trx_txid:
                    req = challenge["accepts"][0]
                    ok, reason = await _verify_native_trx_transfer(
                        txid=trx_txid,
                        expected_to=req["payTo"],
                        expected_amount_sun=int(req["amount"]),
                    )
                    if ok:
                        tx_url = _tx_explorer_url(trx_txid)
                        success = {
                            "status": "paid",
                            "recharge_status": "success",
                            "message": (
                                f"Recharge successful. View your bill at {BILL_URL}. "
                                f"Transaction: {tx_url}"
                            ),
                            "bill_url": BILL_URL,
                            "transaction_hash": trx_txid,
                            "transaction_url": tx_url,
                            "token": "TRX",
                            "amount": amount,
                            "pay_to": network_config.ainft_deposit_address,
                            "network": network_id,
                            "verified": True,
                            "settlement": {
                                "success": True,
                                "transaction": trx_txid,
                                "network": network_id,
                                "mode": "native_trx_fallback",
                            },
                        }
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
                        return
                    logger.warning("TRX fallback tx verify failed: %s txid=%s", reason, trx_txid)

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
                tx_url = _tx_explorer_url(tx_hash) if tx_hash else ""
                success = {
                    "status": "paid",
                    "recharge_status": "success",
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
                    "settlement": settle_result,
                }
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
async def recharge(
    amount: str,
    token: str = "USDT",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Recharge tool for AINFT.

    Note: real x402 HTTP 402/headers are enforced by MCPRecharge402Middleware.
    """
    payment_signature = None
    if ctx and ctx.request_context.request is not None:
        payment_signature = ctx.request_context.request.headers.get(PAYMENT_SIGNATURE_HEADER)

    challenge = await _build_recharge_challenge(
        amount=amount,
        token=token,
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
        tx_url = _tx_explorer_url(tx_hash) if tx_hash else ""
        return {
            "status": "paid",
            "recharge_status": "success",
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
            "settlement": settle_result,
        }
    return {
        "status": "payment_required",
        "message": "Payment required. Call this tool through MCP HTTP /mcp to receive standard x402 402 headers.",
        "x402": challenge,
        "retry_hint": "Retry the same MCP tool call with PAYMENT-SIGNATURE header after payment.",
    }


@mcp.tool()
def get_balance(account_id: str = "") -> dict[str, str]:
    """Return AINFT balance query entry information."""
    return {
        "account_id": account_id,
        "status": "redirect",
        "message": "Query balance from AINFT directly.",
        "ainft_web_url": network_config.ainft_web_url,
        "ainft_api_url": network_config.ainft_api_url,
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

    if not payment_signature:
        challenge = await _build_recharge_challenge(
            amount=amount,
            token=token,
            resource_url=str(request.url),
        )
        return JSONResponse(
            content=challenge,
            status_code=402,
            headers={PAYMENT_REQUIRED_HEADER: _encode_payment_payload(challenge)},
        )

    challenge = await _build_recharge_challenge(
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
    tx_url = _tx_explorer_url(tx_hash) if tx_hash else ""
    success = {
        "status": "paid",
        "recharge_status": "success",
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
        "settlement": settle_result,
    }
    return JSONResponse(
        content=success,
        status_code=200,
        headers={PAYMENT_RESPONSE_HEADER: _encode_payment_payload(success)},
    )


if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("AINFT Account Manager MCP Server Starting")
    logger.info("Network: %s", network_config.name)
    logger.info("AINFT Deposit Address: %s", network_config.ainft_deposit_address)
    logger.info("Tools: recharge, get_balance")
    logger.info("MCP Streamable HTTP Endpoint: http://%s:%s/mcp", settings.host, settings.port)
    logger.info("x402 HTTP Endpoint: http://%s:%s/x402/recharge", settings.host, settings.port)
    logger.info("=" * 60)

    app = MCPRecharge402Middleware(mcp.streamable_http_app())
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)
