"""查询库中有出站 wafer 数据的产品+站点，用于验证良率修复"""
import sys, os
sys.path.insert(0, '/Users/fupeggy/NL2SQL')
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
app = create_app()

with app.app_context():
    from app.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()

    # 找有足够出站 wafer 的产品+站点
    cursor.execute("""
        SELECT l.product_code, l.process_code,
               COUNT(DISTINCT w.wafer_id) AS wafer_cnt,
               SUM(CASE WHEN w.wafer_type='good' OR w.wafer_type IS NULL THEN 1 ELSE 0 END) AS good_cnt,
               MIN(DATE(l.gmt_create)) AS earliest,
               MAX(DATE(l.gmt_create)) AS latest
        FROM matrix_routerx_operation_lot_batch_resume_log l
        JOIN matrix_routerx_operation_lot_batch_resume_wafer_detail_log w
          ON w.batch_resume_detail_log_id IN (
              SELECT d.id
              FROM matrix_routerx_operation_lot_batch_resume_detail_log d
              WHERE d.batch_resume_log_id = l.id
          )
        WHERE l.operation_type = 9
          AND (l.deleted = 0 OR l.deleted IS NULL)
        GROUP BY l.product_code, l.process_code
        HAVING wafer_cnt >= 10
        ORDER BY latest DESC, wafer_cnt DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    print(f"{'product_code':<15} {'process_code':<20} {'wafer_cnt':>9} {'good_cnt':>8} {'earliest':<12} {'latest':<12}")
    print("-" * 80)
    for r in rows:
        print(f"{str(r[0]):<15} {str(r[1]):<20} {r[2]:>9} {r[3]:>8} {str(r[4]):<12} {str(r[5]):<12}")

    # 额外：看是否有 deleted=1 的 CheckOut 记录
    cursor.execute("""
        SELECT COUNT(*) AS total_deleted
        FROM matrix_routerx_operation_lot_batch_resume_log
        WHERE operation_type = 9 AND deleted = 1
    """)
    row = cursor.fetchone()
    print(f"\ndeleted=1 的 CheckOut 记录总数: {row[0]}")

    cursor.close()
    conn.close()
