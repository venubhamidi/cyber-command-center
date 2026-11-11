# Glossary: Cyber Command Center

The domain's terms, from `docs/PRD.pdf` (v1.0) and the code. One meaning per word. Wording was
settled with the owner on 2026-11-10 (`DECISIONS.md` D-027 to D-037); where the code still uses
an older word, the entry says so and names the row, and the rename is a ticket. Foundation
terms (harness, agent, tool, plugin, seam) are in the root `CONTEXT.md`.

## asset
One thing the enterprise must protect and account for: an IT system, a cloud resource or an OT
device, with an enterprise asset ID, a type, an owner, a business unit and service, a criticality,
a location and an environment (PRD Module 2). An asset is never deleted because a source stops
reporting it; it is marked potentially inactive (see lifecycle state).
Example: `EA-000001`, host `fin-erp-db01`, a `database` in Finance serving ERP, criticality `critical`.
Not: a finding, a source record, an application.

## asset owner
The accountable party recorded on an asset: a person or a team (D-027). Stored as text in
`asset_owner`; an owner type will be recorded once real data shows the mix. An asset with no
owner is a gap, never an asset that belongs to nobody by design.
Example: `j.alvarez` owns `EA-000001`; `EA-000003` has no owner and is flagged `no_owner`.
Not: the control owner, the accountable owner of a risk, a business owner (persona).

## asset type
What kind of thing an asset is, one of a closed list spanning IT, cloud and OT (`asset_type`
enum: endpoint, server, database, gcp_project, plc, and so on). OT and cloud types exist from day
one even with zero rows (PRD §3).
Example: `EA-000005` is a `plc`; `EA-000006` is a `gcp_project`.
Not: asset category (the PRD's three groups IT, Cloud, OT), which the code does not store.

## brief
The Asset Summary Agent's advisory answer about one asset, in the PRD Module 7 format: executive
summary, supporting facts, business impact, recommended action, source references, last-updated
time, data completeness. Facts, sources, time and completeness are filled by code; the model
writes only the summary, impact and action. Endpoint: `POST /api/v1/assets/{enterprise asset ID}/brief`.
Example: a brief on `EA-000003` says the asset has no owner and recommends naming one.
Not: a risk record, a chat answer about many assets.

## business service
The service a business unit delivers that an asset supports (PRD Module 2 required field
`business_service`). Risk is expressed per business service.
Example: `ERP` for the two Finance assets; `Line 1 Assembly` for the Plant 1 PLC.
Not: an application (PRD lists applications separately), a business unit.

## business unit
The part of the organisation that owns a business service and its assets (PRD Module 2 required
field `business_unit`). KPIs are broken down by it.
Example: `Finance`, `Human Resources`, `Manufacturing`.
Not: a location, a persona.

## control
One requirement from a control library, starting with NIST SP 800-53 Rev. 5, mapped to ISO 27001
and TISAX (PRD Module 5). Controls are associated with assets and assessed with evidence. Not yet
in the code.
Example: `AC-2 Account Management`.
Not: a finding, a compensating control on a vulnerability.

## control effectiveness
Whether an implemented control actually works, kept as a separate status from control status
(PRD Module 5: "an implemented control is not necessarily an effective control"). Not yet in the
code; its values are not defined by the PRD and are D-029.
Example: AC-2 is implemented but assessed not effective because access reviews are overdue.
Not: control status.

## control status
How far a control is implemented, one of the PRD's six states: Implemented, Partially
Implemented, Not Implemented, Not Applicable, Not Assessed, Evidence Pending. An agent may
recommend a status; only the assessment and approval workflow sets it. Not yet in the code.
Example: SI-2 is `Evidence Pending` until the patch report is attached.
Not: control effectiveness, compliance percentage.

## criticality
How much the business depends on an asset: `critical`, `high`, `medium`, `low` or `unknown`
(`asset_criticality` enum). A blank value is stored as `unknown`, never as `low`. The PRD's
"asset criticality" and "business criticality" are this same field (D-030). Who may set it is
still D-009.
Example: `EA-000006` has criticality `unknown` and is flagged `no_criticality`.
Not: vulnerability severity, risk rating.

## data completeness
Whether an asset record has every required field, reported with a brief as `complete` plus the
list of `missing_fields`. Required: owner, business unit, business service, location and a known
criticality (D-031). Findings, control status and risk rating join the list when those tables
exist.
Example: `EA-000003` is incomplete; missing fields: `asset_owner`.
Not: data freshness (when a source last reported), a data-quality flag.

## data-quality flag
A gap on an asset computed by the rules in code and shared by the API summary, the MCP gap tool
and the agent: `without_owner`, `without_criticality`, `potentially_inactive`. The summary
endpoint counts the same gaps under the same names. The flags still read `no_owner` and
`no_criticality` in code until the rename ticket lands (D-032).
Example: `EA-000003` carries `without_owner`; the summary counts it under `without_owner`.
Not: a finding, data completeness, the PRD's per-finding "data quality status".

## enterprise asset ID
The one identifier every asset must have, unique across all sources, by which the API, the agent
and the MCP tools address an asset (`enterprise_asset_id`, PRD Module 2). Correlation of other
identifiers across sources is D-010.
Example: `EA-000003`.
Not: the database row id, a hostname, a source record id, the PRD's illustrative `AST-10025`.

## finding
A record from a source system that says something is wrong with an asset, kept with its source,
source record id, collection and update times, data-quality status, correlation status and
provenance (PRD §7). Source facts are never overwritten by model output. Not yet in the code.
The PRD uses the word for vulnerability findings, control-assessment findings and the findings
behind a risk; whether one term covers all three waits for the risk model (D-033).
Example: Tenable record `TEN-10001`, a critical CVE on `PROD-SRV-001`.
Not: a data-quality flag, a risk.

## lifecycle state
Whether an asset is still in service: `active`, `potentially_inactive`, `retired` or `unknown`
(`asset_lifecycle` enum). The code never moves an asset to `retired` on its own (D-012). The
PRD's "unknown asset" (Module 2 requirement 5) is something else, called an unregistered asset
here (D-034).
Example: `EA-000004` is `active`; an asset missing from the latest CSV becomes `potentially_inactive`.
Not: environment, criticality.

## persona
A group of users with one set of needs, as the PRD §2 lists them: CIO, CISO, CTO, Security
Operations, Infrastructure Leadership, Application Owners, Business Owners, Internal Audit,
Platform Administrator. The code implements each as a role key in `ROLE_PERMISSIONS`
(`ciso`, `security_ops`, `platform_admin`, ...) with a permission set: persona is the group, role
is its key in code (D-035).
Example: `internal_audit` may read controls, assets and the audit log, and cannot run agents.
Not: a login, a permission.

## potentially inactive
The lifecycle state of an asset that at least one source has stopped reporting and nobody has yet
verified as retired (PRD Module 2). Set by ingestion with a history row; cleared when the asset
reappears; never turned into `retired` automatically. Also surfaced as a data-quality flag and a
summary count of the same name.
Example: an asset in last week's CSV but not this week's.
Not: retired, unknown, offline.

## risk
One consolidated record that connects findings, control gaps, criticality and business dependency
for an asset or service into an executive statement: title, business unit, affected service and
assets, rating, business impact, accountable owner, recommended action, evidence, last updated
(PRD Module 6). The model behind the rating is explainable and version-controlled, and is not
yet defined (D-007). Not yet in the code. The PRD also says "risk rating", "Enterprise Risk Score"
and "risk priority"; which is which waits for the risk model (D-036).
Example: "Critical production server exposure", severity Critical, affecting `PROD-SRV-001`.
Not: a vulnerability, a finding, a data-quality flag.

## source system
An outside system that reports assets or findings and whose name is kept on every record it
contributed (`asset_sources.source_system`; PRD §7 "original source system"). Each is reached
through a plugin. The PRD's "source platform", "integrated platform" and "data source" all mean
this. The API field `sources` becomes `source_systems` in the rename ticket (D-037).
Example: `asset_db_csv` today; Tenable, Defender, SCCM, Intune, Chronicle and Entra ID later.
Not: a model provider, the database.

## unregistered asset
An asset that a source system reports but the inventory does not hold (PRD Module 2 requirement
5, "identify unknown assets"). Not the lifecycle state `unknown`. Not yet detected by the code.
Example: a server Tenable scans that has no enterprise asset ID.
Not: an asset with lifecycle state `unknown`, a potentially inactive asset.
