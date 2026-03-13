from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    chain_id: int
    address: str


class SourceBundle(BaseModel):
    chain_id: int
    address: str
    verified: bool
    contract_name: str
    abi: list[Any] | dict[str, Any] | str = Field(default_factory=list)
    compiler_version: str | None = None
    source_files: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
