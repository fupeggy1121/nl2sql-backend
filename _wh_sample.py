"""
物料库存管理查询验证脚本
本体映射验证：semi:Inventory / semi:MaterialBatch / semi:WarehouseEventRecord 子类体系
"""
import pymysql
from decimal import Decimal

def fmt(val):
    if isinstance(val, bytes):
        return int.from_bytes(val, 'little')
    if isinstance(val, Decimal):
        return float(val)
    return val

def print_table(rows, title, cols=None):
    print(f"\n{'='*60}")
    print(f"  {title}  (共 {len(rows)} 行)")
    print('='*60)
    if not rows:
        print("  (无数据)")
        return
    if cols is None:
        cols = list(rows[0].keys())
    # 列宽自适应（最大 24 字符）
    widths = {c: min(max(len(c), max(len(str(fmt(r.get(c,'')))) for r in rows)), 24) for c in cols}
    header = '  '.join(c.ljust(widths[c]) for c in cols)
    sep    = '  '.join('-'*widths[c] for c in cols)
    print(header)
    print(sep)
    for r in rows:
        print('  '.join(str(fmt(r.get(c,''))).ljust(widths[c])[:widths[c]] for c in cols))

conn = pymysql.connect(
    host='172.16.57.29', port=3306, user='cc_mes_read',
    password='read@Cc2025', database='cc_semi_mvp',
    charset='utf8mb4', connect_timeout=5,
    cursorclass=pymysql.cursors.DictCursor
)
cur = conn.cursor()

# ─────────────────────────────────────────────────────────────
# 场景1：实时库存快照（semi:Inventory.hasQuantity / hasAvailableQty）
#   语义：各库位当前有效在库物料，可用量 = quantity - lock_quantity
# ─────────────────────────────────────────────────────────────
cur.execute("""
    SELECT warehouse_name,
           material_model_code,
           material_model_name,
           material_type_name,
           batch_no,
           quantity,
           lock_quantity,
           (quantity - lock_quantity)  AS available_qty,
           unit_name
    FROM warehouse_inventory
    WHERE `del` = 0
    ORDER BY warehouse_name, material_model_code
    LIMIT 15
""")
print_table(cur.fetchall(), "场景1 · 实时库存快照  (del=0, available=qty-lock)",
    cols=['warehouse_name','material_model_code','material_model_name',
          'batch_no','quantity','lock_quantity','available_qty','unit_name'])

# ─────────────────────────────────────────────────────────────
# 场景2：批次溯源（semi:MaterialBatch  storedAtLocation  semi:WarehouseLocation）
#   语义：选取出现最多的物料，查看其所有在库批次及所在库位
# ─────────────────────────────────────────────────────────────
cur.execute("""
    SELECT material_model_code, COUNT(*) AS batch_cnt
    FROM warehouse_inventory
    WHERE `del` = 0
    GROUP BY material_model_code
    ORDER BY batch_cnt DESC
    LIMIT 1
""")
top = cur.fetchone()
top_code = top['material_model_code'] if top else None
print(f"\n>> 批次数最多的物料代码: {top_code}  (共 {top['batch_cnt'] if top else 0} 批)")

if top_code:
    cur.execute("""
        SELECT material_model_code,
               material_model_name,
               batch_no,
               warehouse_id,
               warehouse_name,
               quantity,
               unit_name,
               receive_time
        FROM warehouse_inventory
        WHERE `del` = 0 AND material_model_code = %s
        ORDER BY receive_time DESC
    """, (top_code,))
    print_table(cur.fetchall(), f"场景2 · 批次溯源  [{top_code}] 在库批次分布",
        cols=['material_model_code','material_model_name','batch_no',
              'warehouse_name','quantity','unit_name','receive_time'])

# ─────────────────────────────────────────────────────────────
# 场景3：出库历史查询（semi:OutboundBill  contains  semi:OutboundEventRecord）
#   语义：出库单表头 JOIN 出库明细，展示最近 15 条出库记录
# ─────────────────────────────────────────────────────────────
cur.execute("""
    SELECT b.record_bill_no,
           b.destination,
           b.status               AS bill_status,
           d.material_model_code,
           d.material_model_name,
           d.batch_no,
           d.output_count,
           d.require_count,
           d.unit_name,
           d.warehouse_name,
           d.gmt_create
    FROM warehouse_output_record_bill       b
    JOIN warehouse_output_record_bill_detail d ON d.record_bill_id = b.id
    ORDER BY d.gmt_create DESC
    LIMIT 15
""")
print_table(cur.fetchall(), "场景3 · 出库历史查询  (OutboundBill ⊃ OutboundEventRecord)",
    cols=['record_bill_no','destination','bill_status','material_model_code',
          'batch_no','output_count','require_count','unit_name','warehouse_name','gmt_create'])

# ─────────────────────────────────────────────────────────────
# 场景4：入库记录与库存更新关联（InboundEventRecord  updatesInventory  Inventory）
#   语义：入库明细通过 batch_no+warehouse_id 关联当前库存，验证入库操作是否正确写入库存
# ─────────────────────────────────────────────────────────────
cur.execute("""
    SELECT d.record_bill_no,
           d.material_model_code,
           d.material_model_name,
           d.batch_no,
           d.count           AS inbound_qty,
           d.unit_name,
           d.warehouse_name  AS inbound_to,
           i.quantity        AS current_stock,
           CASE WHEN i.id IS NULL THEN 'NOT_IN_STOCK' ELSE 'IN_STOCK' END AS match_status
    FROM warehouse_input_record_bill_detail d
    LEFT JOIN warehouse_inventory i
           ON i.batch_no      = d.batch_no
          AND i.warehouse_id  = d.warehouse_id
          AND i.`del`         = 0
    ORDER BY d.gmt_create DESC
    LIMIT 15
""")
print_table(cur.fetchall(), "场景4 · 入库记录 → 库存更新验证  (updatesInventory)",
    cols=['record_bill_no','material_model_code','batch_no',
          'inbound_qty','unit_name','inbound_to','current_stock','match_status'])

# ─────────────────────────────────────────────────────────────
# 场景5：库位库存分布（semi:WarehouseLocation  storedMaterial）
#   语义：各库位（warehouse_model）在库物料种类数和总库存量，
#         warehouse_inventory.warehouse_id → warehouse_model.id
# ─────────────────────────────────────────────────────────────
cur.execute("""
    SELECT m.name                               AS location_name,
           m.type                               AS loc_type,
           COUNT(DISTINCT i.material_model_id)  AS material_types,
           COUNT(i.id)                          AS record_cnt,
           SUM(i.quantity)                      AS total_qty,
           SUM(i.quantity - i.lock_quantity)    AS available_qty
    FROM warehouse_inventory i
    JOIN warehouse_model m ON m.id = i.warehouse_id
    WHERE i.`del` = 0
    GROUP BY i.warehouse_id
    ORDER BY total_qty DESC
    LIMIT 15
""")
rows5 = cur.fetchall()
if not rows5:
    # warehouse_model.id 不对应 inventory.warehouse_id，改用 warehouse_name 直接分组
    print("\n>> warehouse_model JOIN 无结果，改用 warehouse_name 直接聚合")
    cur.execute("""
        SELECT warehouse_name,
               COUNT(DISTINCT material_model_id) AS material_types,
               COUNT(id)                         AS record_cnt,
               SUM(quantity)                     AS total_qty,
               SUM(quantity - lock_quantity)     AS available_qty
        FROM warehouse_inventory
        WHERE `del` = 0
        GROUP BY warehouse_id
        ORDER BY total_qty DESC
        LIMIT 15
    """)
    rows5 = cur.fetchall()
    print_table(rows5, "场景5 · 库位库存分布  (warehouse_name 聚合)",
        cols=['warehouse_name','material_types','record_cnt','total_qty','available_qty'])
else:
    print_table(rows5, "场景5 · 库位库存分布  (JOIN warehouse_model)",
        cols=['location_name','loc_type','material_types','record_cnt','total_qty','available_qty'])

conn.close()
print("\n[验证完成]")
