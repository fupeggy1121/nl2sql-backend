import json
from datetime import datetime

entry = {
    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    "author": "copilot-scan",
    "summary": "重扫 warehouse_output_record_bill_detail，扩充 semi:OutboundEventRecord 数据属性（3→19字段）；新增4条对象关系",
    "changes": [
        {
            "type": "property_enrichment",
            "target": "semi:OutboundEventRecord",
            "table": "warehouse_output_record_bill_detail",
            "before": 3,
            "after": 19,
            "added_properties": [
                "semi:hasRequireQty -> require_count",
                "semi:hasStockQty -> quantity",
                "semi:hasMaterialCode -> material_model_code",
                "semi:hasMaterialName -> material_model_name",
                "semi:hasMaterialVersion -> material_model_version",
                "semi:hasMaterialType -> material_type_name",
                "semi:hasMaterialCategory -> material_category_name",
                "semi:hasBatchNo -> batch_no",
                "semi:hasBoxNo -> unique_code",
                "semi:hasStockUnit -> unit_name",
                "semi:hasWarehouseName -> warehouse_name",
                "semi:hasDestination -> destination",
                "semi:hasStatus -> status",
                "semi:hasOutboundType -> type",
                "semi:hasSupplier -> supplier",
                "semi:hasOperator -> user_create"
            ]
        },
        {
            "type": "relation_added",
            "logic_relation": "semi:outboundFromLocation",
            "domain": "semi:OutboundEventRecord",
            "range": "semi:WarehouseLocation",
            "join": "warehouse_output_record_bill_detail.warehouse_id -> warehouse_model.id"
        },
        {
            "type": "relation_added",
            "logic_relation": "semi:recordsBatch",
            "domain": "semi:OutboundEventRecord",
            "range": "semi:MaterialBatch",
            "join": "warehouse_output_record_bill_detail.(batch_no/unique_code+warehouse_id) -> warehouse_inventory"
        },
        {
            "type": "relation_added",
            "logic_relation": "semi:storedAtLocation",
            "domain": "semi:MaterialBatch",
            "range": "semi:WarehouseLocation",
            "join": "warehouse_inventory.warehouse_id -> warehouse_model.id"
        },
        {
            "type": "relation_added",
            "logic_relation": "semi:updatesInventory",
            "domain": "semi:InboundEventRecord",
            "range": "semi:Inventory",
            "join": "warehouse_input_record_bill_detail.(batch_no/unique_code+warehouse_id) -> warehouse_inventory"
        }
    ]
}
with open("app/ontology/data/mapping_changelog.jsonl", "a") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
print("Changelog written OK")
