#!/usr/bin/env python3
"""Register or update the BofAI payment agent on ERC-8004."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from bankofai.sdk_8004.core.contracts import DEFAULT_REGISTRIES, TRON_DEFAULT_REGISTRIES
    from bankofai.sdk_8004.core.sdk import SDK
    from bankofai.sdk_8004.core.transaction_handle import TransactionHandle
except ImportError:
    local_sdk = PROJECT_ROOT.parent.parent / "8004-sdk" / "python" / "src"
    if local_sdk.exists():
        sys.path.insert(0, str(local_sdk))
        from bankofai.sdk_8004.core.contracts import DEFAULT_REGISTRIES, TRON_DEFAULT_REGISTRIES
        from bankofai.sdk_8004.core.sdk import SDK
        from bankofai.sdk_8004.core.transaction_handle import TransactionHandle
    else:
        raise SystemExit(
            "bankofai-8004-sdk is not installed. "
            "Install it or place the local checkout at ../../8004-sdk/python/src"
        )


TRON_RPC_DEFAULTS = {
    "mainnet": "https://api.trongrid.io",
    "nile": "https://nile.trongrid.io",
    "shasta": "https://api.shasta.trongrid.io",
}

BSC_RPC_DEFAULTS = {
    56: "https://bsc-dataseed.binance.org",
    97: "https://data-seed-prebsc-1-s1.binance.org:8545",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register or update the BofAI payment agent on ERC-8004")
    parser.add_argument("--uri", required=True, help="Registration file URI (https://... or ipfs://...)")
    parser.add_argument("--chain", choices=("tron", "bsc"), required=True, help="Registration chain")
    parser.add_argument("--network", default="", help="TRON: mainnet|nile|shasta. BSC: eip155:56|eip155:97|mainnet|testnet")
    parser.add_argument("--rpc-url", default="", help="Override chain RPC URL")
    parser.add_argument("--registry", default="", help="Override identity registry address")
    parser.add_argument("--agent-id", default="", help="Existing agent ID. If provided, update URI instead of registering")
    parser.add_argument("--mcp-endpoint", default="https://ainft-agent.bankofai.io/mcp", help="MCP endpoint to publish")
    parser.add_argument("--fee-limit", type=int, default=120_000_000, help="TRON fee limit for write transactions")
    parser.add_argument("--name", default="BofAI Payment Agent", help="Agent display name")
    parser.add_argument(
        "--description",
        default="MCP payee-side x402 payment agent for BofAI on supported TRON and BSC routes.",
        help="Agent description",
    )
    parser.add_argument("--image", default="https://www.bankofai.io/og_img_5.png", help="Agent image URL")
    parser.add_argument("--website", default="https://www.bankofai.io/", help="Public website URL")
    parser.add_argument("--chat-url", default="https://chat.bankofai.io/chat", help="Public chat URL")
    parser.add_argument("--operator-key-env", default="", help="Override operator key env var name")
    return parser.parse_args()


def _resolve_operator_key(args: argparse.Namespace) -> tuple[str, str]:
    candidates = []
    if args.operator_key_env:
        candidates.append(args.operator_key_env)
    if args.chain == "tron":
        candidates.append("TRON_AGENT_OPERATOR_KEY")
    else:
        candidates.append("BSC_AGENT_OPERATOR_KEY")
    candidates.append("AGENT_OPERATOR_KEY")

    for env_name in candidates:
        value = os.getenv(env_name, "").strip()
        if value:
            return env_name, value
    raise SystemExit(f"Operator key is not set. Checked: {', '.join(candidates)}")


def _resolve_tron_target(raw_network: str, rpc_override: str, registry_override: str) -> dict[str, str | int]:
    network = (raw_network or "mainnet").strip().lower()
    if network.startswith("tron:"):
        network = network.split(":", 1)[1]
    if network not in TRON_RPC_DEFAULTS:
        raise SystemExit(f"Unsupported TRON network: {raw_network}")

    registry = registry_override.strip() or TRON_DEFAULT_REGISTRIES[network]["IDENTITY"]
    chain_id_for_metadata = {
        "mainnet": "728126428",
        "nile": "3448148188",
        "shasta": "2494104990",
    }[network]

    return {
        "chain_type": "tron",
        "sdk_network": network,
        "sdk_chain_id": 1,
        "rpc_url": rpc_override.strip() or os.getenv("TRON_RPC_URL", "").strip() or TRON_RPC_DEFAULTS[network],
        "registry": registry,
        "agent_registry": f"tron:{chain_id_for_metadata}:{registry}",
    }


def _resolve_bsc_target(raw_network: str, rpc_override: str, registry_override: str) -> dict[str, str | int]:
    network = (raw_network or "eip155:56").strip().lower()
    if network in {"mainnet", "bsc", "bsc_mainnet"}:
        chain_id = 56
    elif network in {"testnet", "bsc_testnet"}:
        chain_id = 97
    elif network.startswith("eip155:"):
        chain_id = int(network.split(":", 1)[1])
    else:
        raise SystemExit(f"Unsupported BSC network: {raw_network}")

    if chain_id not in DEFAULT_REGISTRIES:
        raise SystemExit(f"No default 8004 registry found for BSC chain ID {chain_id}. Use --registry.")

    registry = registry_override.strip() or DEFAULT_REGISTRIES[chain_id]["IDENTITY"]
    return {
        "chain_type": "bsc",
        "sdk_network": f"eip155:{chain_id}",
        "sdk_chain_id": chain_id,
        "rpc_url": rpc_override.strip() or BSC_RPC_DEFAULTS.get(chain_id, ""),
        "registry": registry,
        "agent_registry": f"eip155:{chain_id}:{registry}",
    }


def _resolve_target(args: argparse.Namespace) -> dict[str, str | int]:
    if args.chain == "tron":
        return _resolve_tron_target(args.network, args.rpc_url, args.registry)
    return _resolve_bsc_target(args.network, args.rpc_url, args.registry)


def main() -> int:
    load_dotenv()
    args = parse_args()
    operator_key_env, private_key = _resolve_operator_key(args)
    target = _resolve_target(args)

    rpc_url = str(target["rpc_url"]).strip()
    if not rpc_url:
        raise SystemExit("RPC URL is empty. Use --rpc-url or configure a default.")

    registry = str(target["registry"])
    sdk_chain_id = int(target["sdk_chain_id"])
    sdk_network = str(target["sdk_network"])

    sdk = SDK(
        chainId=sdk_chain_id,
        rpcUrl=rpc_url,
        network=sdk_network,
        signer=private_key,
        feeLimit=args.fee_limit,
        registryOverrides={sdk_chain_id: {"IDENTITY": registry}},
    )

    print(f"chain={args.chain}")
    print(f"network={sdk_network}")
    print(f"rpc_url={rpc_url}")
    print(f"registry={registry}")
    print(f"agent_registry={target['agent_registry']}")
    print(f"operator_key_env={operator_key_env}")

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
            name=args.name,
            description=args.description,
            image=args.image,
        )
        agent.setMCP(args.mcp_endpoint, auto_fetch=False)
        agent.setTrust(reputation=True, cryptoEconomic=False)
        agent.setX402Support(True)
        agent.setActive(True)
        agent.setMetadata(
            {
                "brand": "BofAI",
                "website": args.website,
                "chatUrl": args.chat_url,
                "paymentProtocol": "x402",
                "serviceType": "mcp-payment-agent",
                "primaryRegistrationChain": target["agent_registry"],
            }
        )
        handle = agent.register(args.uri)

    print(f"tx_hash: {handle.tx_hash}")
    result = handle.wait_confirmed(timeout=180).result
    print(f"agent_id: {result.agentId}")
    print(f"agent_uri: {result.agentURI}")
    print(f"agent_registry: {target['agent_registry']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
