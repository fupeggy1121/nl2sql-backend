#!/usr/bin/env python3
"""注入 value_mappings 和 business_rules 骨架到 mapping_prod.json"""
import json
from pathlib import Path

MAPPING_FILE = Path("app/ontology/data/mapping_prod.json")
T = "\u26a0\ufe0f TODO: \u8bf7\u5bf9\u7167\u771f\u5b9e\u6570\u636e\u5e93\u679a\u4e3e\u5024\u786e\u8ba4\u540e\u4fee\u6539 physical_condition"

VALUE_MAPPINGS = {
  "semi:BatchStatus": {
    "Pending": {"description": "\u5f85\u6267\u884c\u6279\u6b21", "physical_condition": "local_production_batch.status = 0", "applies_to_table": "local_production_batch", "applies_to_column": "status", "note": "status=0 \u5f85\u6267\u884c"},
    "Running": {"description": "\u6267\u884c\u4e2d\u6279\u6b21\uff08\u5728\u5236\u54c1/WIP\uff09", "physical_condition": "local_production_batch.status = 1", "applies_to_table": "local_production_batch", "applies_to_column": "status", "count_target_table": "local_production_batch", "count_target_column": "id", "note": "status=1 \u6267\u884c\u4e2d \u2014 WIP \u67e5\u8be2\u65f6 COUNT \u6b64\u8868"},
    "Completed": {"description": "\u5df2\u5b8c\u6210\u6279\u6b21", "physical_condition": "local_production_batch.status = 3", "applies_to_table": "local_production_batch", "applies_to_column": "status", "note": "status=3 \u5df2\u5b8c\u6210\uff082\u672a\u4f7f\u7528\uff09"},
    "Cancelled": {"description": "\u5df2\u53d6\u6d88\u6279\u6b21", "physical_condition": "local_production_batch.status = 4", "applies_to_table": "local_production_batch", "applies_to_column": "status", "note": "status=4 \u53d6\u6d88"}
  },
  "semi:LotStatus": {
    "Active":    {"description": "\u6279\u6b21\u5728\u5236/\u8fdb\u884c\u4e2d", "physical_condition": T + " \u2014 lot_list.lot_status = ?", "applies_to_table": "lot_list", "applies_to_column": "lot_status", "note": T},
    "Completed": {"description": "\u6279\u6b21\u5df2\u5b8c\u6210",               "physical_condition": T + " \u2014 lot_list.lot_status = ?", "applies_to_table": "lot_list", "applies_to_column": "lot_status", "note": T},
    "OnHold":    {"description": "\u6279\u6b21 Hold \u4e2d",                      "physical_condition": T + " \u2014 lot_list.lot_status = ?", "applies_to_table": "lot_list", "applies_to_column": "lot_status", "note": T}
  },
  "semi:HoldStatus": {
    "Held":     {"description": "\u6279\u6b21\u5904\u4e8e Hold \u672a\u91ca\u653e", "physical_condition": "matrix_routerx_operation_lot_hold_action.status = 0", "applies_to_table": "matrix_routerx_operation_lot_hold_action", "applies_to_column": "status", "note": "status=0 \u672a release"},
    "Released": {"description": "Hold \u5df2\u91ca\u653e",                          "physical_condition": "matrix_routerx_operation_lot_hold_action.status = 1", "applies_to_table": "matrix_routerx_operation_lot_hold_action", "applies_to_column": "status", "note": "status=1 \u5df2 release"}
  },
  "semi:EquipmentStatus": {
    "Active":   {"description": "\u8bbe\u5907\u542f\u7528\u4e2d\uff08OPEN\uff09",    "physical_condition": "equipment.status = 1", "applies_to_table": "equipment", "applies_to_column": "status", "note": "status=1 OPEN"},
    "Inactive": {"description": "\u8bbe\u5907\u505c\u7528/\u5173\u95ed\uff08CLOSE\uff09", "physical_condition": "equipment.status = 0", "applies_to_table": "equipment", "applies_to_column": "status", "note": "status=0 CLOSE"},
    "Running":  {"description": "\u8bbe\u5907\u8fd0\u884c\u4e2d\uff08OEE \u7ef4\u5ea6\uff09", "physical_condition": T + " \u2014 equipment_oee_status.status_code = ?", "applies_to_table": "equipment_oee_status", "applies_to_column": "status_code", "note": T},
    "Down":     {"description": "\u8bbe\u5907\u5b95\u673a/\u6545\u969c\uff08OEE \u7ef4\u5ea6\uff09", "physical_condition": T + " \u2014 equipment_oee_status.status_code = ?", "applies_to_table": "equipment_oee_status", "applies_to_column": "status_code", "note": T}
  },
  "semi:CarrierStatus": {
    "Available": {"description": "\u8f7d\u5177\u53ef\u7528/\u7a7a\u95f2", "physical_condition": T + " \u2014 carrier_info.status = ?", "applies_to_table": "carrier_info", "applies_to_column": "status", "note": T},
    "InUse":     {"description": "\u8f7d\u5177\u4f7f\u7528\u4e2d",         "physical_condition": T + " \u2014 carrier_info.status = ?", "applies_to_table": "carrier_info", "applies_to_column": "status", "note": T}
  },
  "semi:ProductStatus": {
    "Draft":           {"description": "\u4ea7\u54c1\u8349\u7a3f", "physical_condition": "product_model.product_status = 0", "applies_to_table": "product_model", "applies_to_column": "product_status", "note": "product_status=0"},
    "PendingApproval": {"description": "\u4ea7\u54c1\u5f85\u5ba1\u6838", "physical_condition": "product_model.product_status = 1", "applies_to_table": "product_model", "applies_to_column": "product_status", "note": "product_status=1"},
    "Active":          {"description": "\u4ea7\u54c1\u6fc0\u6d3b/\u5728\u4ea7", "physical_condition": "product_model.product_status = 2", "applies_to_table": "product_model", "applies_to_column": "product_status", "note": "product_status=2"}
  },
  "semi:ApproveStatus": {
    "Pending":  {"description": "\u5ba1\u6279\u5f85\u5904\u7406", "physical_condition": "product_model_approve.approve_status = 0", "applies_to_table": "product_model_approve", "applies_to_column": "approve_status", "note": "0 \u5f85\u5ba1\u6279"},
    "Approved": {"description": "\u5ba1\u6279\u901a\u8fc7",       "physical_condition": "product_model_approve.approve_status = 1", "applies_to_table": "product_model_approve", "applies_to_column": "approve_status", "note": "1 \u901a\u8fc7"},
    "Rejected": {"description": "\u5ba1\u6279\u62d2\u7edd",       "physical_condition": "product_model_approve.approve_status = 2", "applies_to_table": "product_model_approve", "applies_to_column": "approve_status", "note": "2 \u62d2\u7edd"}
  },
  "semi:BOMStatus": {
    "Active":   {"description": "BOM \u751f\u6548", "physical_condition": "product_bom.status = 1", "applies_to_table": "product_bom", "applies_to_column": "status", "note": "1 \u751f\u6548"},
    "Inactive": {"description": "BOM \u5931\u6548", "physical_condition": "product_bom.status = 0", "applies_to_table": "product_bom", "applies_to_column": "status", "note": "0 \u5931\u6548"}
  },
  "semi:AccessoryStatus": {
    "Pending":       {"description": "\u8f85\u6599\u5f85\u4e0a\u673a",       "physical_condition": "accy_accessory.status = 0", "applies_to_table": "accy_accessory", "applies_to_column": "status", "note": "0"},
    "InUse":         {"description": "\u8f85\u6599\u4e0a\u673a\u4e2d",       "physical_condition": "accy_accessory.status = 1", "applies_to_table": "accy_accessory", "applies_to_column": "status", "note": "1"},
    "PendingReturn": {"description": "\u8f85\u6599\u9000\u5e93\u5f85\u786e\u8ba4", "physical_condition": "accy_accessory.status = 2", "applies_to_table": "accy_accessory", "applies_to_column": "status", "note": "2"},
    "Returned":      {"description": "\u8f85\u6599\u5df2\u9000\u5e93",       "physical_condition": "accy_accessory.status = 3", "applies_to_table": "accy_accessory", "applies_to_column": "status", "note": "3"}
  },
  "semi:AccessoryApplyStatus": {
    "Pending":  {"description": "\u8f85\u6599\u7533\u8bf7\u5f85\u51fa\u5e93", "physical_condition": "accy_apply_record.status = 0", "applies_to_table": "accy_apply_record", "applies_to_column": "status", "note": "0"},
    "Issued":   {"description": "\u8f85\u6599\u5df2\u51fa\u5e93",             "physical_condition": "accy_apply_record.status = 1", "applies_to_table": "accy_apply_record", "applies_to_column": "status", "note": "1"},
    "Rejected": {"description": "\u8f85\u6599\u7533\u8bf7\u88ab\u62d2\u7edd", "physical_condition": "accy_apply_record.status = 2", "applies_to_table": "accy_apply_record", "applies_to_column": "status", "note": "2"}
  },
  "semi:WarnStatus": {
    "Normal": {"description": "\u65e0\u9884\u8b66",   "physical_condition": "accy_accessory.warn_status = 0", "applies_to_table": "accy_accessory", "applies_to_column": "warn_status", "note": "0"},
    "Warned": {"description": "\u5df2\u89e6\u53d1\u9884\u8b66", "physical_condition": "accy_accessory.warn_status = 1", "applies_to_table": "accy_accessory", "applies_to_column": "warn_status", "note": "1"}
  },
  "semi:TransferJobStatus": {
    "Submitted": {"description": "\u641e\u8fd0\u4efb\u52a1\u5df2\u63d0\u4ea4", "physical_condition": "mcs_transfer_job.status = 0", "applies_to_table": "mcs_transfer_job", "applies_to_column": "status", "note": "0"},
    "Running":   {"description": "\u641e\u8fd0\u4efb\u52a1\u8fd0\u884c\u4e2d", "physical_condition": "mcs_transfer_job.status = 1", "applies_to_table": "mcs_transfer_job", "applies_to_column": "status", "note": "1"},
    "Completed": {"description": "\u641e\u8fd0\u4efb\u52a1\u5df2\u7ed3\u675f", "physical_condition": "mcs_transfer_job.status = 2", "applies_to_table": "mcs_transfer_job", "applies_to_column": "status", "note": "2"}
  },
  "semi:TransferJobSubStatus": {
    "Pending":    {"description": "\u641e\u8fd0\u5f85\u5904\u7406", "physical_condition": "mcs_transfer_job.sub_status = 1", "applies_to_table": "mcs_transfer_job", "applies_to_column": "sub_status", "note": "1"},
    "InTransfer": {"description": "\u641e\u8fd0\u4e2d",             "physical_condition": "mcs_transfer_job.sub_status = 2", "applies_to_table": "mcs_transfer_job", "applies_to_column": "sub_status", "note": "2"},
    "Completed":  {"description": "\u641e\u8fd0\u5df2\u5b8c\u6210", "physical_condition": "mcs_transfer_job.sub_status = 3", "applies_to_table": "mcs_transfer_job", "applies_to_column": "sub_status", "note": "3"},
    "Cancelled":  {"description": "\u641e\u8fd0\u5df2\u53d6\u6d88", "physical_condition": "mcs_transfer_job.sub_status = 4", "applies_to_table": "mcs_transfer_job", "applies_to_column": "sub_status", "note": "4"},
    "Error":      {"description": "\u641e\u8fd0\u5f02\u5e38",       "physical_condition": "mcs_transfer_job.sub_status = 5", "applies_to_table": "mcs_transfer_job", "applies_to_column": "sub_status", "note": "5"}
  },
  "semi:MarkStatus": {
    "Pending":       {"description": "\u5f85\u6253\u6807",   "physical_condition": "mark_gen_code_record.status = 0", "applies_to_table": "mark_gen_code_record", "applies_to_column": "status", "note": "0"},
    "CodeGenerated": {"description": "\u5df2\u751f\u6210\u6253\u6807\u7801", "physical_condition": "mark_gen_code_record.status = 1", "applies_to_table": "mark_gen_code_record", "applies_to_column": "status", "note": "1"},
    "Completed":     {"description": "\u6253\u6807\u5df2\u5b8c\u6210", "physical_condition": "mark_gen_code_record.status = 2", "applies_to_table": "mark_gen_code_record", "applies_to_column": "status", "note": "2"}
  },
  "semi:WarehouseStatus": {
    "Normal":   {"description": "\u5e93\u4f4d\u6b63\u5e38", "physical_condition": "equipment_warehouse.status = 0", "applies_to_table": "equipment_warehouse", "applies_to_column": "status", "note": "0"},
    "Disabled": {"description": "\u5e93\u4f4d\u7981\u7528", "physical_condition": "equipment_warehouse.status = 1", "applies_to_table": "equipment_warehouse", "applies_to_column": "status", "note": "1"}
  },
  "semi:ReportStatus": {
    "Pending":  {"description": "\u5f85\u62a5\u5de5", "physical_condition": "report_record_info.status = 0", "applies_to_table": "report_record_info", "applies_to_column": "status", "note": "0"},
    "Reported": {"description": "\u5df2\u62a5\u5de5", "physical_condition": "report_record_info.status = 1", "applies_to_table": "report_record_info", "applies_to_column": "status", "note": "1"}
  },
  "semi:ProductionOrderStatus": {
    "Open":   {"description": "\u5de5\u5355\u5f00\u542f\u4e2d", "physical_condition": "production_order.production_status = 0", "applies_to_table": "production_order", "applies_to_column": "production_status", "note": "0 \u5f00\u542f"},
    "Closed": {"description": "\u5de5\u5355\u5df2\u5173\u95ed", "physical_condition": "production_order.production_status = 1", "applies_to_table": "production_order", "applies_to_column": "production_status", "note": "1 \u5173\u95ed"}
  }
}

BUSINESS_RULES = []  # \u751f\u4ea7\u5e93\u67e5\u8be2\u6a21\u677f\u5f85\u5207\u6362\u5230\u751f\u4ea7\u5e93\u540e\u6dfb\u52a0

with open(MAPPING_FILE, encoding="utf-8") as f:
    data = json.load(f)

data["value_mappings"] = VALUE_MAPPINGS
data["business_rules"] = BUSINESS_RULES

tmp = MAPPING_FILE.with_suffix(".json.tmp")
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
tmp.replace(MAPPING_FILE)

# verify
with open(MAPPING_FILE, encoding="utf-8") as f:
    v = json.load(f)

print("DONE")
print("object_mappings:", len(v["object_mappings"]))
print("relation_mappings:", len(v["relation_mappings"]))
print("value_mappings domains:", len(v["value_mappings"]))
print("business_rules:", len(v["business_rules"]))
domains = list(v["value_mappings"].keys())
for d in domains:
    cnt = len(v["value_mappings"][d])
    print(f"  {d}: {cnt} values")
