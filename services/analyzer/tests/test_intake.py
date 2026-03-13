from __future__ import annotations

import json

import httpx
import pytest

from services.analyzer.intake import (
    InvalidAddressError,
    SourceNotVerifiedError,
    UpstreamFetchError,
    fetch_from_etherscan,
    fetch_from_sourcify,
    fetch_source_bundle,
)


def _client_with_handler(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, timeout=5.0)


def test_sourcify_success_path():
    address = "0x1111111111111111111111111111111111111111"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/metadata.json"):
            return httpx.Response(
                200,
                json={
                    "contractName": "Vault",
                    "compiler": {"version": "v0.8.20+commit.a1b79de6"},
                    "output": {"abi": [{"type": "function", "name": "pause"}]},
                    "sources": {"contracts/Vault.sol": {}},
                },
            )
        if "/sources/contracts%2FVault.sol" in str(request.url):
            return httpx.Response(200, text="contract Vault { function pause() external {} }")
        return httpx.Response(404)

    with _client_with_handler(handler) as client:
        bundle = fetch_from_sourcify(1, address, client=client)

    assert bundle is not None
    assert bundle.contract_name == "Vault"
    assert bundle.metadata["source"] == "sourcify"
    assert "contracts/Vault.sol" in bundle.source_files


def test_fallback_to_etherscan_when_sourcify_missing(monkeypatch: pytest.MonkeyPatch):
    address = "0x2222222222222222222222222222222222222222"
    original_client_cls = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "repo.sourcify.dev":
            return httpx.Response(404)

        if request.url.host == "api.etherscan.io":
            payload = {
                "status": "1",
                "message": "OK",
                "result": [
                    {
                        "ContractName": "Vault",
                        "ABI": json.dumps([{"type": "function", "name": "pause"}]),
                        "SourceCode": "contract Vault { function pause() external {} }",
                        "CompilerVersion": "v0.8.24+commit.e11b9ed9",
                    }
                ],
            }
            return httpx.Response(200, json=payload)

        return httpx.Response(500)

    class DummyClient:
        def __init__(self, *args, **kwargs):
            transport = httpx.MockTransport(handler)
            self._client = original_client_cls(transport=transport, timeout=5.0)

        def __enter__(self):
            return self._client

        def __exit__(self, exc_type, exc, tb):
            self._client.close()
            return False

    monkeypatch.setattr("services.analyzer.intake.httpx.Client", DummyClient)
    bundle = fetch_source_bundle(1, address)

    assert bundle.metadata["source"] == "etherscan"
    assert bundle.contract_name == "Vault"


def test_invalid_address_failure():
    with pytest.raises(InvalidAddressError):
        fetch_source_bundle(1, "not-an-address")


def test_unverified_contract_failure():
    address = "0x3333333333333333333333333333333333333333"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.etherscan.io":
            return httpx.Response(
                200,
                json={
                    "status": "0",
                    "message": "NOTOK",
                    "result": [
                        {
                            "ContractName": "",
                            "ABI": "Contract source code not verified",
                            "SourceCode": "",
                        }
                    ],
                },
            )
        return httpx.Response(404)

    with _client_with_handler(handler) as client:
        with pytest.raises(SourceNotVerifiedError):
            fetch_from_etherscan(1, address, client=client)


def test_upstream_error_handling():
    address = "0x4444444444444444444444444444444444444444"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with _client_with_handler(handler) as client:
        with pytest.raises(UpstreamFetchError):
            fetch_from_sourcify(1, address, client=client)


def test_etherscan_notok_maps_to_upstream_error():
    address = "0x5555555555555555555555555555555555555555"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.etherscan.io":
            return httpx.Response(
                200,
                json={
                    "status": "0",
                    "message": "NOTOK",
                    "result": "Max rate limit reached",
                },
            )
        return httpx.Response(404)

    with _client_with_handler(handler) as client:
        with pytest.raises(UpstreamFetchError):
            fetch_from_etherscan(1, address, client=client)
