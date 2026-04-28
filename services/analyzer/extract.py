from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

try:
    from .models import SourceBundle
except ImportError:
    from models import SourceBundle

_FUNCTION_DECLARATION_RE = re.compile(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_ROLE_CONSTANT_RE = re.compile(r"\b([A-Z][A-Z0-9_]*_ROLE)\b")
_ONLY_ROLE_RE = re.compile(r"\bonly([A-Z][A-Za-z0-9_]*)\b")


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _parse_abi_list(abi_raw: Any) -> list[dict[str, Any]]:
    if isinstance(abi_raw, list):
        return [entry for entry in abi_raw if isinstance(entry, dict)]

    if isinstance(abi_raw, str):
        try:
            decoded = json.loads(abi_raw)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return [entry for entry in decoded if isinstance(entry, dict)]

    return []


def _abi_function_names(abi_raw: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in _parse_abi_list(abi_raw):
        if item.get("type") != "function":
            continue
        name = item.get("name")
        if isinstance(name, str) and name:
            out[name.lower()] = name
    return out


def _source_function_index(source_files: dict[str, str]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for path, content in source_files.items():
        if not isinstance(content, str):
            continue
        for match in _FUNCTION_DECLARATION_RE.finditer(content):
            name = match.group(1)
            lowered = name.lower()
            entry = index.setdefault(lowered, {"name": name, "locations": []})
            entry["locations"].append(f"{path}:{_line_for_offset(content, match.start())}")
    return index


def _normalize_role_name(raw: str) -> str:
    cleaned = raw.strip("_")
    if cleaned.endswith("_ROLE"):
        cleaned = cleaned[: -len("_ROLE")]
    return cleaned.lower()


def _classify_function(name: str) -> str | None:
    lowered = name.lower()

    if "unpause" in lowered or "resume" in lowered or "unfreeze" in lowered:
        return "unpause"

    if "pause" in lowered:
        return "pause"

    if any(token in lowered for token in ("halt", "freeze", "shutdown", "circuitbreak", "stop", "kill")):
        return "halt"

    emergency_withdraw_tokens = (
        "emergencywithdraw",
        "rescue",
        "sweep",
        "recover",
    )
    if any(token in lowered for token in emergency_withdraw_tokens):
        if "withdraw" in lowered or "emergency" in lowered or "fund" in lowered or "token" in lowered:
            return "emergency_withdraw"

    upgrade_tokens = (
        "upgradetoandcall",
        "upgradeto",
        "setimplementation",
        "changeadmin",
        "setproxyadmin",
        "_authorizeupgrade",
    )
    if any(token in lowered for token in upgrade_tokens):
        return "upgrade_admin"

    if lowered.startswith("upgrade"):
        return "upgrade_admin"

    return None


def _append_unique(finds: list[dict[str, Any]], finding: dict[str, Any]) -> None:
    key = (finding["name"].lower(), finding["type"], finding["confidence"])
    if any((item["name"].lower(), item["type"], item["confidence"]) == key for item in finds):
        return
    finds.append(finding)


def _build_finding(
    *,
    name: str,
    finding_type: str,
    confidence: str,
    evidence: str,
    source_location: str | None = None,
) -> dict[str, Any]:
    payload = {
        "name": name,
        "type": finding_type,
        "confidence": confidence,
        "evidence": evidence,
    }
    if source_location:
        payload["source_location"] = source_location
    return payload


def extract_emergency_capabilities(source_bundle: SourceBundle | dict[str, Any]) -> dict[str, Any]:
    bundle = (
        source_bundle
        if isinstance(source_bundle, SourceBundle)
        else SourceBundle.model_validate(source_bundle)
    )

    abi_functions = _abi_function_names(bundle.abi)
    source_functions = _source_function_index(bundle.source_files)
    full_source = "\n".join(text for text in bundle.source_files.values() if isinstance(text, str))
    source_lower = full_source.lower()

    confirmed_functions: list[dict[str, Any]] = []
    inferred_functions: list[dict[str, Any]] = []
    confirmed_roles: list[dict[str, Any]] = []
    inferred_roles: list[dict[str, Any]] = []
    manual_checks: list[str] = []
    warnings: list[str] = []

    # Confirmed function findings come only from ABI/source function declarations.
    function_name_candidates = set(abi_functions.keys()) | set(source_functions.keys())
    for lowered in sorted(function_name_candidates):
        finding_type = _classify_function(lowered)
        if not finding_type:
            continue

        name = abi_functions.get(lowered) or source_functions.get(lowered, {}).get("name") or lowered
        in_abi = lowered in abi_functions
        in_source = lowered in source_functions
        evidence_parts = []
        if in_abi:
            evidence_parts.append("ABI function exists")
        if in_source:
            evidence_parts.append("Source function declaration found")
        source_location = None
        if in_source:
            source_location = source_functions[lowered]["locations"][0]

        _append_unique(
            confirmed_functions,
            _build_finding(
                name=name,
                finding_type=finding_type,
                confidence="confirmed",
                evidence="; ".join(evidence_parts),
                source_location=source_location,
            ),
        )

    confirmed_types = {item["type"] for item in confirmed_functions}

    # Inferred capabilities from source-only patterns (no direct function match).
    if "pause" not in confirmed_types and any(token in source_lower for token in ("pausable", "whennotpaused", "whenpaused", "event paused")):
        _append_unique(
            inferred_functions,
            _build_finding(
                name="pause-like control",
                finding_type="pause",
                confidence="inferred",
                evidence="Pausable-related source patterns detected without explicit pause function",
            ),
        )

    if "unpause" not in confirmed_types and any(token in source_lower for token in ("unpaused", "_unpause", "whenpaused")):
        _append_unique(
            inferred_functions,
            _build_finding(
                name="unpause-like control",
                finding_type="unpause",
                confidence="inferred",
                evidence="Unpause-related source patterns detected without explicit unpause function",
            ),
        )

    if "emergency_withdraw" not in confirmed_types and ("emergency" in source_lower and any(t in source_lower for t in ("withdraw", "rescue", "sweep"))):
        _append_unique(
            inferred_functions,
            _build_finding(
                name="emergency withdraw capability",
                finding_type="emergency_withdraw",
                confidence="inferred",
                evidence="Emergency and withdraw/rescue keywords found in source",
            ),
        )

    proxy_indicators = [
        "delegatecall",
        "proxyadmin",
        "transparentupgradeableproxy",
        "uups",
        "erc1967",
        "_authorizeupgrade",
        "implementation",
    ]
    has_proxy_indicator = any(token in source_lower for token in proxy_indicators)

    if "upgrade_admin" not in confirmed_types and has_proxy_indicator:
        _append_unique(
            inferred_functions,
            _build_finding(
                name="upgrade/admin control path",
                finding_type="upgrade_admin",
                confidence="inferred",
                evidence="Proxy/upgrade-related source indicators detected",
            ),
        )

    # Role detection and access-control patterns.
    has_ownable = "ownable" in source_lower
    has_pausable = "pausable" in source_lower
    has_access_control = "accesscontrol" in source_lower

    role_constants = {_normalize_role_name(match.group(1)) for match in _ROLE_CONSTANT_RE.finditer(full_source)}
    modifier_roles = {
        _normalize_role_name(match.group(1))
        for match in _ONLY_ROLE_RE.finditer(full_source)
        if _normalize_role_name(match.group(1))
    }

    function_names_lower = set(function_name_candidates)

    if has_ownable or "owner" in function_names_lower or "transferownership" in function_names_lower:
        _append_unique(
            confirmed_roles,
            _build_finding(
                name="owner",
                finding_type="owner",
                confidence="confirmed",
                evidence="Ownable pattern and/or owner control functions detected",
            ),
        )

    if has_access_control or "default_admin" in source_lower or "default_admin_role" in source_lower:
        _append_unique(
            confirmed_roles,
            _build_finding(
                name="admin",
                finding_type="admin",
                confidence="confirmed",
                evidence="AccessControl DEFAULT_ADMIN_ROLE pattern detected",
            ),
        )
    elif "admin" in function_names_lower or "changeadmin" in function_names_lower:
        _append_unique(
            inferred_roles,
            _build_finding(
                name="admin",
                finding_type="admin",
                confidence="inferred",
                evidence="Admin-related function names detected",
            ),
        )

    if "pauser" in role_constants or "pauser" in modifier_roles or "pauser_role" in source_lower:
        _append_unique(
            confirmed_roles,
            _build_finding(
                name="pauser",
                finding_type="pauser",
                confidence="confirmed",
                evidence="Pauser role constants/modifiers detected",
            ),
        )
    elif "pauser" in source_lower:
        _append_unique(
            inferred_roles,
            _build_finding(
                name="pauser",
                finding_type="pauser",
                confidence="inferred",
                evidence="Pauser terminology appears in source",
            ),
        )

    has_guardian_constant = "guardian" in role_constants or "guardian_role" in source_lower
    has_guardian_modifier = "guardian" in modifier_roles or "onlyguardian" in source_lower
    has_guardian_var = bool(re.search(r"\baddress\s+(public|private|internal)?\s*guardian\b", source_lower))

    if has_guardian_constant or has_guardian_modifier or has_guardian_var:
        _append_unique(
            confirmed_roles,
            _build_finding(
                name="guardian",
                finding_type="guardian",
                confidence="confirmed",
                evidence="Guardian role constants/modifiers/state variables detected",
            ),
        )
    elif "guardian" in source_lower:
        _append_unique(
            inferred_roles,
            _build_finding(
                name="guardian",
                finding_type="guardian",
                confidence="inferred",
                evidence="Guardian terminology appears in source",
            ),
        )

    # Access pattern findings feed manual checks and warnings.
    if has_ownable:
        manual_checks.append("Verify current owner signer access on-chain.")

    if has_access_control:
        manual_checks.append("Verify DEFAULT_ADMIN_ROLE and operational role members on-chain.")

    if has_proxy_indicator or any(item["type"] == "upgrade_admin" for item in confirmed_functions + inferred_functions):
        manual_checks.append("Verify proxy/implementation path and upgrade admin authority before execution.")

    if has_pausable and "pause" not in confirmed_types:
        warnings.append("Pausable pattern appears in source, but no confirmed pause function found in ABI/declarations.")

    if not confirmed_functions:
        warnings.append("No confirmed emergency control functions detected.")
        manual_checks.append("No deterministic emergency controls confirmed; prepare off-chain containment plan.")

    if not any(role["type"] in {"owner", "admin"} for role in confirmed_roles):
        warnings.append("No confirmed owner/admin role found from deterministic parse.")

    if not any(role["type"] == "guardian" for role in confirmed_roles):
        warnings.append("No confirmed guardian role found.")

    if not manual_checks:
        manual_checks.append("Verify signer permissions and contract state before executing any emergency action.")

    return {
        "confirmed_functions": confirmed_functions,
        "inferred_functions": inferred_functions,
        "confirmed_roles": confirmed_roles,
        "inferred_roles": inferred_roles,
        "manual_checks": manual_checks,
        "warnings": warnings,
    }


__all__ = ["extract_emergency_capabilities"]
