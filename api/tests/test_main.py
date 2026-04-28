from __future__ import annotations

import asyncio

from services.analyzer.intake import InvalidAddressError, UpstreamFetchError
from services.analyzer.main import (
    analyze,
    health,
    invalid_address_handler,
    upstream_error_handler,
)
from services.analyzer.models import AnalyzeRequest, SourceBundle


def test_health_function():
    assert health() == {"status": "ok"}


def test_analyze_success(monkeypatch):
    bundle = SourceBundle(
        chain_id=1,
        address="0x1111111111111111111111111111111111111111",
        verified=True,
        contract_name="Vault",
        abi=[{"type": "function", "name": "pause"}],
        compiler_version="v0.8.24",
        source_files={"contracts/Vault.sol": "contract Vault { function pause() external {} }"},
        metadata={"source": "sourcify"},
    )

    findings = {
        "confirmed_functions": [
            {
                "name": "pause",
                "type": "pause",
                "confidence": "confirmed",
                "evidence": "ABI function exists",
            }
        ],
        "inferred_functions": [],
        "confirmed_roles": [
            {
                "name": "owner",
                "type": "owner",
                "confidence": "confirmed",
                "evidence": "Ownable detected",
            }
        ],
        "inferred_roles": [],
        "manual_checks": ["Verify signer access on-chain."],
        "warnings": [],
    }

    monkeypatch.setattr("services.analyzer.main.fetch_source_bundle", lambda chain_id, address: bundle)
    monkeypatch.setattr("services.analyzer.main.extract_emergency_capabilities", lambda _: findings)

    payload = analyze(AnalyzeRequest(chain_id=1, address="0x1111111111111111111111111111111111111111"))

    assert payload["contract"]["contract_name"] == "Vault"
    assert payload["normalized_source_summary"]["metadata_source"] == "sourcify"
    assert payload["confirmed_functions"][0]["name"] == "pause"
    assert "runbook_markdown" in payload


def test_invalid_address_error_handler():
    response = asyncio.run(invalid_address_handler(None, InvalidAddressError("bad address")))

    assert response.status_code == 400
    assert response.body
    assert b'"code":"invalid_address"' in response.body


def test_upstream_error_handler():
    response = asyncio.run(upstream_error_handler(None, UpstreamFetchError("network down")))

    assert response.status_code == 502
    assert response.body
    assert b'"code":"upstream_fetch_failed"' in response.body
