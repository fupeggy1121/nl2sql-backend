import mysql.connector, json

conn = mysql.connector.connect(host='10.60.120.33', port=3336, user='root', password='Csxw@2024', database='cc_semi_mvp')
cur = conn.cursor()

cur.execute("SELECT id, main_route FROM product_model WHERE main_route IS NOT NULL AND JSON_LENGTH(main_route, '$.processes') > 0")
rows = cur.fetchall()

param_keys_seen = set()
measure_keys_seen = set()
spc_keys_seen = set()
route_root_keys_seen = set()
has_paramModelId = False

for r in rows:
    mr = json.loads(r[1])
    route_root_keys_seen.update(mr.keys())
    for proc in mr.get('processes', []):
        for item in proc.get('processParamList', []):
            param_keys_seen.update(item.keys())
            if 'paramModelId' in item or 'paramId' in item or 'paramModel' in item:
                has_paramModelId = True
                print(f"  Found paramModelId-like key in processParamList: {list(item.keys())}, value sample: {item}")
        for item in proc.get('measurementParamList', []):
            measure_keys_seen.update(item.keys())
        for item in proc.get('spcParamList', []):
            spc_keys_seen.update(item.keys())

cur.execute("SELECT COUNT(*) FROM product_model WHERE sub_route IS NOT NULL AND sub_route != '' AND sub_route != '{}'")
sub_route_count = cur.fetchone()[0]

print(f'Total products with route data: {len(rows)}')
print(f'Sub-route non-empty count: {sub_route_count}')
print()
print('main_route root keys (union all products):', sorted(route_root_keys_seen))
print()
print('processParamList item keys (union all products):', sorted(param_keys_seen))
print(f'Any paramModelId-like key found: {has_paramModelId}')
print()
print('measurementParamList item keys (union all products):', sorted(measure_keys_seen))
print()
print('spcParamList item keys (union all products):', sorted(spc_keys_seen))

# Sample a full processParamList and measurementParamList with multiple items
for r in rows:
    mr = json.loads(r[1])
    for proc in mr.get('processes', []):
        pl = proc.get('processParamList', [])
        ml = proc.get('measurementParamList', [])
        sl = proc.get('spcParamList', [])
        if pl and len(pl) >= 2:
            print(f'\n=== Sample processParamList (product_id={r[0]}, station={proc.get("code")}):')
            for item in pl[:3]:
                print(' ', item)
            break
    else:
        continue
    break

for r in rows:
    mr = json.loads(r[1])
    for proc in mr.get('processes', []):
        sl = proc.get('spcParamList', [])
        if sl:
            print(f'\n=== Sample spcParamList (product_id={r[0]}, station={proc.get("code")}):')
            for item in sl[:3]:
                print(' ', item)
            break
    else:
        continue
    break

conn.close()
