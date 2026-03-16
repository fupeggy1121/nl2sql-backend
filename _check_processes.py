import os, pymysql, json
from dotenv import load_dotenv
load_dotenv()

conn = pymysql.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', 3306)),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    charset='utf8mb4',
    connect_timeout=10
)
cur = conn.cursor()

# 先查路由是否存在
cur.execute("SELECT id, name FROM matrix_routerx_config_route WHERE name='GKY_0818001_test' LIMIT 1")
row = cur.fetchone()
if not row:
    cur.execute("SELECT id, name FROM matrix_routerx_config_route LIMIT 5")
    print("Route not found. Sample routes:", cur.fetchall())
else:
    print(f"Route id={row[0]}, name={row[1]}")
    cur.execute("SELECT processes FROM matrix_routerx_config_route WHERE id=%s", (row[0],))
    val = cur.fetchone()[0]
    print("processes column type:", type(val))
    if isinstance(val, str):
        parsed = json.loads(val)
    else:
        parsed = val
    print("processes sample (first 2 elements):")
    print(json.dumps(parsed[:2], ensure_ascii=False, indent=2))
    print(f"total elements: {len(parsed)}")
    print("\nAll keys in first element:", list(parsed[0].keys()) if parsed else "empty")

    # 测试正确的 MySQL JSON 查询
    print("\n--- Testing correct MySQL JSON query ---")
    # MySQL 中 JSON 数组展开需用 JSON_TABLE (MySQL 8.0+) 或 JSON_EXTRACT
    # 先验证 JSON_EXTRACT 单个元素
    cur.execute("""
        SELECT JSON_EXTRACT(processes, '$[0]') AS first_elem
        FROM matrix_routerx_config_route WHERE id=%s
    """, (row[0],))
    print("First element via JSON_EXTRACT:", cur.fetchone())

conn.close()
