"""Shared helpers for ERC-8004 registration scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PUBLIC_MCP_ENDPOINT = "https://ainft-agent.bankofai.io/mcp"

TRON_RPC_DEFAULTS: dict[str, str] = {
    "mainnet": "https://api.trongrid.io",
    "nile": "https://nile.trongrid.io",
    "shasta": "https://api.shasta.trongrid.io",
}

TRON_REGISTRATION_TARGETS: dict[str, dict[str, str]] = {
    "mainnet": {
        "network": "mainnet",
        "chain_family": "tron",
        "chain_id": "728126428",
        "agent_registry": "TFLvivMdKsk6v2GrwyD2apEr9dU1w7p7Fy",
    },
    "nile": {
        "network": "nile",
        "chain_family": "tron",
        "chain_id": "3448148188",
        "agent_registry": "TDDk4vc69nzBCbsY4kfu7gw2jmvbinirj5",
    },
}


def load_env() -> None:
    load_dotenv()


def load_operator_key() -> str:
    load_env()
    private_key = os.getenv("AGENT_OPERATOR_KEY", "").strip()
    if not private_key:
        raise SystemExit("Error: AGENT_OPERATOR_KEY is not set")
    return private_key


def resolve_network(network_arg: str, rpc_url_arg: str) -> tuple[str, str]:
    load_env()
    network = (network_arg or os.getenv("NETWORK", "mainnet")).strip().lower() or "mainnet"
    default_rpc = TRON_RPC_DEFAULTS.get(network, TRON_RPC_DEFAULTS["mainnet"])
    rpc_url = (rpc_url_arg or os.getenv("TRON_RPC_URL", "")).strip() or default_rpc
    return network, rpc_url


def build_sdk(network: str, rpc_url: str, signer: str, fee_limit: int) -> Any:
    try:
        from bankofai.sdk_8004.core.sdk import SDK
    except ImportError as exc:
        raise SystemExit(
            "bankofai-8004-sdk is not installed. "
            "Install the local SDK checkout with: pip install -e ../8004-sdk/python"
        ) from exc

    return SDK(
        chainId=1,
        rpcUrl=rpc_url,
        network=network,
        signer=signer,
        feeLimit=fee_limit,
    )


def resolve_public_mcp_endpoint(mcp_endpoint_arg: str = "") -> str:
    load_env()
    return (
        mcp_endpoint_arg
        or os.getenv("AINFT_PUBLIC_MCP_ENDPOINT", "").strip()
        or PUBLIC_MCP_ENDPOINT
    )


def resolve_public_web_url(web_url_arg: str = "") -> str:
    load_env()
    if web_url_arg:
        return web_url_arg.rstrip("/")
    if os.getenv("AINFT_WEB_URL", "").strip():
        return os.getenv("AINFT_WEB_URL", "").strip().rstrip("/")
    ainft_env = os.getenv("AINFT_ENV", "prod").strip().lower() or "prod"
    if ainft_env == "dev":
        return "https://chat-dev.ainft.com"
    return "https://chat.ainft.com"


def resolve_registration_target(network_arg: str = "") -> dict[str, str]:
    network = (network_arg or os.getenv("NETWORK", "mainnet")).strip().lower() or "mainnet"
    target = TRON_REGISTRATION_TARGETS.get(network)
    if not target:
        supported = ", ".join(sorted(TRON_REGISTRATION_TARGETS))
        raise SystemExit(
            f"Unsupported ERC-8004 registration network: {network}. Supported: {supported}"
        )
    return target


def resolve_agent_id(agent_id_arg: str = "") -> str:
    load_env()
    agent_id = (agent_id_arg or os.getenv("ERC8004_AGENT_ID", "")).strip()
    if not agent_id:
        raise SystemExit("Error: agent id is required. Pass --agent-id or set ERC8004_AGENT_ID.")
    return agent_id
