import { useEffect, useState } from "react";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { api, type AgentResponse, type Asset, type AssetSummary, type Health, type Page } from "./api";
import { GapChart } from "./GapChart";
import { Shell } from "./Shell";
import "./App.css";

// PRD Module 1: every figure carries data freshness and source systems.
function freshness(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${mins} min ago`;
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`;
  return `${Math.round(mins / 1440)} d ago`;
}

export default function App() {
  const [page, setPage] = useState<Page<Asset> | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [summary, setSummary] = useState<AssetSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [criticality, setCriticality] = useState<string>("");
  const [brief, setBrief] = useState<{ id: string; result?: AgentResponse; error?: string } | null>(null);

  function runBrief(id: string) {
    setBrief({ id });
    api.brief(id).then((result) => setBrief({ id, result })).catch((e: Error) => setBrief({ id, error: e.message }));
  }

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    // KPIs are counted by the backend over the whole inventory, never from the rows on screen.
    api.assetSummary().then(setSummary).catch(() => setSummary(null));
  }, []);

  useEffect(() => {
    setError(null);
    api
      .assets(criticality ? { criticality } : {})
      .then(setPage)
      .catch((e: Error) => setError(e.message));
  }, [criticality]);

  const items = page?.items ?? [];

  return (
    <Shell health={health}>
      <section className="kpis">
        <Kpi label="Assets in inventory" value={summary?.total_assets ?? "—"} />
        <Kpi label="Without owner" value={summary?.without_owner ?? "—"} warn={(summary?.without_owner ?? 0) > 0} />
        <Kpi label="Without criticality" value={summary?.without_criticality ?? "—"} warn={(summary?.without_criticality ?? 0) > 0} />
        <Kpi label="Potentially inactive" value={summary?.potentially_inactive ?? "—"} warn={(summary?.potentially_inactive ?? 0) > 0} />
      </section>
      <p className="asof">
        Whole inventory · data as of {summary?.data_as_of ? freshness(summary.data_as_of) : "unknown"}
      </p>
      {summary && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" color="text.secondary">Data-quality gaps across the inventory</Typography>
          <GapChart summary={summary} />
        </Paper>
      )}

      <section className="toolbar">
        <label>
          Criticality
          <select value={criticality} onChange={(e) => setCriticality(e.target.value)}>
            <option value="">All</option>
            {["critical", "high", "medium", "low", "unknown"].map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        {page && <span className="count">{page.items.length} of {page.total}</span>}
      </section>

      {error && <div className="error">Could not load assets: {error}</div>}

      <table className="assets">
        <thead>
          <tr>
            <th>Asset ID</th><th>Hostname</th><th>Type</th><th>Owner</th><th>Business unit</th>
            <th>Service</th><th>Criticality</th><th>Env</th><th>State</th><th>Freshness</th><th>Sources</th><th />
          </tr>
        </thead>
        <tbody>
          {items.map((a) => (
            <tr key={a.id}>
              <td className="mono">{a.enterprise_asset_id}</td>
              <td className="mono">{a.hostname ?? <Missing />}</td>
              <td>{a.asset_type}</td>
              <td>{a.asset_owner ?? <Missing />}</td>
              <td>{a.business_unit}</td>
              <td>{a.business_service}</td>
              <td><span className={`pill crit-${a.criticality}`}>{a.criticality}</span></td>
              <td>{a.environment}</td>
              <td><span className={`pill state-${a.lifecycle_state}`}>{a.lifecycle_state.replace("_", " ")}</span></td>
              <td>{freshness(a.last_seen_at)}</td>
              <td className="mono small">{a.source_systems.join(", ")}</td>
              <td><button onClick={() => runBrief(a.enterprise_asset_id)}>Brief</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {brief && (
        <section className="brief" aria-live="polite">
          <h2>Assistant brief on {brief.id} <span className="advisory">advisory</span></h2>
          {!brief.result && !brief.error && <p className="sub">Running…</p>}
          {brief.error && <div className="error">Brief failed: {brief.error}</div>}
          {brief.result?.status === "failed" && <div className="error">Agent failed: {brief.result.error}</div>}
          {brief.result?.status === "succeeded" && (
            <>
              <p>{brief.result.output.executive_summary}</p>
              <p><strong>Business impact:</strong> {brief.result.output.business_impact}</p>
              <p><strong>Recommended action:</strong> {brief.result.output.recommended_action}</p>
              <p className="small">
                Gaps (computed by rules): {brief.result.output.data_quality_flags?.join(", ") || "none"} · missing fields:{" "}
                {brief.result.output.data_completeness?.missing_fields.join(", ") || "none"} · sources:{" "}
                {brief.result.output.source_references?.join(", ")} · last updated {brief.result.output.last_updated}
                {brief.result.guardrail_events.length > 0 && ` · guardrails: ${brief.result.guardrail_events.join(", ")}`}
              </p>
            </>
          )}
        </section>
      )}
    </Shell>
  );
}

function Kpi({ label, value, warn }: { label: string; value: number | string; warn?: boolean }) {
  return (
    <div className={`kpi ${warn ? "warn" : ""}`}>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

function Missing() {
  return <span className="missing">missing</span>;
}
