#!/usr/bin/env python3
import httpx, json, time, os

os.environ["NO_PROXY"] = "*"
os.environ["ALL_PROXY"] = ""

query = (
    "统计本月不同产品的批次完工记录，需要关联 "
    "matrix_routerx_operation_lot_batch_resume_log_detail 和 "
    "matrix_routerx_operation_lot_batch_resume_wafer_detail_log 两张大表"
)

transport = httpx.HTTPTransport(proxy=None)
t0 = time.time()
with httpx.Client(transport=transport) as client:
    r = client.post("http://localhost:8000/api/v1/chat", json={"message": query}, timeout=120)
lat = time.time() - t0

data = r.json()
d = data.get("data", {})
trace = d.get("pipeline_trace", [])
step_map = {s["step"]: s.get("detail", {}) for s in trace if "step" in s}
exec_d = step_map.get("data_executor", {})
sg_d = step_map.get("sql_generator", {})
ep = d.get("execution_plan")

print(f"latency: {lat:.1f}s")
print(f"execution_plan._decomposed: {(ep or {}).get('_decomposed')}")
print(f"execution_plan.sqls count: {len((ep or {}).get('sqls', []))}")
if ep:
    for s in ep.get("sqls", []):
        print(f"  [{s.get('id')}] purpose={s.get('purpose','')[:50]}  sql={s.get('sql','')[:80]}")
print(f"data_executor.mode: {exec_d.get('mode')}")
print(f"data_executor.rows: {exec_d.get('rows_count')}")
print("engine_trace:")
for t in exec_d.get("engine_trace", []):
    print(" ", t)
print(f"answer[:300]: {str(d.get('answer', ''))[:300]}")
