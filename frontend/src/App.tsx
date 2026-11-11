import { useEffect, useState } from "react";
import Paper from "@mui/material/Paper";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";
import { api, type Asset, type AssetSummary, type Health, type Page, type RecordView } from "./api";
import { AssetDetailPage } from "./AssetDetailPage";
import { DashboardPage } from "./DashboardPage";
import { GapChart } from "./GapChart";
import { RecordsPage } from "./RecordsPage";
import { Shell } from "./Shell";
import { useRoute, type Route } from "./useRoute";
import "./App.css";

const RECORD_VIEWS: RecordView[] = ["findings", "patch-status", "controls", "incidents", "risks"];
const SUBTITLES: Record<string, string> = {
  dashboard: "Executive Security Dashboard", assets: "Enterprise Asset Intelligence",
  findings: "Vulnerability Management", "patch-status": "Patch Compliance", controls: "NIST 800-53 Control Compliance",
  incidents: "Security Operations", risks: "Executive Risk Intelligence",
};

// PRD Module 1: every figure carries data freshness and source systems.
function freshness(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${mins} min ago`;
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`;
  return `${Math.round(mins / 1440)} d ago`;
}

// The dashboard is the landing page (D-041); the inventory and the drill-down lists are views.
export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [route, go] = useRoute();
  const view = route.view ?? "dashboard";

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);

  let body;
  if (route.asset) body = <AssetDetailPage id={route.asset} onBack={() => go({ view: "assets" })} />;
  else if (view === "assets") body = <Inventory route={route} go={go} />;
  else if ((RECORD_VIEWS as string[]).includes(view)) body = <RecordsPage view={view as RecordView} />;
  else body = <DashboardPage go={go} />;

  return (
    <Shell health={health} subtitle={SUBTITLES[view] ?? SUBTITLES.dashboard}>
      <Tabs value={view === "assets" ? "assets" : "dashboard"} onChange={(_, v: string) => go({ view: v })} sx={{ mb: 2 }}>
        <Tab value="dashboard" label="Dashboard" />
        <Tab value="assets" label="Assets" />
      </Tabs>
      {body}
    </Shell>
  );
}

function Inventory({ route, go }: { route: Route; go: (r: Route) => void }) {
  const [page, setPage] = useState<Page<Asset> | null>(null);
  const [summary, setSummary] = useState<AssetSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const criticality = route.criticality ?? "";
  const navigate = (id: string) => go({ ...route, view: "assets", asset: id });

  useEffect(() => {
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
    <>
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
          <select value={criticality} onChange={(e) => { const { criticality: _, ...rest } = route; go(e.target.value ? { ...rest, view: "assets", criticality: e.target.value } : { ...rest, view: "assets" }); }}>
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
            <th>Service</th><th>Criticality</th><th>Env</th><th>State</th><th>Freshness</th><th>Sources</th>
          </tr>
        </thead>
        <tbody>
          {items.map((a) => (
            <tr key={a.id}>
              <td className="mono"><a href={`?view=assets&asset=${a.enterprise_asset_id}`} onClick={(e) => { e.preventDefault(); navigate(a.enterprise_asset_id); }}>{a.enterprise_asset_id}</a></td>
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
            </tr>
          ))}
        </tbody>
      </table>
    </>
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
