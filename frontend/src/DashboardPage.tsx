// Executive Security Dashboard (PRD Module 1): eight KPI tiles and the top five risks.
// Every number, trend and ordering comes from /api/v1/dashboard; the browser only displays.
import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Link from "@mui/material/Link";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { api, recordsApi, type Dashboard, type Kpi, type Me } from "./api";
import { routeOf, type Route } from "./useRoute";

const LABELS: Record<string, string> = {
  enterprise_risk_score: "Enterprise risk score", security_posture: "Security posture",
  patch_compliance: "Patch compliance", vulnerability_exposure: "Vulnerability exposure",
  nist_compliance: "NIST compliance", critical_assets: "Critical assets",
  open_incidents: "Open incidents", remediation_sla: "Remediation within SLA",
};

// Each drill-down keeps its module's permission (D-040); the link shows only to a caller who holds it.
const VIEW_PERMISSION: Record<string, string> = {
  assets: "assets:read", findings: "vulns:read", "patch-status": "patch:read", controls: "controls:read",
  incidents: "incidents:read", risks: "risks:read",
};

function mayDrill(k: Kpi, me: Me | null): boolean {
  const view = routeOf(k.drilldown).view;
  const needed = VIEW_PERMISSION[view];
  return !!me && !!needed && (me.permissions.includes("*") || me.permissions.includes(needed));
}

function fmt(value: number | null, unit: Kpi["unit"]): string {
  if (value === null) return "unknown";
  return unit === "percent" ? `${value}%` : String(value);
}

function freshness(iso: string | null): string {
  if (!iso) return "no data";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${mins} min ago`;
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`;
  return `${Math.round(mins / 1440)} d ago`;
}

function Tile({ k, me, go }: { k: Kpi; me: Me | null; go: (r: Route) => void }) {
  const arrow = { up: "▲", down: "▼", flat: "■", no_history: "" }[k.trend];
  const improved = k.trend === "flat" || k.trend === "no_history" ? null : k.trend === k.good_direction;
  const trendColor = improved === null ? "text.secondary" : improved ? "success.main" : "error.main";
  const provisional = k.formula_version === "v0" && (k.kpi === "enterprise_risk_score" || k.kpi === "security_posture");
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="body2" color="text.secondary">{LABELS[k.kpi] ?? k.kpi}</Typography>
      <Stack direction="row" spacing={1} sx={{ alignItems: "baseline" }}>
        <Typography sx={{ fontSize: 30, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}
          className={k.value === null ? "missing" : undefined}>{fmt(k.value, k.unit)}</Typography>
        {arrow && <Typography sx={{ color: trendColor, fontSize: 14 }}>{arrow}</Typography>}
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
        {k.previous_value === null ? "no previous period" : `previous ${fmt(k.previous_value, k.unit)} (${k.previous_period})`}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
        as of {freshness(k.data_as_of)} · {k.source_systems.length ? k.source_systems.join(", ") : "no source"}
      </Typography>
      <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1, alignItems: "center", flexWrap: "wrap" }}>
        {k.mock && <Chip size="small" color="warning" variant="outlined" label="mock data" />}
        {provisional && <Chip size="small" variant="outlined" label="provisional v0 (D-039)" />}
        {mayDrill(k, me) && (
          <Link href={k.drilldown} onClick={(e) => { e.preventDefault(); go(routeOf(k.drilldown)); }} sx={{ fontSize: 12 }}>
            Drill down
          </Link>
        )}
      </Stack>
    </Paper>
  );
}

export function DashboardPage({ go }: { go: (r: Route) => void }) {
  const [data, setData] = useState<Dashboard | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    recordsApi.dashboard().then(setData).catch((e: Error) => setError(e.message));
    api.me().then(setMe).catch(() => setMe(null));
  }, []);

  if (error) return <div className="error">Could not load the dashboard: {error}</div>;
  if (!data) return <Typography color="text.secondary">Loading…</Typography>;
  return (
    <>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 1.5, mb: 3 }}>
        {data.kpis.map((k) => <Tile key={k.kpi} k={k} me={me} go={go} />)}
      </Box>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>Top five enterprise cybersecurity risks</Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Risk</TableCell><TableCell>Rating</TableCell><TableCell>Business unit</TableCell>
              <TableCell>Service</TableCell><TableCell>Assets</TableCell><TableCell>Business impact</TableCell>
              <TableCell>Owner</TableCell><TableCell>Recommended action</TableCell><TableCell>Updated</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.top_risks.map((r) => (
              <TableRow key={r.title}>
                <TableCell>{r.title}<div className="small">{r.source_system} · {r.model_version}</div></TableCell>
                <TableCell><span className={`pill crit-${r.rating}`}>{r.rating}</span></TableCell>
                <TableCell>{r.business_unit ?? <span className="missing">missing</span>}</TableCell>
                <TableCell>{r.business_service ?? <span className="missing">missing</span>}</TableCell>
                <TableCell className="mono">
                  {r.affected_assets.map((id) => (
                    <div key={id}><Link href={`?view=assets&asset=${id}`} onClick={(e) => { e.preventDefault(); go({ view: "assets", asset: id }); }}>{id}</Link></div>
                  ))}
                </TableCell>
                <TableCell>{r.business_impact}</TableCell>
                <TableCell>{r.owner ?? <span className="missing">missing</span>}</TableCell>
                <TableCell>{r.recommended_action}</TableCell>
                <TableCell>{r.last_updated.slice(0, 10)}</TableCell>
              </TableRow>
            ))}
            {data.top_risks.length === 0 && <TableRow><TableCell colSpan={9}><span className="missing">no risks reported</span></TableCell></TableRow>}
          </TableBody>
        </Table>
      </Paper>
    </>
  );
}
