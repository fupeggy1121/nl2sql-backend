"""
ExecutionPlan mode 准确率探针测试（使用与 _validate_full_pipeline.py 相同的 call_api）

检验 LLM 遵循 ExecutionPlan 规则的准确率：
  简单查询  → 期望 sql_only
  大表 JOIN → 期望 multi_sql_merge
  pivot 需求 → 期望 sql_then_python
"""
import os, sys, re, time

os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)

CHAT_ENDPOINT = "http://localhost:8000/api/v1/chat"
TIMEOUT = 90

def call_api(query: str) -> dict:
    try:
        import httpx
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "-q"])
        import httpx
    for k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"]:
        os.environ.pop(k, None)
    t0 = time.time()
    try:
        r = httpx.post(CHAT_ENDPOINT, json={"message": query}, timeout=TIMEOUT)
        body = r.json()
        body["_latency_ms"] = (time.time() - t0) * 1000
        return body
    except Exception as e:
        return {"error": str(e), "_latency_ms": (time.time() - t0) * 1000}


# ── 探针用例 ─────────────────────────────────────────────────────────────────
PROBES = [
    # 简单查询 → 期望 sql_only（不输出 EXEC_PLAN，走 sql_only 兜底）
    ("P01", "当前有多少批次在加工",                                 "sql_only",       "简单 COUNT"),
    ("P02", "最近创建的10个批次的批次号",                           "sql_only",       "简单 LIST + LIMIT"),
    ("P03", "上个月新建了多少个生产批次",                           "sql_only",       "时间过滤 COUNT"),
    ("P04", "查询最近3天各设备的加工批次数",                        "sql_only",       "小表 JOIN"),
    ("P05", "各工站当前有多少批次在加工",                           "sql_only",       "GROUP BY 聚合"),
    # 大表 JOIN → 期望 multi_sql_merge（两张 resume 大表）
    ("P06",
     ("从 matrix_routerx_operation_lot_batch_resume_log_detail 和 "
      "matrix_routerx_operation_lot_batch_resume_wafer_detail_log "
      "查最近一周的批次完工情况，关联 lot_id"),
     "multi_sql_merge", "明确命名两张大表"),
    ("P07",
     ("统计本月不同产品的批次完工记录，需要关联 "
      "matrix_routerx_operation_lot_batch_resume_log_detail 和 "
      "matrix_routerx_operation_lot_batch_resume_wafer_detail_log 两张大表"),
     "multi_sql_merge", "多产品大表统计"),
    # pivot 需求 → 期望 sql_then_python
    ("P08",
     "把最近7天每个工站的WIP数量按日期做成透视表（行=工站，列=日期）",
     "sql_then_python", "透视表转置"),
    ("P09",
     "将各产品每天的新增批次数转置为透视表，列为日期，行为产品名称",
     "sql_then_python", "产品×日期透视"),
    # 单张大表（只有一张，不应触发 multi_sql_merge）
    ("P10",
     "查 matrix_routerx_operation_lot_batch_resume_log_detail 里最近5条记录的批次号",
     "sql_only",         "单张大表扫描"),
]


def extract_mode(response: dict) -> tuple:
    """从 API 响应中提取执行模式和行数。"""
    data = response.get("data", {})
    trace = data.get("pipeline_trace", [])
    step_map = {s["step"]: s.get("detail", {}) for s in trace if "step" in s}
    exec_d = step_map.get("data_executor", {})
    gen_d = step_map.get("sql_generator", {})
    mode = exec_d.get("mode", "N/A")
    rows = exec_d.get("rows_count", 0)
    # 缓存命中时 mode 可能为 sql_only（已在 execution_engine_node 修复）
    sql = gen_d.get("sql", "")[:60]
    engine_steps = len(exec_d.get("engine_trace", []))
    return mode, rows, engine_steps, sql


if __name__ == "__main__":
    correct = 0
    wrong = 0
    results = []

    for pid, query, expected, note in PROBES:
        print(f"[{pid}] {query[:55]:55s} ← {note}", flush=True)
        resp = call_api(query)
        if "error" in resp:
            mode, rows, steps, sql = "API_ERROR", 0, 0, resp["error"][:40]
        else:
            mode, rows, steps, sql = extract_mode(resp)

        lat = resp.get("_latency_ms", 0)
        ok = (mode == expected)
        correct += int(ok)
        wrong += int(not ok)
        label = "✅" if ok else "❌"
        print(f"  {label} expected={expected:<18s}  actual={mode:<18s}  rows={rows:4d}  steps={steps}  {lat:.0f}ms")
        if sql:
            print(f"     sql: {sql}")
        results.append((pid, expected, mode, ok, note))
        print()

    print("=" * 65)
    print(f"Mode 判断准确率: {correct}/{len(PROBES)} = {100*correct/len(PROBES):.0f}%")

    n_simple = sum(1 for _, exp, _, _, _ in results if exp == "sql_only")
    err_simple = sum(1 for _, exp, act, _, _ in results if exp == "sql_only" and act != "sql_only")
    n_complex = sum(1 for _, exp, _, _, _ in results if exp != "sql_only")
    ok_complex = sum(1 for _, exp, act, _, _ in results if exp != "sql_only" and act == exp)

    print(f"  简单查询误触发率: {err_simple}/{n_simple} = {100*err_simple/n_simple:.0f}%")
    if n_complex:
        print(f"  复杂查询命中率:   {ok_complex}/{n_complex} = {100*ok_complex/n_complex:.0f}%")

    if wrong > 0:
        print()
        print("❌ 错误用例:")
        for pid, exp, act, ok_, note_ in results:
            if not ok_:
                print(f"  [{pid}] {note_}: expected={exp}  actual={act}")

    print()
    sys.exit(0 if wrong == 0 else 1)
