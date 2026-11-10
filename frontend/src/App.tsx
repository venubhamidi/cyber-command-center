import { useEffect, useState } from "react";
import { api, type AgentResponse, type Asset, type AssetSummary, type Health, type Page } from "./api";
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
  const [review, setReview] = useState<{ id: string; result?: AgentResponse; error?: string } | null>(null);

  function runReview(id: string) {
    setReview({ id });
    api.review(id).then((result) => setReview({ id, result })).catch((e: Error) => setReview({ id, error: e.message }));
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
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Cyber Command Center</h1>
          <p className="sub">Enterprise Asset Intelligence</p>
        </div>
        <div className={`health ${health?.status ?? "down"}`}>
          {health
            ? `API ${health.status} · db ${health.database} · login ${health.auth_provider} · model ${health.llm_provider} · harness ${health.harness_version}`
            : "API unreachable"}
        </div>
      </header>

      <section className="kpis">
        <Kpi label="Assets in inventory" value={summary?.total_assets ?? "—"} />
        <Kpi label="Without owner" value={summary?.without_owner ?? "—"} warn={(summary?.without_owner ?? 0) > 0} />
        <Kpi label="Without criticality" value={summary?.without_criticality ?? "—"} warn={(summary?.without_criticality ?? 0) > 0} />
        <Kpi label="Potentially inactive" value={summary?.potentially_inactive ?? "—"} warn={(summary?.potentially_inactive ?? 0) > 0} />
      </section>
      <p className="asof">
        Whole inventory · data as of {summary?.data_as_of ? freshness(summary.data_as_of) : "unknown"}
      </p>

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
              <td className="mono small">{a.sources.join(", ")}</td>
              <td><button onClick={() => runReview(a.enterprise_asset_id)}>Brief</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {review && (
        <section className="review" aria-live="polite">
          <h2>Assistant brief on {review.id} <span className="advisory">advisory</span></h2>
          {!review.result && !review.error && <p className="sub">Running…</p>}
          {review.error && <div className="error">Brief failed: {review.error}</div>}
          {review.result?.status === "failed" && <div className="error">Agent failed: {review.result.error}</div>}
          {review.result?.status === "succeeded" && (
            <>
              <p>{review.result.output.executive_summary}</p>
              <p><strong>Business impact:</strong> {review.result.output.business_impact}</p>
              <p><strong>Recommended action:</strong> {review.result.output.recommended_action}</p>
              <p className="small">
                Gaps (computed by rules): {review.result.output.data_quality_flags?.join(", ") || "none"} · missing fields:{" "}
                {review.result.output.data_completeness?.missing_fields.join(", ") || "none"} · sources:{" "}
                {review.result.output.source_references?.join(", ")} · last updated {review.result.output.last_updated}
                {review.result.guardrail_events.length > 0 && ` · guardrails: ${review.result.guardrail_events.join(", ")}`}
              </p>
            </>
          )}
        </section>
      )}
    </main>
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
