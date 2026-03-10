#!/usr/bin/env python3
"""Upload a local file to Pinata and print the resulting IPFS URI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx

from _8004_common import load_env

PINATA_UPLOAD_URL = "https://uploads.pinata.cloud/v3/files"
PINATA_TEST_AUTH_URL = "https://api.pinata.cloud/data/testAuthentication"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload a file to Pinata IPFS")
    parser.add_argument(
        "file",
        help="Local file path to upload",
    )
    parser.add_argument(
        "--name",
        default="",
        help="Optional display name in Pinata. Defaults to the local filename",
    )
    parser.add_argument(
        "--group-id",
        default="",
        help="Optional Pinata group id",
    )
    parser.add_argument(
        "--keyvalues",
        default="",
        help='Optional JSON object string for Pinata metadata, for example \'{"kind":"erc8004"}\'',
    )
    parser.add_argument(
        "--network",
        choices=("public", "private"),
        default="public",
        help="Pinata upload network. ERC-8004 metadata should usually be public.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "uri"),
        default="text",
        help="Output format. Use 'uri' for shell-friendly piping.",
    )
    parser.add_argument(
        "--skip-auth-check",
        action="store_true",
        help="Skip the Pinata auth test request before upload",
    )
    return parser.parse_args()


def load_pinata_jwt() -> str:
    load_env()
    token = os.getenv("PINATA_JWT", "").strip()
    if not token:
        raise SystemExit("Error: PINATA_JWT is not set")
    return token


def parse_keyvalues(raw: str) -> str:
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Error: --keyvalues must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit("Error: --keyvalues must decode to a JSON object")
    return json.dumps(parsed, separators=(",", ":"))


def validate_file(file_path: Path) -> Path:
    resolved = file_path.expanduser().resolve()
    if not resolved.exists():
        raise SystemExit(f"Error: file not found: {resolved}")
    if not resolved.is_file():
        raise SystemExit(f"Error: path is not a file: {resolved}")
    return resolved


def test_auth(client: httpx.Client, jwt: str) -> None:
    response = client.get(
        PINATA_TEST_AUTH_URL,
        headers={"Authorization": f"Bearer {jwt}", "Accept": "application/json"},
    )
    response.raise_for_status()


def upload_file(
    *,
    client: httpx.Client,
    jwt: str,
    file_path: Path,
    upload_name: str,
    network: str,
    group_id: str,
    keyvalues: str,
) -> dict[str, object]:
    data: dict[str, str] = {
        "network": network,
        "name": upload_name,
    }
    if group_id:
        data["group_id"] = group_id
    if keyvalues:
        data["keyvalues"] = keyvalues

    with file_path.open("rb") as handle:
        response = client.post(
            PINATA_UPLOAD_URL,
            headers={"Authorization": f"Bearer {jwt}"},
            data=data,
            files={"file": (file_path.name, handle, "application/json")},
        )

    response.raise_for_status()
    payload = response.json()
    data_obj = payload.get("data")
    if not isinstance(data_obj, dict) or not data_obj.get("cid"):
        raise SystemExit(f"Unexpected Pinata response: {payload}")
    return data_obj


def print_result(result: dict[str, object], fmt: str, file_path: Path, network: str) -> None:
    cid = str(result["cid"])
    ipfs_uri = f"ipfs://{cid}"
    gateway_base = os.getenv("PINATA_GATEWAY", "").strip().rstrip("/")
    output = {
        "file": str(file_path),
        "network": network,
        "pinata_id": result.get("id", ""),
        "cid": cid,
        "name": result.get("name", file_path.name),
        "size": result.get("size", 0),
        "mime_type": result.get("mime_type", ""),
        "created_at": result.get("created_at", ""),
        "is_duplicate": result.get("is_duplicate", False),
        "ipfs_uri": ipfs_uri,
    }
    if gateway_base:
        output["gateway_url"] = f"{gateway_base}/ipfs/{cid}"

    if fmt == "uri":
        print(ipfs_uri)
        return
    if fmt == "json":
        print(json.dumps(output, ensure_ascii=True, indent=2))
        return

    print(f"file: {output['file']}")
    print(f"network: {output['network']}")
    print(f"cid: {output['cid']}")
    print(f"ipfs_uri: {output['ipfs_uri']}")
    print(f"pinata_id: {output['pinata_id']}")
    if gateway_base:
        print(f"gateway_url: {output['gateway_url']}")


def main() -> int:
    args = parse_args()
    jwt = load_pinata_jwt()
    keyvalues = parse_keyvalues(args.keyvalues)
    file_path = validate_file(Path(args.file))
    upload_name = args.name or file_path.name

    with httpx.Client(timeout=60.0) as client:
        try:
            if not args.skip_auth_check:
                test_auth(client, jwt)
            result = upload_file(
                client=client,
                jwt=jwt,
                file_path=file_path,
                upload_name=upload_name,
                network=args.network,
                group_id=args.group_id,
                keyvalues=keyvalues,
            )
        except httpx.HTTPStatusError as exc:
            body = exc.response.text.strip()
            raise SystemExit(
                f"Pinata request failed: status={exc.response.status_code}, body={body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SystemExit(f"Pinata request failed: {exc}") from exc

    print_result(result, args.format, file_path, args.network)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
