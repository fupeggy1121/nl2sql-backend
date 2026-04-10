import app.agent.nodes.query_planner as qp

q = (
    "统计本月不同产品的批次完工记录，需要关联 "
    "matrix_routerx_operation_lot_batch_resume_log_detail 和 "
    "matrix_routerx_operation_lot_batch_resume_wafer_detail_log 两张大表"
)
plan = qp._detect_forced_execution_plan(q)
print("_forced:", plan.get("_forced"))
print("_decomposed:", plan.get("_decomposed"))
print("mode:", plan.get("mode"))
print("sqls count:", len(plan.get("sqls", [])))
for s in plan.get("sqls", []):
    print(f"  s{s['id']}: table={s.get('table')}, purpose={s.get('purpose','')[:50]}")

state = {
    "execution_plan": plan,
    "sql_error": "",
    "user_input": q,
    "query_plan": {},
}
forced_plan_hint = state.get("execution_plan") if not state.get("sql_error") else None
print()
print("_forced_plan_hint is not None:", forced_plan_hint is not None)
print("_decomposed flag:", forced_plan_hint.get("_decomposed") if forced_plan_hint else "N/A")
print("would_enter_path_B:", bool(forced_plan_hint and forced_plan_hint.get("_decomposed") and not state.get("sql_error")))
