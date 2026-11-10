"""Asset Summary Agent.

Python decides the facts: which data-quality gaps an asset has, which required fields are
missing, where the record came from and how fresh it is. The model only writes the executive
wording, as a validated structure. Nothing the model says changes stored data (PRD Module 5:
agents recommend, never decide).

The output follows the PRD Module 7 response format: executive summary, supporting facts,
business impact, recommended action, source references, last-updated time, data completeness.

    python -m ccc.agents.asset_agent EA-000003
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from ccc.assets import asset_flags, missing_required_fields
from ccc.config import settings
from harness.agents.contract import Agent, AgentRequest, AgentResponse, AgentRunner, AgentSpec, ToolClient, build_agent
from harness.agents.mcp_client import McpStdioToolClient
from harness.db import conn_factory

REPO_ROOT = str(Path(__file__).resolve().parents[2])

SYSTEM = ("You brief a CISO on one enterprise asset. Use plain business language. State only facts "
          "that are in the data; never invent values. If a field is missing, say it is missing.")


class AssetBrief(BaseModel):
    executive_summary: str       # two or three sentences
    business_impact: str         # what the asset's gaps could mean for the business service
    recommended_action: str      # one concrete action for a person to consider


class AssetSummaryAgent(Agent):
    spec = AgentSpec(agent_id="asset-summary-agent", name="Asset Summary Agent", version="0.2.0",
                     description="Briefs an executive on one asset and flags data-quality gaps.",
                     allowed_tools=["get_asset", "list_asset_gaps"])

    def run(self, request: AgentRequest) -> AgentResponse:
        asset = self.call_tool("get_asset", enterprise_asset_id=request.input["enterprise_asset_id"])
        if asset is None:
            return self.fail(request, "asset_not_found", f"No asset {request.input['enterprise_asset_id']}")

        flags = asset_flags(asset)                       # computed by rules, never inferred by the model
        missing = missing_required_fields(asset)
        brief = self.llm(SYSTEM, f"Brief me on this asset. Known data-quality gaps: {flags or 'none'}.",
                         data=json.dumps(asset), schema=AssetBrief)
        return self.ok(request, {
            "executive_summary": brief.executive_summary,
            "supporting_facts": asset,
            "business_impact": brief.business_impact,
            "recommended_action": brief.recommended_action,
            "source_references": asset.get("sources", []),
            "last_updated": asset.get("last_seen_at"),
            "data_completeness": {"complete": not missing, "missing_fields": missing},
            "data_quality_flags": flags,
        }, "Facts, flags, sources, timestamp and completeness come from the database and rules in code. "
           "The summary, impact and recommended action are model-written from those facts.")


def mcp_tools() -> ToolClient:
    return McpStdioToolClient(sys.executable, ["-m", "ccc.mcp_servers.asset_mcp.server"], cwd=REPO_ROOT)


def summarize_asset(enterprise_asset_id: str, requested_by: str, tools: ToolClient | None = None) -> AgentResponse:
    agent = build_agent(AssetSummaryAgent, settings, tools or mcp_tools())
    return AgentRunner(conn_factory(settings.database_url)).execute(
        agent, AgentRequest(requested_by=requested_by, input={"enterprise_asset_id": enterprise_asset_id}))


if __name__ == "__main__":
    response = summarize_asset(sys.argv[1] if len(sys.argv) > 1 else "EA-000003", requested_by="cli:dev")
    print(json.dumps(response.model_dump(mode="json"), indent=2))
