#!/usr/bin/env python3
"""Update an existing ERC-8004 agent URI."""

from __future__ import annotations

import argparse

from bankofai.sdk_8004.core.transaction_handle import TransactionHandle

from _8004_common import build_sdk, load_operator_key, resolve_agent_id, resolve_network


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update AINFT Merchant Agent URI on ERC-8004")
    parser.add_argument(
        "--agent-id",
        default="",
        help="Existing agent ID to update. Falls back to ERC8004_AGENT_ID in .env",
    )
    parser.add_argument(
        "--uri",
        required=True,
        help="New registration file URI (https://... or ipfs://...)",
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
    agent_id = resolve_agent_id(args.agent_id)
    network, rpc_url = resolve_network(args.network, args.rpc_url)

    print(f"Using network={network}, rpc_url={rpc_url}")

    sdk = build_sdk(network=network, rpc_url=rpc_url, signer=private_key, fee_limit=args.fee_limit)

    print(f"Updating existing agent {agent_id} URI -> {args.uri}")
    agent_id_int = int(str(agent_id).split(":")[-1])
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

    print(f"tx_hash: {handle.tx_hash}")
    result = handle.wait_confirmed(timeout=180).result
    print(f"agent_id: {result.agentId}")
    print(f"agent_uri: {result.agentURI}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
