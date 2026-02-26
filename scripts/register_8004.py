#!/usr/bin/env python3
"""Register or update this agent on ERC-8004.

This script is intentionally separate from service startup.
It only handles on-chain registration metadata (identity/discovery).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from bankofai.sdk_8004.core.sdk import SDK
    from bankofai.sdk_8004.core.transaction_handle import TransactionHandle
except ImportError as exc:
    raise SystemExit(
        "bankofai-8004-sdk is not installed. "
        "Install the local SDK checkout with: pip install -e ../8004-sdk/python"
    ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register/update AINFT Merchant Agent on ERC-8004")
    parser.add_argument(
        "--uri",
        required=True,
        help="Registration file URI (https://... or ipfs://...)",
    )
    parser.add_argument(
        "--mcp-endpoint",
        default="http://127.0.0.1:8000/mcp",
        help="MCP endpoint to publish in registration metadata",
    )
    parser.add_argument(
        "--agent-id",
        default="",
        help="Existing agent ID. If provided, script updates URI instead of creating a new agent",
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
    load_dotenv()
    args = parse_args()

    private_key = os.getenv("AGENT_OPERATOR_KEY", "").strip()
    if not private_key:
        print("Error: AGENT_OPERATOR_KEY is not set")
        return 1

    network = (args.network or os.getenv("NETWORK", "mainnet")).strip().lower() or "mainnet"
    default_rpc = {
        "mainnet": "https://api.trongrid.io",
        "nile": "https://nile.trongrid.io",
        "shasta": "https://api.shasta.trongrid.io",
    }.get(network, "https://api.trongrid.io")
    rpc_url = (args.rpc_url or os.getenv("TRON_RPC_URL", "")).strip() or default_rpc

    print(f"Using network={network}, rpc_url={rpc_url}")

    sdk = SDK(
        chainId=1,
        rpcUrl=rpc_url,
        network=network,
        signer=private_key,
        feeLimit=args.fee_limit,
    )

    if args.agent_id:
        print(f"Updating existing agent {args.agent_id} URI -> {args.uri}")
        agent_id_int = int(str(args.agent_id).split(":")[-1])
        tx_hash = sdk.web3_client.transact_contract(
            sdk.identity_registry,
            "setAgentURI",
            agent_id_int,
            args.uri,
        )
        handle = TransactionHandle(
            web3_client=sdk.web3_client,
            tx_hash=tx_hash,
            compute_result=lambda _receipt: type(
                "UpdateResult",
                (),
                {"agentId": str(agent_id_int), "agentURI": args.uri},
            )(),
        )
    else:
        print("Registering new agent")
        agent = sdk.createAgent(
            name="AINFT Merchant Agent",
            description="MCP payee-side x402 challenge provider for AINFT recharge on TRON mainnet.",
            image="https://chat.ainft.com/favicon.ico",
        )
        agent.setMCP(args.mcp_endpoint, auto_fetch=True)
        agent.setTrust(reputation=True, cryptoEconomic=False)
        agent.setX402Support(True)
        agent.setActive(True)
        handle = agent.register(args.uri)

    print(f"tx_hash: {handle.tx_hash}")
    result = handle.wait_confirmed(timeout=180).result
    print(f"agent_id: {result.agentId}")
    print(f"agent_uri: {result.agentURI}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
