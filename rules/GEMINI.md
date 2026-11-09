# Google Cloud Enterprise Workspace & Architecture Governance Rules (v3.9 Clean-Room Edition)

## 1. Cloud Architecture, FinOps & Data Telemetry Governance
- **Six-Pillar Cloud Architecture Scope**: Address all relevant enterprise cloud pillars when designing solutions (AI/ML, Data & Analytics, Application Modernization, Security & Zero Trust, Multicloud/Hybrid, and Data Sovereignty) using weighted Six Thinking Hats trade-off matrices before major architectural changes.
- **Live Read-Only Cloud & Billing Telemetry**: Ground cost, quota, and utilization claims in live read-only queries (`cloud_telemetry` FastMCP tools, `bq query --nouse_legacy_sql` against BigQuery billing export tables, and `gcloud` read-only `--format=json` commands with explicit `--project` and `--quiet` flags). Never fabricate or guess spend figures.
- **High-Resolution Architecture Diagrams (`diagram_renderer`)**: Render architecture topologies through `diagram_renderer` (`render_gcp_draw.py` BENTO v15.5 zones or Mermaid compilation) with 100% component parity and verified viewport geometry (`issueCount == 0`).

## 2. Clean-Room Security, Anonymization & Script Maintainability
- **Zero Secret, Credential, or Workstation Path Leakage**: Never commit credentials, OAuth tokens, private keys, or host-specific home paths into repository files or exported documents; scrub tenant-specific identifiers in shared templates.
- **Parameterized Helper Scripts & Clean Repositories**: Parameterize reusable helper scripts via `argparse` or environment variables (`Role`, `Purpose`, and `How It Is Used` module docstrings), run `PYTHONDONTWRITEBYTECODE=1 python3 -B` tests after every mutation, and defer background graph consolidation and temporal confidence maintenance to scheduled off-peak `dreaming_engine.py` runs.
