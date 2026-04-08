import pymysql, pymysql.cursors

conn = pymysql.connect(
    host='10.60.120.33', port=3336,
    db='cc_semi_mvp', user='root', password='Csxw@2024',
    charset='utf8mb4', connect_timeout=5,
    cursorclass=pymysql.cursors.DictCursor
)
cur = conn.cursor()

tables = [
    'equipment_realtime_info',
    'equipment_realtime_record',
    'equipment_log',
    'equipment_detail_log',
    'equipment_processing_record',
]

for tbl in tables:
    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, COLUMN_COMMENT
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
    """, (tbl,))
    cols = cur.fetchall()

    cur.execute(f"SELECT COUNT(*) as cnt FROM `{tbl}`")
    cnt = cur.fetchone()['cnt']

    print(f"\n{'='*60}")
    print(f"  {tbl}  (rows={cnt})")
    print(f"{'='*60}")
    for c in cols:
        comment = c['COLUMN_COMMENT'] or ''
        print(f"  {c['COLUMN_NAME']:35s} {c['DATA_TYPE']:12s} {comment[:40]}")

    if cnt > 0:
        cur.execute(f"SELECT * FROM `{tbl}` LIMIT 2")
        rows = cur.fetchall()
        print(f"\n  --- sample rows ---")
        for row in rows:
            for k, v in row.items():
                print(f"    {k}: {v}")
            print()

conn.close()
