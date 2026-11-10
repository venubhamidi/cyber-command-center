"""Evaluation suites for the Command Center's agents:  python -m harness.evals ccc

Suites use fixed fixture records, not the database, so results are repeatable."""
from __future__ import annotations

import json
from pathlib import Path

from ccc.agents.asset_agent import AssetSummaryAgent
from ccc.config import settings
from harness.agents.contract import build_agent
from harness.evals import EvalSuite
from harness.testing import DictToolClient

HERE = Path(__file__).resolve().parent
FIXTURES: dict[str, dict] = json.loads((HERE / "fixtures.json").read_text())

EVAL_SUITES = {
    "asset-summary": EvalSuite(
        agent_factory=lambda: build_agent(AssetSummaryAgent, settings, DictToolClient(
            {"get_asset": lambda enterprise_asset_id: FIXTURES.get(enterprise_asset_id)})),
        cases_dir=HERE / "asset_summary"),
}
