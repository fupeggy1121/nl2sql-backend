"""Reproduce the carrier follow-up query issue."""
import requests
import json

BASE = "http://localhost:8000/api/v1/chat"
SESSION = "test-carrier-followup-v2"

def send(message):
    print("\n" + "=" * 70)
    print("  NL: %s" % message)
    print("=" * 70)
    r = requests.post(BASE, json={"message": message, "session_id": SESSION}, timeout=180)
    d = r.json()
    data = d.get("data", {})
    trace = data.get("pipeline_trace", [])
    for step in trace:
        name = step.get("step", "")
        detail = step.get("detail", {})
        summary = step.get("summary", "")
        if name == "memory_loader":
            print("  [memory] is_followup=%s" % detail.get("is_followup"))
            resolved = detail.get("resolved_input", "")
            if resolved:
                print("  [memory] resolved_input=%s" % resolved[:300])
        elif name == "intent_router":
            print("  [intent] raw=%s, route=%s" % (detail.get("raw_intent"), detail.get("route")))
            print("  [intent] classes=%s" % detail.get("target_class_hints"))
            print("  [intent] query_type=%s" % detail.get("query_type"))
            ent = detail.get("entities", {})
            print("  [intent] entities=%s" % json.dumps(ent, ensure_ascii=False))
            sf = detail.get("semantic_filters", [])
            if sf:
                print("  [intent] filters=%s" % json.dumps(sf, ensure_ascii=False))
            slots = detail.get("intent_slots", {})
            if slots:
                limit_n = slots.get("limit_n")
                print("  [intent] slots.limit_n=%s" % limit_n)
        elif name == "query_planner":
            if summary:
                print("  [planner] %s" % summary[:300])
            plan_limit = detail.get("limit")
            if plan_limit:
                print("  [planner] limit=%s" % plan_limit)
        elif name == "sql_generator":
            sql = detail.get("sql", detail.get("generated_sql", ""))
            if sql:
                print("  [sql] %s" % sql)
            elif summary:
                print("  [sql] %s" % summary[:300])
        elif name == "data_executor":
            rc = detail.get("row_count", detail.get("rows_returned", "?"))
            err = detail.get("error", "")
            print("  [exec] rows=%s %s" % (rc, ("err=%s" % err[:100]) if err else ""))
        elif name == "clarification_node":
            print("  [clarify] %s" % detail.get("clarification_question", "")[:200])
    # Top level
    sql = data.get("sql", "")
    if sql:
        print("  FINAL SQL: %s" % sql)
    cq = data.get("clarification_question", "")
    if cq:
        print("  CLARIFY: %s" % cq[:200])

# Step 1: initial query
send("站点\"光泽度测量\"的可用载具列表")

# Step 2: follow-up
send("不做数量限制，并展示maintenance_countdown字段列")
