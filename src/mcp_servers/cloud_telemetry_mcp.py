#!/usr/bin/env python3
"""Role: Clean-Room FastMCP Server for Google Cloud Monitoring & BigQuery Billing Telemetry (`cloud_telemetry`).

Purpose:
  Exposes `discover_billing_export_tables`, `query_bigquery_billing`, and `query_cloud_monitoring`
  over MCP stdio transport using standard Google Cloud REST APIs and Application Default Credentials
  (GCE Metadata Server primary + gcloud ADC fallback), returning parsed row dictionaries and schemas
  for real-time FinOps billing audits and regional SRE checks without proprietary dependencies.

How It Is Used:
  Launched automatically via `mcp_config.json` (`python3 -B cloud_telemetry_mcp.py`).
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True

try:
    from fastmcp import FastMCP
except ImportError:
    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, name: str = "", **kwargs):
            self.name = name

        def tool(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        def run(self, *args, **kwargs):
            pass

EAGER_TOOL_META = {"antigravity/alwaysLoad": True}
mcp = FastMCP("cloud_telemetry")
_TOK_CACHE = {"token": "", "expires_at": 0.0}


def _eager_tool():
    try:
        return mcp.tool(meta=EAGER_TOOL_META)
    except TypeError:
        return mcp.tool()


def _default_project() -> str:
    env_proj = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
    if env_proj:
        return env_proj
    try:
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            pid = resp.read().decode("utf-8").strip()
            if pid:
                return pid
    except Exception:
        pass
    return "my-enterprise-gcp-project"


def _adc_token() -> str:
    now = time.time()
    if _TOK_CACHE["token"] and now < _TOK_CACHE["expires_at"]:
        return str(_TOK_CACHE["token"])
    try:
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tok = str(data.get("access_token") or "").strip()
            ttl = max(60, int(data.get("expires_in", 600) or 600) - 90)
            if tok:
                _TOK_CACHE["token"] = tok
                _TOK_CACHE["expires_at"] = now + ttl
                return tok
    except Exception:
        pass
    for cmd in (
        ["gcloud", "auth", "application-default", "print-access-token"],
        ["gcloud", "auth", "print-access-token"],
    ):
        try:
            tok = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
            if tok and not tok.startswith("ERROR"):
                _TOK_CACHE["token"] = tok
                _TOK_CACHE["expires_at"] = now + 240
                return tok
        except Exception:
            pass
    return ""


def _parse_bq_cell(val, field_spec: dict):
    if val is None:
        return None
    mode = str(field_spec.get("mode") or "NULLABLE").upper()
    ftype = str(field_spec.get("type") or "STRING").upper()
    if mode == "REPEATED" and isinstance(val, list):
        item_spec = dict(field_spec, mode="NULLABLE")
        return [_parse_bq_cell(item.get("v") if isinstance(item, dict) else item, item_spec) for item in val]
    if ftype in ("RECORD", "STRUCT") and isinstance(val, dict) and "f" in val:
        subfields = field_spec.get("fields") or []
        subcells = val.get("f") or []
        return {
            str(sf.get("name") or f"col_{idx}"): _parse_bq_cell(
                subcells[idx].get("v") if idx < len(subcells) and isinstance(subcells[idx], dict) else None,
                sf,
            )
            for idx, sf in enumerate(subfields)
        }
    if ftype in ("INTEGER", "INT64"):
        try:
            return int(val)
        except Exception:
            return val
    if ftype in ("FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"):
        try:
            return float(val)
        except Exception:
            return val
    if ftype in ("BOOLEAN", "BOOL"):
        return str(val).lower() == "true"
    return val


def _parse_bq_rows(data: dict) -> tuple[list[str], list[dict]]:
    fields = ((data.get("schema") or {}).get("fields")) or []
    columns = [str(f.get("name") or f"col_{idx}") for idx, f in enumerate(fields)]
    parsed_rows = []
    for raw_row in data.get("rows") or []:
        cells = raw_row.get("f") or []
        row_obj = {}
        for idx, f_spec in enumerate(fields):
            col_name = columns[idx]
            raw_v = cells[idx].get("v") if idx < len(cells) and isinstance(cells[idx], dict) else None
            row_obj[col_name] = _parse_bq_cell(raw_v, f_spec)
        parsed_rows.append(row_obj)
    return columns, parsed_rows


@_eager_tool()
def discover_billing_export_tables(project_id: str = "") -> str:
    """Discover BigQuery datasets and Cloud Billing export tables in the target GCP project."""
    proj = project_id or _default_project()
    tok = _adc_token()
    if not tok:
        return json.dumps({"project_id": proj, "status": "NO_ADC_TOKEN", "billing_tables": []}, indent=2)
    hdrs = {"Authorization": f"Bearer {tok}"}
    datasets = []
    billing_tables = []
    all_tables = []
    try:
        ds_url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{proj}/datasets?maxResults=100"
        with urllib.request.urlopen(urllib.request.Request(ds_url, headers=hdrs), timeout=15) as resp:
            ds_doc = json.loads(resp.read().decode("utf-8"))
        for ds in ds_doc.get("datasets") or []:
            ds_id = ((ds.get("datasetReference") or {}).get("datasetId")) or ""
            if not ds_id:
                continue
            datasets.append(ds_id)
            tb_url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{proj}/datasets/{ds_id}/tables?maxResults=200"
            try:
                with urllib.request.urlopen(urllib.request.Request(tb_url, headers=hdrs), timeout=15) as tb_resp:
                    tb_doc = json.loads(tb_resp.read().decode("utf-8"))
                for tb in tb_doc.get("tables") or []:
                    tb_id = ((tb.get("tableReference") or {}).get("tableId")) or ""
                    if not tb_id:
                        continue
                    fqn = f"{proj}.{ds_id}.{tb_id}"
                    all_tables.append(fqn)
                    if "billing" in ds_id.lower() or "billing" in tb_id.lower():
                        billing_tables.append(fqn)
            except Exception:
                continue
        return json.dumps(
            {
                "project_id": proj,
                "status": "OK",
                "datasets": datasets,
                "billing_tables": billing_tables,
                "tables": all_tables[:50],
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"project_id": proj, "status": "DISCOVERY_ERROR", "error": str(exc)}, indent=2)


@_eager_tool()
def query_cloud_monitoring(
    project_id: str = "",
    metric_type: str = "compute.googleapis.com/instance/cpu/utilization",
    minutes: int = 15,
) -> str:
    """Query Google Cloud Monitoring timeSeries API for live infrastructure telemetry."""
    proj = project_id or _default_project()
    tok = _adc_token()
    if not tok:
        return json.dumps({"project_id": proj, "status": "NO_ADC_TOKEN", "series": []}, indent=2)
    now_ts = int(time.time())
    start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts - max(1, int(minutes)) * 60))
    end_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts))
    params = urllib.parse.urlencode(
        {
            "filter": f'metric.type = "{metric_type}"',
            "interval.startTime": start_iso,
            "interval.endTime": end_iso,
            "pageSize": 20,
        }
    )
    url = f"https://monitoring.googleapis.com/v3/projects/{proj}/timeSeries?{params}"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        series = data.get("timeSeries") or []
        summaries = []
        for ts in series[:10]:
            pts = ts.get("points") or []
            latest_val = (pts[0].get("value") if pts else {}) or {}
            summaries.append(
                {
                    "resource_labels": (ts.get("resource") or {}).get("labels") or {},
                    "metric_labels": (ts.get("metric") or {}).get("labels") or {},
                    "latest_value": latest_val,
                    "points_count": len(pts),
                }
            )
        return json.dumps(
            {
                "project_id": proj,
                "metric_type": metric_type,
                "status": "OK",
                "series_count": len(series),
                "unit": (series[0] if series else {}).get("unit", ""),
                "series_summaries": summaries,
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"project_id": proj, "status": "QUERY_ERROR", "error": str(exc)}, indent=2)


@_eager_tool()
def query_bigquery_billing(sql_query: str = "SELECT 1 AS health_check", project_id: str = "") -> str:
    """Execute a read-only BigQuery Standard SQL query and return parsed schema columns and row dictionaries."""
    proj = project_id or _default_project()
    tok = _adc_token()
    if not tok:
        return json.dumps({"project_id": proj, "status": "NO_ADC_TOKEN", "rows": []}, indent=2)
    url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{proj}/queries"
    payload = json.dumps(
        {
            "query": sql_query,
            "useLegacySql": False,
            "maxResults": 100,
            "timeoutMs": 30000,
        }
    ).encode("utf-8")
    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        columns, parsed_rows = _parse_bq_rows(data)
        return json.dumps(
            {
                "project_id": proj,
                "status": "OK",
                "jobComplete": data.get("jobComplete", False),
                "totalRows": int(data.get("totalRows", len(parsed_rows)) or 0),
                "totalBytesProcessed": data.get("totalBytesProcessed", "0"),
                "columns": columns,
                "row_count": len(parsed_rows),
                "rows": parsed_rows,
            },
            indent=2,
        )
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        return json.dumps(
            {"project_id": proj, "status": "QUERY_ERROR", "http_status": he.code, "error": err_body[:1200]},
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"project_id": proj, "status": "QUERY_ERROR", "error": str(exc)}, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
