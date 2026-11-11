// Drill-down from a dashboard tile (D-040): a plain, read-only list of the records behind the number,
// with their provenance. Filters arrive with each module's own slice.
import { useEffect, useState } from "react";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { recordsApi, type DrilldownRecord, type Page, type RecordView } from "./api";

const COLUMNS: Record<RecordView, string[]> = {
  findings: ["enterprise_asset_id", "severity", "cve", "title", "status", "exploitable", "known_exploited", "first_seen_at", "due_at", "closed_at"],
  "patch-status": ["enterprise_asset_id", "state", "missing_count", "collected_at"],
  controls: ["control_id", "title", "status", "effectiveness", "assessor", "assessed_at"],
  incidents: ["title", "severity", "status", "opened_at", "closed_at"],
  risks: ["title", "rating", "business_unit", "business_service", "affected_assets", "owner", "recommended_action", "last_updated"],
};
const TITLES: Record<RecordView, string> = {
  findings: "Vulnerability findings", "patch-status": "Patch status", controls: "Control assessments",
  incidents: "Incidents", risks: "Enterprise risks",
};

function cell(v: DrilldownRecord[string]): string {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v)) return v.slice(0, 10);   // the UTC calendar day, as stored
  return String(v).replace(/_/g, " ");
}

export function RecordsPage({ view }: { view: RecordView }) {
  const [page, setPage] = useState<Page<DrilldownRecord> | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setPage(null); setError(null);
    recordsApi.list(view, { limit: "100" }).then(setPage).catch((e: Error) => setError(e.message));
  }, [view]);

  const cols = COLUMNS[view];
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
        {TITLES[view]}{page && ` · ${page.items.length} of ${page.total}`}
      </Typography>
      {error && <div className="error">Could not load: {error}</div>}
      {page && (
        <Table size="small">
          <TableHead>
            <TableRow>{cols.map((c) => <TableCell key={c}>{c.replace(/_/g, " ")}</TableCell>)}<TableCell>source</TableCell></TableRow>
          </TableHead>
          <TableBody>
            {page.items.map((r) => (
              <TableRow key={`${r.source_system}:${r.source_record_id}`}>
                {cols.map((c) => {
                  const v = r[c];
                  const pill = c === "severity" || c === "rating";
                  const blankWhenNull = c === "closed_at";          // an open record has no close date by design
                  return (
                    <TableCell key={c} className={c === "enterprise_asset_id" || c === "cve" ? "mono" : undefined}>
                      {v === null || v === undefined ? (blankWhenNull ? "" : <span className="missing">unknown</span>)
                        : pill ? <span className={`pill crit-${String(v)}`}>{String(v)}</span> : cell(v)}
                    </TableCell>
                  );
                })}
                <TableCell className="small">{String(r.source_system)} · {String(r.source_record_id)}{r.data_quality_status !== "ok" && ` · ${String(r.data_quality_status)}`}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Paper>
  );
}
