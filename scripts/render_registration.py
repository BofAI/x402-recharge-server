#!/usr/bin/env python3
"""Render bootstrap or final ERC-8004 registration JSON."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from _8004_common import (
    load_env,
    resolve_agent_id,
    resolve_public_mcp_endpoint,
    resolve_public_web_url,
    resolve_registration_target,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render ERC-8004 registration JSON")
    parser.add_argument(
        "--mode",
        choices=("bootstrap", "final"),
        default="bootstrap",
        help="bootstrap renders a pre-registration file; final includes agent_id in registrations",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--network",
        default="",
        help="Registration network for agentRegistry metadata (mainnet|nile)",
    )
    parser.add_argument(
        "--agent-id",
        default="",
        help="Existing agent ID for final mode. Falls back to ERC8004_AGENT_ID in .env",
    )
    parser.add_argument(
        "--mcp-endpoint",
        default="",
        help="Public MCP endpoint. Falls back to AINFT_PUBLIC_MCP_ENDPOINT or production default",
    )
    parser.add_argument(
        "--web-url",
        default="",
        help="Public web URL. Falls back to AINFT_WEB_URL or env-based default",
    )
    parser.add_argument(
        "--name",
        default="AINFT Merchant Agent",
        help="Agent display name",
    )
    parser.add_argument(
        "--description",
        default="MCP payee-side recharge provider for AINFT token top-up over x402 on the configured production chain.",
        help="Agent description",
    )
    parser.add_argument(
        "--image",
        "--icon",
        dest="image",
        default=(
            os.getenv("AINFT_REGISTRATION_IMAGE", "").strip()
            or "https://chat.ainft.com/favicon.ico"
        ),
        help="Agent image/icon URL (https://... or ipfs://...)",
    )
    parser.add_argument(
        "--tags",
        default=(
            os.getenv("AINFT_REGISTRATION_TAGS", "").strip()
            or "ainft,mcp,x402,tron,bsc,payments"
        ),
        help="Comma-separated registration tags",
    )
    return parser.parse_args()


def build_document(args: argparse.Namespace) -> dict[str, object]:
    load_env()
    target = resolve_registration_target(args.network)
    mcp_endpoint = resolve_public_mcp_endpoint(args.mcp_endpoint)
    web_url = resolve_public_web_url(args.web_url)
    ainft_env = (os.getenv("AINFT_ENV", "prod").strip().lower() or "prod")
    tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]

    registrations: list[dict[str, str]] = []
    if args.mode == "final":
        agent_id = resolve_agent_id(args.agent_id)
        registrations.append(
            {
                "agentRegistry": (
                    f"{target['chain_family']}:{target['chain_id']}:{target['agent_registry']}"
                ),
                "agentId": str(agent_id).split(":")[-1],
            }
        )

    return {
        "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
        "name": args.name,
        "description": args.description,
        "image": args.image,
        "tags": tags,
        "services": [
            {
                "name": "MCP",
                "endpoint": mcp_endpoint,
                "version": "2025-06-18",
            },
            {
                "name": "web",
                "endpoint": web_url,
            },
        ],
        "supportedTrust": ["reputation"],
        "active": True,
        "registrations": registrations,
        "environment": {
            "external": f"ainft {ainft_env}",
            "runtimeNetwork": target["network"],
            "chainFamily": target["chain_family"],
            "chainId": target["chain_id"],
            "agentRegistry": (
                f"{target['chain_family']}:{target['chain_id']}:{target['agent_registry']}"
            ),
        },
        "mcp": {
            "transport": "streamable-http",
            "paymentProtocol": "x402",
            "tools": [
                {
                    "name": "ainft_pay_trc20",
                    "status": "active",
                    "description": "Token recharge via x402 on TRON-compatible runtime configuration.",
                    "arguments": {
                        "amount": "string",
                        "token": "network-aware enum from MCP tools/list",
                    },
                },
                {
                    "name": "ainft_pay_erc20",
                    "status": "conditional",
                    "description": "Explicit ERC20 recharge alias. Only available when the deployed runtime network is EVM/BSC.",
                    "arguments": {
                        "amount": "string",
                        "token": "network-aware enum from MCP tools/list",
                    },
                },
                {
                    "name": "recharge",
                    "status": "deprecated",
                    "description": "Compatibility alias for recharge flows. Prefer ainft_pay_trc20 or ainft_pay_erc20.",
                    "arguments": {
                        "amount": "string",
                        "token": "string",
                        "txid": "string",
                    },
                },
                {
                    "name": "get_balance",
                    "status": "deprecated",
                    "description": "Moved to local ainft-skill. The server now returns a redirect hint.",
                    "arguments": {
                        "account_id": "string",
                    },
                },
            ],
        },
    }


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = build_document(args)
    output_path.write_text(json.dumps(document, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    print(f"Rendered {args.mode} registration JSON -> {output_path}")
    if args.mode == "bootstrap":
        print("registrations: []")
    else:
        print(f"registrations[0].agentId: {document['registrations'][0]['agentId']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
