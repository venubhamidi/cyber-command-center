from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DataCompleteness(BaseModel):
    """PRD Module 7 part 7: whether the record has every required field (D-031)."""

    complete: bool
    missing_fields: list[str]


class Asset(BaseModel):
    id: int
    enterprise_asset_id: str
    hostname: str | None
    ip_address: str | None
    mac_address: str | None
    asset_type: str
    asset_owner: str | None
    business_unit: str | None
    business_service: str | None
    criticality: str
    location: str | None
    environment: str
    operating_system: str | None
    lifecycle_state: str
    last_seen_at: datetime
    # PRD Module 1: every KPI/record carries freshness and source systems
    source_systems: list[str] = Field(default_factory=list)
    # Derived at read time by the rules in ccc/assets.py; never stored (ARCHITECTURE.md, database design)
    flags: list[str] = Field(default_factory=list)
    data_completeness: DataCompleteness | None = None


class SourceSystemRecord(BaseModel):
    """One source system's report of an asset (PRD §7 provenance): who reported it and when."""

    source_system: str
    source_record_id: str
    first_seen_at: datetime
    last_seen_at: datetime


class AssetDetail(Asset):
    """The asset detail (PRD §11): the inventory row plus each source system's first and last sighting."""

    source_systems: list[SourceSystemRecord] = Field(default_factory=list)   # type: ignore[assignment]


class AssetSummary(BaseModel):
    """Enterprise-wide asset KPIs, computed in SQL over the whole inventory."""

    total_assets: int
    without_owner: int
    without_criticality: int
    potentially_inactive: int
    data_as_of: datetime | None   # newest last_seen_at; None when the inventory is empty


class UsageRow(BaseModel):
    agent_id: str | None
    provider: str
    model_id: str
    executions: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float | None
