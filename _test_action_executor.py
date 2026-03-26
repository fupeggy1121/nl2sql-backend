"""Smoke test for action_executor with mocked MySQL and MES API."""
import sys
import types
import unittest.mock as mock

# ── Mock MES API adapter so no real HTTP call ──
fake_adapter = mock.MagicMock()
fake_adapter.call.return_value = {"$newId": "LOT-001-SPLIT-TEST", "_raw": {}}

mes_mod = types.SimpleNamespace(
    MESAPIAdapter=mock.MagicMock(return_value=fake_adapter),
    MESAPIError=Exception,
    get_mes_api_adapter=mock.MagicMock(return_value=fake_adapter),
)
sys.modules["app.services.mes_api_adapter"] = mes_mod

# ── Mock MySQL executor (no real DB) ──
fake_db = mock.MagicMock()
fake_db.connect.return_value = True
fake_db.execute_query.side_effect = lambda sql, params=None: (
    [{"id": 99, "current_lot_code": "LOT-001", "status": "10", "wafer_count": 25}]
    if "matrix_routerx_lot" in sql and "SELECT" in sql.upper()
    else None
)
mysql_mod = types.SimpleNamespace(
    MySQLExecutor=mock.MagicMock(return_value=fake_db),
    PYMYSQL_AVAILABLE=True,
)
sys.modules["app.services.mysql_executor"] = mysql_mod

# ── Import the real action_executor ──
from app.agent.nodes.action_executor import action_executor_node  # noqa: E402

# ── Smoke test ──
state = {
    "session_id": "test-session-001",
    "intent": "action",
    "action_intent": {
        "entities": {
            "eventType": "SPLIT",
            "lotId": "LOT-001",
            "waferList": ["W001", "W002", "W003"],
        }
    },
    "pipeline_trace": [],
}

result = action_executor_node(state)

ar = result.get("action_result", {})
ae = result.get("action_error", "")
resp = result.get("response", {})

print("=== action_executor smoke test ===")
print(f"action_error   : {repr(ae)}")
print(f"success        : {ar.get('success')}")
print(f"sourceLotId    : {ar.get('sourceLotId')}")
print(f"newLotId       : {ar.get('newLotId')}")
print(f"affectedWafers : {ar.get('affectedWafers')}")
print(f"waferCount     : {ar.get('waferCount')}")
print(f"prevQty        : {ar.get('prevQty')}")
print(f"remainingQty   : {ar.get('remainingQty')}")
print(f"response.msg   : {str(resp.get('message', ''))[:120]}")
print()

# ── Also test response_builder with action intent ──
from app.agent.nodes.response_builder import response_builder_node  # noqa: E402

rb_state = {
    "intent": "action",
    "start_time": __import__("time").time() - 0.5,
    "action_result": ar,
    "action_error": ae,
    "response": resp,
    "pipeline_trace": [],
}
rb_result = response_builder_node(rb_state)
final = rb_result.get("response", {})
print("=== response_builder smoke test ===")
print(f"type          : {final.get('type')}")
print(f"success       : {final.get('success')}")
print(f"action        : {final.get('action')}")
print(f"message[:80]  : {str(final.get('message',''))[:80]}")
print(f"query_time_ms : {final.get('query_time_ms')}")

# Assertions
assert ae == "", f"FAIL: action_error should be empty, got {repr(ae)}"
assert ar.get("success") is True, "FAIL: success != True"
assert ar.get("newLotId") == "LOT-001-SPLIT-TEST", f"FAIL: wrong newLotId {ar.get('newLotId')}"
assert ar.get("waferCount") == 3, "FAIL: waferCount != 3"
assert final.get("type") == "action", "FAIL: response type != action"
assert final.get("success") is True, "FAIL: response success != True"
print()
print("ALL ASSERTIONS PASSED ✅")
