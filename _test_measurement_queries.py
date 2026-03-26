"""
Test typical NL2SQL queries for the two-layer measurement model.
Sends queries to the backend API and extracts generated SQL + matched classes.
"""
import requests
import json
import sys

BASE = "http://localhost:8000/api/v1/chat"

QUERIES = [
    ("Q1: 简单查询量测数据", "查询量测数据"),
    ("Q2: 按批次查量测参数", "查询批次 M250701001 的量测参数值"),
    ("Q3: 按晶圆查量测结果", "查询晶圆 W001 的量测结果"),
    ("Q4: 按设备查量测数据", "查询设备 EQP-01 的量测数据"),
    ("Q5: 按站点查量测参数", "查询 PHOTO 站点的量测参数"),
    ("Q6: 量测录入人(事件层)", "谁录入了量测数据"),
]

def run_query(idx, label, message):
    session_id = "test-meas-%03d" % idx
    print("")
    print("=" * 60)
    print("  %s" % label)
    print("  NL: %s" % message)
    print("=" * 60)
    try:
        resp = requests.post(BASE, json={"message": message, "session_id": session_id}, timeout=120)
        data = resp.json()
        if not data.get("success"):
            print("  API ERROR: %s" % str(data))
            return

        d = data.get("data", {})
        resp_type = d.get("type", "unknown")
        print("  Response type: %s" % resp_type)

        trace = d.get("pipeline_trace", [])
        for step in trace:
            name = step.get("step", "")
            detail = step.get("detail", {})
            summary = step.get("summary", "")

            if name == "intent_router":
                print("  Intent: %s" % detail.get("raw_intent"))
                print("  Route: %s" % detail.get("route"))
                print("  Classes: %s" % detail.get("target_class_hints"))
                print("  Query type: %s" % detail.get("query_type"))
                entities = detail.get("entities", {})
                print("  Entities: %s" % json.dumps(entities, ensure_ascii=False))
                sf = detail.get("semantic_filters", [])
                if sf:
                    print("  Semantic filters: %s" % json.dumps(sf, ensure_ascii=False))

            elif name == "query_planner":
                if summary:
                    print("  Plan summary: %s" % summary[:400])

            elif name == "sql_generator":
                sql = detail.get("sql", detail.get("generated_sql", ""))
                if sql:
                    print("  Generated SQL: %s" % sql)
                elif summary:
                    print("  SQL summary: %s" % summary[:400])

            elif name == "data_executor":
                row_count = detail.get("row_count", detail.get("rows_returned", "?"))
                print("  Rows returned: %s" % row_count)

            elif name == "clarification_node":
                q = detail.get("clarification_question", "")
                print("  Clarification: %s" % q)

        sql = d.get("sql", "")
        if sql:
            print("  Final SQL: %s" % sql)
        cq = d.get("clarification_question", "")
        if cq:
            print("  Clarification Q: %s" % cq[:200])

    except Exception as e:
        print("  EXCEPTION: %s" % str(e))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        idx = int(sys.argv[1])
        label, msg = QUERIES[idx]
        run_query(idx, label, msg)
    else:
        for i, (label, msg) in enumerate(QUERIES):
            run_query(i, label, msg)
