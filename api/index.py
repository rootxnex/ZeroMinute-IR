from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

try:
    from .extract import extract_emergency_capabilities
    from .intake import (
        InvalidAddressError,
        SourceNotVerifiedError,
        UnsupportedChainError,
        UpstreamFetchError,
        fetch_source_bundle,
    )
    from .models import AnalyzeRequest, SourceBundle
except ImportError:
    from extract import extract_emergency_capabilities
    from intake import (
        InvalidAddressError,
        SourceNotVerifiedError,
        UnsupportedChainError,
        UpstreamFetchError,
        fetch_source_bundle,
    )
    from models import AnalyzeRequest, SourceBundle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("zerominute.analyzer")

app = FastAPI(
    title="ZeroMinute IR Analyzer",
    version="0.1.0",
    description="Deterministic smart-contract emergency response analyzer",
)


def _error_payload(code: str, message: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
        }
    }


@app.exception_handler(InvalidAddressError)
async def invalid_address_handler(_, exc: InvalidAddressError):
    return JSONResponse(
        status_code=400,
        content=_error_payload("invalid_address", str(exc)),
    )


@app.exception_handler(UnsupportedChainError)
async def unsupported_chain_handler(_, exc: UnsupportedChainError):
    return JSONResponse(
        status_code=400,
        content=_error_payload("unsupported_chain", str(exc)),
    )


@app.exception_handler(SourceNotVerifiedError)
async def source_not_verified_handler(_, exc: SourceNotVerifiedError):
    return JSONResponse(
        status_code=404,
        content=_error_payload("contract_not_verified", str(exc)),
    )


@app.exception_handler(UpstreamFetchError)
async def upstream_error_handler(_, exc: UpstreamFetchError):
    return JSONResponse(
        status_code=502,
        content=_error_payload("upstream_fetch_failed", str(exc)),
    )


def _summarize_source(bundle: SourceBundle) -> dict[str, Any]:
    return {
        "chain_id": bundle.chain_id,
        "address": bundle.address,
        "verified": bundle.verified,
        "contract_name": bundle.contract_name,
        "compiler_version": bundle.compiler_version,
        "source_file_count": len(bundle.source_files),
        "metadata_source": bundle.metadata.get("source"),
    }


def _compose_action(function_finding: dict[str, Any]) -> str:
    confidence = function_finding.get("confidence", "inferred")
    name = function_finding.get("name", "unknown")
    function_type = function_finding.get("type", "function")
    return f"[{confidence}] Review and, if authorized, execute `{name}` ({function_type})."


def _deterministic_runbook(contract: dict[str, Any], findings: dict[str, Any]) -> tuple[dict[str, Any], str]:
    confirmed_functions = findings.get("confirmed_functions", [])
    inferred_functions = findings.get("inferred_functions", [])
    confirmed_roles = findings.get("confirmed_roles", [])
    inferred_roles = findings.get("inferred_roles", [])
    manual_checks = findings.get("manual_checks", [])
    warnings = findings.get("warnings", [])

    immediate_actions: list[str] = []
    containment_actions: list[str] = []
    verification_actions: list[str] = []

    for finding in confirmed_functions:
        if finding.get("type") in {"pause", "halt"}:
            immediate_actions.append(_compose_action(finding))

    for finding in confirmed_functions + inferred_functions:
        if finding.get("type") in {"emergency_withdraw", "upgrade_admin", "unpause"}:
            containment_actions.append(_compose_action(finding))

    for check in manual_checks:
        verification_actions.append(f"[manual verification required] {check}")

    if not immediate_actions:
        immediate_actions.append(
            "[manual verification required] No confirmed pause/halt function found; verify alternate containment path immediately."
        )

    if not containment_actions:
        containment_actions.append(
            "[manual verification required] No deterministic containment function confirmed; validate fallback operational controls."
        )

    if not verification_actions:
        verification_actions.append(
            "[manual verification required] Verify signer permissions and contract state before executing actions."
        )

    required_roles = [
        f"[{role.get('confidence', 'inferred')}] {role.get('name', 'unknown')}"
        for role in (confirmed_roles + inferred_roles)
    ]
    if not required_roles:
        required_roles = ["[manual verification required] No role findings detected."]

    functions_to_review = [
        f"[{finding.get('confidence', 'inferred')}] {finding.get('name', 'unknown')} ({finding.get('type', 'function')})"
        for finding in (confirmed_functions + inferred_functions)
    ]
    if not functions_to_review:
        functions_to_review = ["[manual verification required] No emergency function findings detected."]

    risk_notes = warnings if warnings else ["No additional uncertainty warnings generated."]

    executive_summary = (
        f"Contract `{contract['contract_name']}` at `{contract['address']}` on chain {contract['chain_id']} has "
        f"{len(confirmed_functions)} confirmed and {len(inferred_functions)} inferred emergency-function findings."
    )

    runbook_json = {
        "executive_summary": executive_summary,
        "immediate_actions": immediate_actions,
        "containment_actions": containment_actions,
        "verification_actions": verification_actions,
        "required_roles": required_roles,
        "functions_to_review": functions_to_review,
        "manual_verification_required": manual_checks,
        "uncertainty_risk_notes": risk_notes,
    }

    markdown_lines = [
        "# Executive Summary",
        executive_summary,
        "",
        "## Immediate Actions (0-5 minutes)",
        *[f"- {item}" for item in immediate_actions],
        "",
        "## Containment Actions (5-15 minutes)",
        *[f"- {item}" for item in containment_actions],
        "",
        "## Verification Actions (15-30 minutes)",
        *[f"- {item}" for item in verification_actions],
        "",
        "## Required Roles / Signers",
        *[f"- {item}" for item in required_roles],
        "",
        "## Functions to Review",
        *[f"- {item}" for item in functions_to_review],
        "",
        "## Manual Verification Required",
        *[f"- {item}" for item in (manual_checks or ["None reported"])],
        "",
        "## Uncertainty / Risk Notes",
        *[f"- {item}" for item in risk_notes],
    ]
    markdown = "\n".join(markdown_lines)

    return runbook_json, markdown


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    start = time.perf_counter()
    logger.info("request.start method=POST path=/api/analyze chain_id=%s", request.chain_id)
    try:
        bundle = fetch_source_bundle(request.chain_id, request.address)
        findings = extract_emergency_capabilities(bundle)

        contract = {
            "chain_id": bundle.chain_id,
            "address": bundle.address,
            "contract_name": bundle.contract_name,
            "verified": bundle.verified,
        }

        runbook_json, runbook_markdown = _deterministic_runbook(contract, findings)

        payload = {
            "contract": contract,
            "normalized_source_summary": _summarize_source(bundle),
            "analyzer_findings": findings,
            # Flatten findings for frontend compatibility.
            "confirmed_functions": findings.get("confirmed_functions", []),
            "inferred_functions": findings.get("inferred_functions", []),
            "confirmed_roles": findings.get("confirmed_roles", []),
            "inferred_roles": findings.get("inferred_roles", []),
            "manual_checks": findings.get("manual_checks", []),
            "warnings": findings.get("warnings", []),
            "runbook_json": runbook_json,
            "runbook_markdown": runbook_markdown,
        }
        return payload
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("request.end method=POST path=/analyze duration_ms=%.2f", duration_ms)


__all__ = ["app"]
