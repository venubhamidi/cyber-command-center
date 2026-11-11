"""Mock connectors: one per source system the dashboard reads, each returning the records in
`ccc/mock/<kind>.json`. A real connector (Tenable, SCCM, the GRC tool, Chronicle) replaces a mock
by changing APP_CONNECTORS; the ingestion code does not change.

A connector only fetches. It never touches the database (root CONTEXT.md: connector).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from harness.plugins import register

MOCK_DIR = Path(__file__).resolve().parents[1] / "mock"

KINDS = ("findings", "patch_status", "control_assessments", "incidents", "risks", "kpi_snapshots")


@dataclass
class Feed:
    """What a connector returns: the source, the table kind, when it was collected, the records."""

    source_system: str
    kind: str
    collected_at: str
    records: list[dict[str, Any]]


class Connector(Protocol):
    def fetch(self) -> Feed: ...


class MockConnector:
    def __init__(self, path: Path):
        self.path = path

    def fetch(self) -> Feed:
        data = json.loads(self.path.read_text())
        if data["kind"] not in KINDS:
            raise ValueError(f"{self.path}: unknown kind {data['kind']!r}")
        return Feed(data["source_system"], data["kind"], data["collected_at"], data["records"])


def _mock(name: str, filename: str) -> None:
    register("connector", name)(lambda settings: MockConnector(MOCK_DIR / filename))


_mock("mock_tenable", "findings.json")
_mock("mock_sccm", "patch_status.json")
_mock("mock_grc", "control_assessments.json")
_mock("mock_chronicle", "incidents.json")
_mock("mock_risk", "risks.json")
_mock("mock_history", "kpi_snapshots.json")
