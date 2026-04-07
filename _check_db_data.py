import pymysql, os

# 加载 .env 文件（不覆盖已存在的环境变量）
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

source = os.getenv("MYSQL_SOURCE", "test").upper()
def g(key, fallback):
    return (os.getenv(f"MYSQL_{key}_{source}")
            or os.getenv(f"MYSQL_{key}")
            or os.getenv(f"PROD_DB_{key}", fallback))

conn = pymysql.connect(
    host=g("HOST","10.60.120.33"), port=int(g("PORT","3336")),
    db=g("DB","cc_semi_mvp"), user=g("USER","root"),
    password=g("PASSWORD",""), charset="utf8mb4", connect_timeout=5
)
cur = conn.cursor()

print("=== 1. deleted 分布（TOP产品，operation_type=9）===")
cur.execute("""
SELECT product_code, COUNT(*) total,
       SUM(deleted=1) del1,
       SUM(deleted=0 OR deleted IS NULL) kept
FROM matrix_routerx_operation_lot_batch_resume_log
WHERE operation_type=9
GROUP BY product_code ORDER BY total DESC LIMIT 5
""")
products = []
for r in cur.fetchall():
    print(f"  {r[0]}  total={r[1]}  deleted={r[2]}  kept={r[3]}")
    if r[2] and int(r[2]) > 0:
        products.append(r[0])

if not products:
    print("  (所有产品 deleted=0，无 deleted 记录差异)")
    # 仍用第一个产品做 FY vs FPY 对比
    cur.execute("""SELECT product_code FROM matrix_routerx_operation_lot_batch_resume_log
                   WHERE operation_type=9 GROUP BY product_code ORDER BY COUNT(*) DESC LIMIT 1""")
    row = cur.fetchone()
    if row:
        products = [row[0]]

print("=== 分析：返工场景下 FY vs FPY 的理论关系 ===")
# 简单查：每个 (wafer_id, process_code) 的首次和末次 wafer_type
cur.execute("""
SELECT wafer_id, process_code,
       MIN(CASE WHEN rn_asc=1  THEN wafer_type END) first_type,
       MIN(CASE WHEN rn_desc=1 THEN wafer_type END) last_type,
       COUNT(*) AS cnt
FROM (
    SELECT w.wafer_id, l.process_code, w.wafer_type,
           ROW_NUMBER() OVER (PARTITION BY w.wafer_id, l.process_code ORDER BY l.gmt_create ASC)  rn_asc,
           ROW_NUMBER() OVER (PARTITION BY w.wafer_id, l.process_code ORDER BY l.gmt_create DESC) rn_desc
    FROM matrix_routerx_operation_lot_batch_resume_log l
    JOIN matrix_routerx_operation_lot_batch_resume_log_detail d ON d.batch_resume_log_id=l.id
    JOIN matrix_routerx_operation_lot_batch_resume_wafer_detail_log w ON w.batch_resume_detail_log_id=d.id
    WHERE l.operation_type=9 AND (l.deleted=0 OR l.deleted IS NULL)
    LIMIT 50000
) t
GROUP BY wafer_id, process_code
LIMIT 5000
""")
rows = cur.fetchall()
multi_checkout = [r for r in rows if r[4] > 1]
total = len(rows)

print(f"  总 (wafer, process_code) 对: {total}")
print(f"  其中多次出站（经历返工）的:  {len(multi_checkout)}")

def is_good(v):
    return v is None or v == 'good' or v == ''

# 统计四种场景
good_to_ng = [r for r in rows if     is_good(r[2]) and not is_good(r[3])]  # FPY好→FY差
ng_to_good = [r for r in rows if not is_good(r[2]) and     is_good(r[3])]  # FPY差→FY好（返工成功）
both_good  = [r for r in rows if     is_good(r[2]) and     is_good(r[3])]
both_ng    = [r for r in rows if not is_good(r[2]) and not is_good(r[3])]

print(f"\n  首次good→末次NG  (拉低FY, 导致FY<FPY可能): {len(good_to_ng)}")
print(f"  首次NG→末次good  (返工成功, 拉高FY):         {len(ng_to_good)}")
print(f"  首末均good:                                  {len(both_good)}")
print(f"  首末均NG:                                    {len(both_ng)}")

fpy_good_cnt = len(both_good) + len(good_to_ng)
fy_good_cnt  = len(both_good) + len(ng_to_good)
fpy_pct = fpy_good_cnt / total * 100
fy_pct  = fy_good_cnt  / total * 100
print(f"\n  计算一次良率(FPY): {fpy_good_cnt}/{total} = {fpy_pct:.2f}%")
print(f"  计算综合良率(FY):  {fy_good_cnt}/{total}  = {fy_pct:.2f}%")
print(f"\n  FY >= FPY ? {'✅ 正常' if fy_good_cnt >= fpy_good_cnt else '❌ FY < FPY'}")
if good_to_ng:
    print(f"\n  注意: 存在 {len(good_to_ng)} 片「首次good但末次NG」的wafer（返工失败）。")
    print(f"       这使 FY 低于 FPY {abs(fy_pct - fpy_pct):.2f}pp，是业务合理场景，非 deleted 导致的 bug。")

conn.close()
print("\nDone.")
