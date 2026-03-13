#!/usr/bin/env python3
"""Register this agent on ERC-8004.

This script is intentionally separate from service startup.
It only handles the first on-chain registration metadata write.
"""

from __future__ import annotations

import argparse
import os

from _8004_common import (
    build_sdk,
    load_operator_key,
    resolve_network,
    resolve_public_mcp_endpoint,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register AINFT Merchant Agent on ERC-8004")
    parser.add_argument(
        "--uri",
        required=True,
        help="Registration file URI (https://... or ipfs://...)",
    )
    parser.add_argument(
        "--mcp-endpoint",
        default="",
        help="Public MCP endpoint to publish on-chain. Falls back to AINFT_PUBLIC_MCP_ENDPOINT or production default",
    )
    parser.add_argument(
        "--fee-limit",
        type=int,
        default=120_000_000,
        help="TRON fee limit for write transactions",
    )
    parser.add_argument(
        "--network",
        default="",
        help="Target network for registration metadata load/update (mainnet|nile|shasta).",
    )
    parser.add_argument(
        "--rpc-url",
        default="",
        help="Override TRON RPC URL. If omitted, uses env TRON_RPC_URL or network default.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    private_key = load_operator_key()
    network, rpc_url = resolve_network(args.network, args.rpc_url)
    mcp_endpoint = resolve_public_mcp_endpoint(args.mcp_endpoint)

    print(f"Using network={network}, rpc_url={rpc_url}")
    print(f"Using mcp_endpoint={mcp_endpoint}")

    sdk = build_sdk(network=network, rpc_url=rpc_url, signer=private_key, fee_limit=args.fee_limit)

    print("Registering new agent")
    agent = sdk.createAgent(
        name="AINFT Merchant Agent",
        description="MCP payee-side recharge provider for AINFT token top-up over x402.",
        image=(
            os.getenv("AINFT_REGISTRATION_IMAGE", "").strip()
            or "https://chat.ainft.com/favicon.ico"
        ),
    )
    agent.setMCP(mcp_endpoint, auto_fetch=True)
    agent.setTrust(reputation=True, cryptoEconomic=False)
    agent.setX402Support(True)
    agent.setActive(True)
    handle = agent.register(args.uri)

    print(f"tx_hash: {handle.tx_hash}")
    result = handle.wait_confirmed(timeout=180).result
    print(f"agent_id: {result.agentId}")
    print(f"agent_uri: {result.agentURI}")
    print("Next: render a final registration JSON with this agent_id, upload it, then run update_8004.py.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
