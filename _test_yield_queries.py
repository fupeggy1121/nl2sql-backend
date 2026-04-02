"""
Test yield queries via the /api/v1/chat API.
Run with: python _test_yield_queries.py
"""
import json
import os
import time

# Remove proxy env vars to avoid redirect issues
for k in ("http_proxy","https_proxy","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","all_proxy"):
    os.environ.pop(k, None)

import httpx

BASE_URL = "http://localhost:8000"

QUERIES = [
    ("Q1 各工站一次良率",    "统计各工站在最近一周的一次良率"),
    ("Q2 各工站综合良率",    "统计各工站在最近一周的综合良率"),
    ("Q3 产线FPY按天趋势",  "统计整体产线最近一周按天的一次良率趋势"),
    ("Q4 某工站FPY趋势",    "统计POL抛光工站最近一周按天的一次良率趋势"),
    ("Q5 某工站综合良率趋势","统计POL抛光工站最近一周按天的综合良率趋势"),
]

SEP = "=" * 70

def run_query(label: str, message: str) -> None:
    print(f"\n{SEP}")
    print(f"[{label}]")
    print(f"Query: {message}")
    print(SEP)

    t0 = time.time()
    try:
        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat",
            json={"message": message},
            timeout=120,
        )
        elapsed = round(time.time() - t0, 2)
        print(f"HTTP {resp.status_code}  ({elapsed}s)")

        if resp.status_code != 200:
            print(f"ERROR body: {resp.text[:500]}")
            return

        data = resp.json()
        success = data.get("success")
        inner  = data.get("data", {})

        print(f"success: {success}")

        # --- SQL generated ---
        sql = inner.get("sql") or inner.get("generated_sql") or inner.get("query")
        if sql:
            print(f"\n--- Generated SQL ---\n{sql}\n")

        # --- Error ---
        err = inner.get("error") or data.get("error")
        if err:
            print(f"ERROR: {err}")

        # --- Result rows ---
        rows = inner.get("rows") or inner.get("data") or inner.get("results") or []
        if isinstance(rows, list):
            print(f"Result rows: {len(rows)}")
            for r in rows[:5]:
                print(f"  {r}")
            if len(rows) > 5:
                print(f"  ... ({len(rows) - 5} more rows)")
        elif isinstance(rows, dict):
            print(f"Result (dict keys): {list(rows.keys())[:10]}")

        # --- Analytics result ---
        analysis = inner.get("analysis") or inner.get("analytics")
        if analysis:
            summary = analysis.get("summary") or ""
            a_data  = analysis.get("data") or {}
            charts  = analysis.get("charts") or []
            print(f"\nAnalysis summary: {summary}")
            if a_data:
                print(f"Analysis data keys: {list(a_data.keys())}")
                for k, v in a_data.items():
                    if not isinstance(v, list):
                        print(f"  {k}: {v}")
            print(f"Charts: {len(charts)}")
            for ch in charts:
                print(f"  chart type={ch.get('type')} title={ch.get('title')}")

        # --- LLM answer/response ---
        answer = inner.get("answer") or inner.get("response") or inner.get("message")
        if answer and isinstance(answer, str):
            print(f"\nLLM Answer: {answer[:300]}")

        # Pipeline trace summary
        trace = inner.get("pipeline_trace") or data.get("pipeline_trace") or []
        if trace:
            print(f"\nPipeline steps: {[t.get('node', t.get('step')) for t in trace]}")

    except httpx.ConnectError:
        print("ERROR: Cannot connect to backend. Make sure it's running on port 8000.")
    except Exception as e:
        print(f"EXCEPTION: {e}")


if __name__ == "__main__":
    print(f"Testing yield queries against {BASE_URL}")

    # Health check
    try:
        h = httpx.get(f"{BASE_URL}/health", timeout=5)
        print(f"Health: {h.status_code} {h.text[:100]}")
    except Exception:
        try:
            h = httpx.get(f"{BASE_URL}/", timeout=5)
            print(f"Root: {h.status_code}")
        except Exception as e:
            print(f"Backend not reachable: {e}")

    for label, query in QUERIES:
        run_query(label, query)

    print(f"\n{SEP}\nDone.\n")
