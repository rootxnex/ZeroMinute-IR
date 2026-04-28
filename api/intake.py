from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

try:
    from .models import SourceBundle
except ImportError:
    from models import SourceBundle

try:
    from eth_utils import is_checksum_address, to_checksum_address
except Exception:  # pragma: no cover - optional dependency fallback
    is_checksum_address = None
    to_checksum_address = None


class IntakeError(Exception):
    """Base exception for source-intake failures."""


class InvalidAddressError(IntakeError):
    pass


class UnsupportedChainError(IntakeError):
    pass


class SourceNotVerifiedError(IntakeError):
    pass


class UpstreamFetchError(IntakeError):
    pass


@dataclass(frozen=True)
class ChainConfig:
    chain_id: int
    name: str
    sourcify_repo_base: str
    etherscan_api_base: str


SUPPORTED_CHAINS: dict[int, ChainConfig] = {
    1: ChainConfig(1, "ethereum", "https://repo.sourcify.dev", "https://api.etherscan.io/api"),
    10: ChainConfig(10, "optimism", "https://repo.sourcify.dev", "https://api-optimistic.etherscan.io/api"),
    137: ChainConfig(137, "polygon", "https://repo.sourcify.dev", "https://api.polygonscan.com/api"),
    8453: ChainConfig(8453, "base", "https://repo.sourcify.dev", "https://api.basescan.org/api"),
    42161: ChainConfig(42161, "arbitrum", "https://repo.sourcify.dev", "https://api.arbiscan.io/api"),
}

_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


def validate_address(address: str) -> str:
    """Validate an EVM address and return a checksummed representation."""
    if not isinstance(address, str) or not _ADDRESS_PATTERN.fullmatch(address):
        raise InvalidAddressError("Address must match 0x + 40 hex chars.")

    hex_body = address[2:]
    has_alpha = any(ch.isalpha() for ch in hex_body)
    is_mixed_case = has_alpha and not (hex_body.islower() or hex_body.isupper())
    if is_mixed_case:
        if is_checksum_address is None:
            raise InvalidAddressError(
                "Mixed-case address requires checksum validation dependency (eth_utils)."
            )
        try:
            valid_checksum = is_checksum_address(address)
        except Exception as exc:
            raise InvalidAddressError(
                "Unable to validate checksum address with current runtime dependencies."
            ) from exc
        if not valid_checksum:
            raise InvalidAddressError("Invalid EIP-55 checksum.")
        return address

    if to_checksum_address is None:
        # Safe fallback: preserve valid hex input if checksum tooling is unavailable.
        return address

    try:
        return to_checksum_address(address)
    except Exception:
        # Fallback when optional hashing backend is unavailable.
        return address


def _chain_config(chain_id: int) -> ChainConfig:
    try:
        return SUPPORTED_CHAINS[chain_id]
    except KeyError as exc:
        raise UnsupportedChainError(f"Unsupported chain_id: {chain_id}") from exc


def _request_with_retries(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    attempts: int = 3,
    backoff_sec: float = 0.3,
) -> httpx.Response:
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            response = client.request(method, url, params=params)
            if response.status_code >= 500:
                raise UpstreamFetchError(f"Upstream server error {response.status_code} from {url}")
            return response
        except (httpx.TimeoutException, httpx.RequestError, UpstreamFetchError) as exc:
            last_exc = exc
            if attempt == attempts:
                break
            time.sleep(backoff_sec * attempt)

    raise UpstreamFetchError(f"Failed upstream request {url}: {last_exc}") from last_exc


def _parse_etherscan_source_files(source_code: str, contract_name: str) -> dict[str, str]:
    raw = (source_code or "").strip()
    if not raw:
        return {}

    candidate = raw
    if candidate.startswith("{{") and candidate.endswith("}}"):
        candidate = candidate[1:-1]

    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError:
        return {f"{contract_name}.sol": raw}

    if isinstance(decoded, dict) and "sources" in decoded and isinstance(decoded["sources"], dict):
        out: dict[str, str] = {}
        for path, payload in decoded["sources"].items():
            if isinstance(payload, dict):
                out[path] = str(payload.get("content", ""))
            else:
                out[path] = str(payload)
        return out

    if isinstance(decoded, dict):
        out: dict[str, str] = {}
        for path, payload in decoded.items():
            if isinstance(payload, dict):
                out[path] = str(payload.get("content", ""))
            elif isinstance(payload, str):
                out[path] = payload
        if out:
            return out

    return {f"{contract_name}.sol": raw}


def normalize_source_bundle(payload: dict[str, Any]) -> SourceBundle:
    return SourceBundle.model_validate(payload)


def fetch_from_sourcify(
    chain_id: int,
    address: str,
    *,
    client: httpx.Client,
    retries: int = 3,
) -> SourceBundle | None:
    config = _chain_config(chain_id)
    metadata_url = (
        f"{config.sourcify_repo_base}/contracts/full_match/{chain_id}/{address}/metadata.json"
    )
    metadata_resp = _request_with_retries(client, "GET", metadata_url, attempts=retries)

    if metadata_resp.status_code == 404:
        return None
    if metadata_resp.status_code != 200:
        raise UpstreamFetchError(
            f"Unexpected Sourcify status {metadata_resp.status_code} for {address}"
        )

    try:
        metadata = metadata_resp.json()
    except ValueError as exc:
        raise UpstreamFetchError("Invalid Sourcify metadata JSON") from exc

    sources = metadata.get("sources", {})
    source_files: dict[str, str] = {}
    for path in sources:
        source_url = (
            f"{config.sourcify_repo_base}/contracts/full_match/{chain_id}/{address}/sources/{quote(path, safe='')}"
        )
        source_resp = _request_with_retries(client, "GET", source_url, attempts=retries)
        if source_resp.status_code != 200:
            raise UpstreamFetchError(
                f"Failed to fetch Sourcify source file {path}: {source_resp.status_code}"
            )
        source_files[path] = source_resp.text

    normalized = {
        "chain_id": chain_id,
        "address": address,
        "verified": True,
        "contract_name": metadata.get("contractName", "UnknownContract"),
        "abi": metadata.get("output", {}).get("abi", []),
        "compiler_version": metadata.get("compiler", {}).get("version"),
        "source_files": source_files,
        "metadata": {
            "source": "sourcify",
            "match": "full_match",
            "raw_metadata": metadata,
        },
    }

    return normalize_source_bundle(normalized)


def fetch_from_etherscan(
    chain_id: int,
    address: str,
    *,
    client: httpx.Client,
    api_key: str | None = None,
    retries: int = 3,
) -> SourceBundle:
    config = _chain_config(chain_id)
    key = api_key if api_key is not None else os.getenv("ETHERSCAN_API_KEY", "")

    params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "apikey": key,
    }
    response = _request_with_retries(
        client, "GET", config.etherscan_api_base, params=params, attempts=retries
    )

    if response.status_code != 200:
        raise UpstreamFetchError(
            f"Unexpected Etherscan status {response.status_code} for {address}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise UpstreamFetchError("Invalid Etherscan JSON") from exc

    # Etherscan-style errors arrive with status/message fields even on HTTP 200.
    status = str(data.get("status", ""))
    message = str(data.get("message", ""))
    if status == "0" and message.upper() == "NOTOK":
        result_payload = data.get("result")
        result_text = (
            result_payload if isinstance(result_payload, str) else json.dumps(result_payload)
        )
        if "not verified" in result_text.lower():
            raise SourceNotVerifiedError(f"No verified source for {address} on chain {chain_id}")
        raise UpstreamFetchError(
            f"Etherscan getsourcecode failed for {address}: {result_text}"
        )

    result = data.get("result")
    if not isinstance(result, list) or not result:
        raise SourceNotVerifiedError(f"No verified source for {address} on chain {chain_id}")

    row = result[0] or {}
    source_code = str(row.get("SourceCode") or "")
    abi_raw = row.get("ABI")

    unverified_sentinels = {
        "",
        "Contract source code not verified",
        "Contract source code not verified",
    }
    if source_code in unverified_sentinels or abi_raw in unverified_sentinels:
        raise SourceNotVerifiedError(f"No verified source for {address} on chain {chain_id}")

    try:
        abi: list[Any] | dict[str, Any] | str = json.loads(abi_raw) if isinstance(abi_raw, str) else abi_raw
    except json.JSONDecodeError:
        abi = abi_raw if isinstance(abi_raw, str) else []

    contract_name = str(row.get("ContractName") or "UnknownContract")
    source_files = _parse_etherscan_source_files(source_code, contract_name)
    if not source_files:
        raise SourceNotVerifiedError(f"No verified source for {address} on chain {chain_id}")

    normalized = {
        "chain_id": chain_id,
        "address": address,
        "verified": True,
        "contract_name": contract_name,
        "abi": abi,
        "compiler_version": row.get("CompilerVersion"),
        "source_files": source_files,
        "metadata": {
            "source": "etherscan",
            "raw_result": row,
        },
    }

    return normalize_source_bundle(normalized)


def fetch_source_bundle(
    chain_id: int,
    address: str,
    *,
    timeout_sec: float = 12.0,
    retries: int = 3,
    api_key: str | None = None,
) -> SourceBundle:
    _chain_config(chain_id)
    normalized_address = validate_address(address)

    with httpx.Client(timeout=timeout_sec) as client:
        sourcify = fetch_from_sourcify(
            chain_id, normalized_address, client=client, retries=retries
        )
        if sourcify is not None:
            return sourcify

        try:
            return fetch_from_etherscan(
                chain_id,
                normalized_address,
                client=client,
                api_key=api_key,
                retries=retries,
            )
        except SourceNotVerifiedError as exc:
            raise SourceNotVerifiedError(
                f"Contract {normalized_address} is not verified on supported sources"
            ) from exc


__all__ = [
    "InvalidAddressError",
    "UnsupportedChainError",
    "SourceNotVerifiedError",
    "UpstreamFetchError",
    "validate_address",
    "fetch_from_sourcify",
    "fetch_from_etherscan",
    "normalize_source_bundle",
    "fetch_source_bundle",
]
