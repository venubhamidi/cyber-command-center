// Asset detail screen (PRD §11): profile, data-quality flags, completeness, source systems.
// Everything shown comes from the detail endpoint; the browser computes nothing.
import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { api, type AgentResponse, type AssetDetail, type HistoryEntry, type Me } from "./api";

const PROFILE: { key: keyof AssetDetail; label: string }[] = [
  { key: "hostname", label: "Name" }, { key: "enterprise_asset_id", label: "Enterprise asset ID" },
  { key: "asset_owner", label: "Owner" }, { key: "business_unit", label: "Business unit" },
  { key: "criticality", label: "Criticality" }, { key: "environment", label: "Environment" },
  { key: "business_service", label: "Business service" }, { key: "location", label: "Location" },
  { key: "asset_type", label: "Type" }, { key: "operating_system", label: "Operating system" },
  { key: "lifecycle_state", label: "Lifecycle state" }, { key: "ip_address", label: "IP address" },
];

export function when(iso: string): string {
  return new Date(iso).toLocaleString();
}

function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return <span className="missing">missing</span>;
  if (value === "unknown") return <span className="missing">unknown</span>;
  return <>{String(value).replace("_", " ")}</>;
}

const HISTORY_PAGE = 50;

function History({ id }: { id: string }) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load(offset: number) {
    api.assetHistory(id, { limit: String(HISTORY_PAGE), offset: String(offset) })
      .then((page) => { setTotal(page.total); setEntries((prev) => (offset === 0 ? page.items : [...prev, ...page.items])); })
      .catch((e: Error) => setError(e.message));
  }
  useEffect(() => { load(0); }, [id]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" color="text.secondary" gutterBottom>History{total !== null && ` · ${total} change${total === 1 ? "" : "s"}`}</Typography>
      {error && <div className="error">Could not load history: {error}</div>}
      {total === 0 && <Typography variant="body2">No changes recorded.</Typography>}
      {entries.length > 0 && (
        <Table size="small">
          <TableHead>
            <TableRow><TableCell>When</TableCell><TableCell>By</TableCell><TableCell>Field</TableCell><TableCell>From</TableCell><TableCell>To</TableCell></TableRow>
          </TableHead>
          <TableBody>
            {entries.map((h, i) => (
              <TableRow key={i}>
                <TableCell>{when(h.changed_at)}</TableCell>
                <TableCell className="mono">{h.changed_by}</TableCell>
                <TableCell>{h.field.replaceAll("_", " ")}</TableCell>
                <TableCell><Value value={h.old_value} /></TableCell>
                <TableCell><Value value={h.new_value} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {total !== null && entries.length < total && (
        <Button size="small" sx={{ mt: 1 }} onClick={() => load(entries.length)}>Load more ({total - entries.length} older)</Button>
      )}
    </Paper>
  );
}

function canRunAgents(me: Me | null): boolean {
  return !!me && (me.permissions.includes("agents:run") || me.permissions.includes("*"));
}

// The seven-part answer (PRD Module 7). Every part is shown; an empty one reads "unavailable".
function Brief({ id }: { id: string }) {
  const [state, setState] = useState<{ running: boolean; result?: AgentResponse; error?: string } | null>(null);

  function run() {
    setState({ running: true });
    api.brief(id).then((result) => setState({ running: false, result })).catch((e: Error) => setState({ running: false, error: e.message }));
  }
  const out = state?.result?.status === "succeeded" ? state.result.output : null;
  const part = (v: string | undefined) => v || "unavailable";

  return (
    <Paper variant="outlined" sx={{ p: 2 }} aria-live="polite">
      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <Typography variant="subtitle2" color="text.secondary">Assistant brief <span className="advisory">advisory</span></Typography>
        <Button variant="contained" size="small" onClick={run} disabled={state?.running}>{state?.running ? "Running…" : "Brief"}</Button>
      </Box>
      {state?.error && <div className="error" style={{ marginTop: 12 }}>Brief failed: {state.error}</div>}
      {state?.result?.status === "failed" && <div className="error" style={{ marginTop: 12 }}>Agent failed: {state.result.error ?? "unknown reason"}</div>}
      {out && (
        <Stack spacing={1} sx={{ mt: 1.5 }}>
          <Typography variant="body2"><strong>Executive summary.</strong> {part(out.executive_summary)}</Typography>
          <Typography variant="body2"><strong>Supporting facts.</strong> {out.supporting_facts ? "The asset record as stored (shown above); flags: " + ((out.data_quality_flags ?? []).map((f) => f.replaceAll("_", " ")).join(", ") || "none") + "." : "unavailable"}</Typography>
          <Typography variant="body2"><strong>Business impact.</strong> {part(out.business_impact)}</Typography>
          <Typography variant="body2"><strong>Recommended action.</strong> {part(out.recommended_action)}</Typography>
          <Typography variant="body2"><strong>Source references.</strong> {out.source_references?.length ? out.source_references.join(", ") : "unavailable"}</Typography>
          <Typography variant="body2"><strong>Last updated.</strong> {out.last_updated ? when(out.last_updated) : "unavailable"}</Typography>
          <Typography variant="body2"><strong>Data completeness.</strong> {out.data_completeness ? (out.data_completeness.complete ? "complete" : `incomplete; missing ${out.data_completeness.missing_fields.join(", ")}`) : "unavailable"}</Typography>
          {state?.result && state.result.guardrail_events.length > 0 && (
            <Typography variant="caption" color="text.secondary">Guardrails: {state.result.guardrail_events.join(", ")}</Typography>
          )}
        </Stack>
      )}
    </Paper>
  );
}

export function AssetDetailPage({ id, onBack }: { id: string; onBack: () => void }) {
  const [asset, setAsset] = useState<AssetDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    api.asset(id).then(setAsset).catch((e: Error) => setError(e.message));
    api.me().then(setMe).catch(() => setMe(null));
  }, [id]);

  return (
    <Stack spacing={2}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <Button variant="outlined" size="small" onClick={onBack}>← Inventory</Button>
        <Typography variant="h6" component="h2" sx={{ fontWeight: 600 }}>
          {asset?.hostname ?? id} <Box component="span" className="mono" sx={{ color: "text.secondary", fontWeight: 400, ml: 1 }}>{id}</Box>
        </Typography>
      </Box>

      {error && <div className="error">{error.startsWith("403") ? "You do not have permission to view assets." : `Could not load asset: ${error}`}</div>}

      {asset && (
        <>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>Asset profile</Typography>
            <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 1.5 }}>
              {PROFILE.map((f) => (
                <Box key={f.key}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>{f.label}</Typography>
                  <Typography variant="body2"><Value value={asset[f.key]} /></Typography>
                </Box>
              ))}
            </Box>
          </Paper>

          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>Data quality</Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1 }}>
              {asset.flags.length === 0 && <Chip size="small" label="No gaps" color="success" variant="outlined" />}
              {asset.flags.map((f) => <Chip key={f} size="small" color="warning" variant="outlined" label={f.replaceAll("_", " ")} />)}
            </Stack>
            <Typography variant="body2" sx={{ mt: 1 }}>
              {asset.data_completeness?.complete
                ? "Record complete: every required field is present."
                : `Record incomplete. Missing: ${asset.data_completeness?.missing_fields.join(", ") ?? "unknown"}.`}
            </Typography>
          </Paper>

          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>Source systems</Typography>
            <Table size="small">
              <TableHead>
                <TableRow><TableCell>Source system</TableCell><TableCell>Source record</TableCell><TableCell>First seen</TableCell><TableCell>Last seen</TableCell></TableRow>
              </TableHead>
              <TableBody>
                {asset.source_systems.map((s) => (
                  <TableRow key={s.source_system}>
                    <TableCell className="mono">{s.source_system}</TableCell>
                    <TableCell className="mono">{s.source_record_id}</TableCell>
                    <TableCell>{when(s.first_seen_at)}</TableCell>
                    <TableCell>{when(s.last_seen_at)}</TableCell>
                  </TableRow>
                ))}
                {asset.source_systems.length === 0 && <TableRow><TableCell colSpan={4}>No source system has reported this asset.</TableCell></TableRow>}
              </TableBody>
            </Table>
          </Paper>

          {canRunAgents(me) && <Brief id={id} />}

          <History id={id} />
        </>
      )}
    </Stack>
  );
}
