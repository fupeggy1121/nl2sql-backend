import mysql.connector, json
conn = mysql.connector.connect(host='10.60.120.33', port=3336, user='root', password='Csxw@2024', database='cc_semi_mvp')
cur = conn.cursor()

cur.execute("SELECT id, main_route FROM product_model WHERE main_route IS NOT NULL AND JSON_LENGTH(main_route, '$.processes') > 0 LIMIT 30")
rows = cur.fetchall()

multi_group_process = 0
multi_group_measure = 0
sample_with_pdg = None

for r in rows:
    mr = json.loads(r[1])
    for proc in mr.get('processes', []):
        pl = proc.get('processParamList') or []
        ml = proc.get('measurementParamList') or []
        pdg = proc.get('processDataGroupList') or []
        mdg = proc.get('measurementDataGroupList') or []
        proc_gids = set(item.get('groupId') for item in pl if item.get('groupId'))
        meas_gids = set(item.get('groupId') for item in ml if item.get('groupId'))
        if len(proc_gids) > 1:
            multi_group_process += 1
            print("MULTI-GROUP processParamList: product=%d station=%s groupIds=%s" % (r[0], proc.get('code'), proc_gids))
        if len(meas_gids) > 1:
            multi_group_measure += 1
            print("MULTI-GROUP measurementParamList: product=%d station=%s groupIds=%s" % (r[0], proc.get('code'), meas_gids))
        # Show sample with both PDG and PL
        if pdg and pl and sample_with_pdg is None:
            sample_with_pdg = (r[0], proc.get('code'), pdg, mdg, proc_gids, meas_gids)

print("\n=== Summary ===")
print("Multi-group processParamList constraint nodes:", multi_group_process)
print("Multi-group measurementParamList constraint nodes:", multi_group_measure)
if sample_with_pdg:
    print("\nSample process node with DataGroupList:")
    print("  product=%d, station=%s" % (sample_with_pdg[0], sample_with_pdg[1]))
    print("  processDataGroupList:", sample_with_pdg[2])
    print("  measurementDataGroupList:", sample_with_pdg[3])
    print("  processParamList groupIds:", sample_with_pdg[4])
    print("  measurementParamList groupIds:", sample_with_pdg[5])

# sub_route status
cur.execute("SELECT COUNT(*) FROM product_model WHERE sub_route IS NOT NULL AND sub_route NOT IN ('', 'null')")
sr_count = cur.fetchone()[0]
print("\nsub_route non-empty count:", sr_count)

# Check matrix_routerx_config_route exists
cur.execute("SHOW TABLES LIKE '%route%'")
print("Tables with 'route':", [x[0] for x in cur.fetchall()])

conn.close()
