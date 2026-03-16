import mysql.connector, json
conn = mysql.connector.connect(host='10.60.120.33', port=3336, user='root', password='Csxw@2024', database='cc_semi_mvp')
cur = conn.cursor()

# 1. sub_route structure
cur.execute("SELECT id, sub_route FROM product_model WHERE sub_route IS NOT NULL AND sub_route NOT IN ('', 'null') LIMIT 3")
for r in cur.fetchall():
    sr = json.loads(r[1]) if r[1] else {}
    tp = type(sr).__name__
    if isinstance(sr, list):
        print("product_id=%d sub_route=LIST len=%d" % (r[0], len(sr)))
        if sr:
            print("  item[0] keys:", list(sr[0].keys()) if isinstance(sr[0], dict) else str(sr[0])[:100])
    else:
        print("product_id=%d sub_route=DICT keys=%s" % (r[0], list(sr.keys())))
        print("  sample:", str(sr)[:200])

# 2. matrix_routerx_config_route schema
cur.execute('DESCRIBE matrix_routerx_config_route')
print("\nmatrix_routerx_config_route cols:", [r[0] for r in cur.fetchall()])

# 3. process node with routeId
cur.execute("SELECT id, main_route FROM product_model WHERE id=155")
r = cur.fetchone()
mr = json.loads(r[1])
proc0 = mr['processes'][0]
keys_of_interest = ['id', 'code', 'name', 'routeId', 'version', 'recipeCode']
print("\nProcess node with routeId (keys):", {k: proc0.get(k) for k in keys_of_interest})

# 4. Check if processDataGroupList in a constraint node appears as groupId in processParamList
cur.execute("SELECT id, main_route FROM product_model WHERE main_route IS NOT NULL AND JSON_LENGTH(main_route, '$.processes') > 0 LIMIT 10")
rows = cur.fetchall()
for r in rows:
    mr = json.loads(r[1])
    for proc in mr.get('processes', []):
        pdg = proc.get('processDataGroupList') or []
        pl = proc.get('processParamList') or []
        if pdg and pl:
            pdg_ids = [x.get('id') for x in pdg if isinstance(x, dict)]
            pl_gids = set(item.get('groupId') for item in pl if item.get('groupId'))
            print("\nStation match analysis: product=%d station=%s" % (r[0], proc.get('code')))
            print("  processDataGroupList ids:", pdg_ids)
            print("  processParamList groupIds:", pl_gids)
            break
    else:
        continue
    break

conn.close()
