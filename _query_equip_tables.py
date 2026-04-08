import os, pymysql, pymysql.cursors

conn = pymysql.connect(
    host='10.60.120.33', port=3336,
    db='cc_semi_mvp', user='root', password='Csxw@2024',
    charset='utf8mb4', connect_timeout=5,
    cursorclass=pymysql.cursors.DictCursor
)
cur = conn.cursor()

print("=== 设备/状态/报警/EAP 相关表 ===")
cur.execute("""
    SELECT TABLE_NAME, TABLE_COMMENT
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND (TABLE_NAME LIKE '%equip%' OR TABLE_NAME LIKE '%alarm%'
           OR TABLE_NAME LIKE '%fault%' OR TABLE_NAME LIKE '%eap%'
           OR TABLE_NAME LIKE '%state%' OR TABLE_NAME LIKE '%status%'
           OR TABLE_NAME LIKE '%downtime%' OR TABLE_NAME LIKE '%maint%'
           OR TABLE_NAME LIKE '%machine%' OR TABLE_NAME LIKE '%device%')
    ORDER BY TABLE_NAME
""")
for r in cur.fetchall():
    print(f"  {r['TABLE_NAME']:50s} | {(r['TABLE_COMMENT'] or '')[:60]}")

print()
print("=== equipment 开头的表（精确）===")
cur.execute("""
    SELECT TABLE_NAME, TABLE_COMMENT
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME LIKE 'equipment%'
    ORDER BY TABLE_NAME
""")
for r in cur.fetchall():
    count_cur = conn.cursor()
    count_cur.execute(f"SELECT COUNT(*) as cnt FROM `{r['TABLE_NAME']}`")
    cnt = count_cur.fetchone()['cnt']
    print(f"  {r['TABLE_NAME']:50s} | rows={cnt:6d} | {(r['TABLE_COMMENT'] or '')[:50]}")

conn.close()
