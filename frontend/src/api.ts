// Typed client for the skeleton's API (PRD §8). Types mirror backend/app/api/schemas.py.
export interface Asset {
  id: number;
  enterprise_asset_id: string;
  hostname: string | null;
  ip_address: string | null;
  asset_type: string;
  asset_owner: string | null;
  business_unit: string | null;
  business_service: string | null;
  location: string | null;
  operating_system: string | null;
  mac_address: string | null;
  criticality: "critical" | "high" | "medium" | "low" | "unknown";
  environment: string;
  lifecycle_state: "active" | "potentially_inactive" | "retired" | "unknown";
  last_seen_at: string;
  source_systems: string[];
  flags: string[];
  data_completeness: { complete: boolean; missing_fields: string[] } | null;
}

export interface SourceSystemRecord {
  source_system: string;
  source_record_id: string;
  first_seen_at: string;
  last_seen_at: string;
}

export interface AssetDetail extends Omit<Asset, "source_systems"> {
  source_systems: SourceSystemRecord[];
}

export interface HistoryEntry {
  changed_at: string;
  changed_by: string;
  field: string;
  old_value: string | null;
  new_value: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AssetSummary {
  total_assets: number;
  without_owner: number;
  without_criticality: number;
  potentially_inactive: number;
  data_as_of: string | null;
}

export interface Health {
  status: string;
  database: string;
  auth_provider: string;
  llm_provider: string;
  version: string;
  harness_version: string;
}

export interface Me {
  subject: string;
  roles: string[];
  permissions: string[];
}

export interface AgentResponse {
  status: "succeeded" | "failed";
  output: {
    executive_summary?: string;
    supporting_facts?: Record<string, unknown>;
    business_impact?: string;
    recommended_action?: string;
    source_references?: string[];
    last_updated?: string;
    data_completeness?: { complete: boolean; missing_fields: string[] };
    data_quality_flags?: string[];
  };
  error: string | null;
  tool_calls: number;
  llm_calls: number;
  guardrail_events: string[];
}

// The browser calls /api on its own origin; Vite (dev) or nginx (container) forwards it to the API.
// Development only: a fixed token. With single sign-on the token comes from the login flow (D-003).
export function getToken(): string {
  let saved: string | null = null;
  try { saved = localStorage.getItem("ccc_token"); } catch { /* storage unavailable */ }
  return saved ?? import.meta.env.VITE_DEV_TOKEN ?? "dev-ciso-token";
}

async function request<T>(path: string, method = "GET"): Promise<T> {
  const res = await fetch(path, { method, headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(`${res.status}: ${body.detail ?? res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  assets: (params: Record<string, string> = {}) =>
    request<Page<Asset>>(`/api/v1/assets?${new URLSearchParams(params)}`),
  asset: (enterpriseAssetId: string) => request<AssetDetail>(`/api/v1/assets/${encodeURIComponent(enterpriseAssetId)}`),
  assetHistory: (enterpriseAssetId: string, params: Record<string, string> = {}) =>
    request<Page<HistoryEntry>>(`/api/v1/assets/${encodeURIComponent(enterpriseAssetId)}/history?${new URLSearchParams(params)}`),
  assetSummary: () => request<AssetSummary>("/api/v1/assets/summary"),
  brief: (assetId: string) =>
    request<AgentResponse>(`/api/v1/assets/${encodeURIComponent(assetId)}/brief`, "POST"),
  me: () => request<Me>("/api/v1/me"),
  health: () => fetch("/api/v1/platform/health").then((r) => r.json() as Promise<Health>),
};

// PRD Module 1: one tile. Types mirror ccc/api/schemas.py (Kpi, TopRisk, Dashboard, the list records).
export interface Kpi {
  kpi: string;
  value: number | null;
  unit: "count" | "percent" | "score";
  previous_value: number | null;
  previous_period: string | null;
  trend: "up" | "down" | "flat" | "no_history";
  good_direction: "up" | "down";
  data_as_of: string | null;
  source_systems: string[];
  drilldown: string;
  formula_version: string;
  mock: boolean;
}

export interface TopRisk {
  title: string;
  business_unit: string | null;
  business_service: string | null;
  affected_assets: string[];
  rating: Asset["criticality"];
  business_impact: string;
  owner: string | null;
  recommended_action: string;
  last_updated: string;
  source_system: string;
  model_version: string;
}

export interface Dashboard {
  generated_at: string;
  kpis: Kpi[];
  top_risks: TopRisk[];
}

export type RecordView = "findings" | "patch-status" | "controls" | "incidents" | "risks";
export type DrilldownRecord = Record<string, string | number | boolean | string[] | null>;

export const recordsApi = {
  dashboard: () => request<Dashboard>("/api/v1/dashboard"),
  list: (view: RecordView, params: Record<string, string> = {}) =>
    request<Page<DrilldownRecord>>(`/api/v1/${view}?${new URLSearchParams(params)}`),
};
