import pymysql
import json

conn = pymysql.connect(host='10.60.120.33', port=3336, user='root',
                       password='Csxw@2024', database='cc_semi_mvp',
                       charset='utf8mb4')
cur = conn.cursor()

# === 场景1: 某产品在某站点的量测参数管控限制 ===
print("=== 场景1: 产品104 在「几何参数检验」站点的量测参数管控限制 ===")
cur.execute("""
SELECT pm.id, pm.product_name,
       jt.station_code, jt.station_name,
       jt.mpl
FROM product_model pm
JOIN JSON_TABLE(
    JSON_EXTRACT(pm.main_route, '$.processes'),
    '$[*]' COLUMNS (
        station_code VARCHAR(20) PATH '$.code',
        station_name VARCHAR(100) PATH '$.name',
        mpl JSON PATH '$.measurementParamList'
    )
) AS jt ON 1=1
WHERE pm.id = 104 AND jt.station_name = '几何参数检验'
LIMIT 1
""")
row = cur.fetchone()
if row:
    pid, pname, scode, sname, mpl_json = row
    print(f"产品: {pid} {pname}, 站点: import pymysql, json

conn = pymysql.connect(host='10.60.120.33', por  
conn = pymysql.con                          password='Csxw@2024', database='cc_semi_mvp')                       charset='utf8mb4')
cur = conn.cursor()

# ==t'cur = conn.cursor()

# === 场景1: 某?.
# === 场景1: ?onprint("=== 场景1: 产品104 在「几何参数检验」站点的??cur.execute("""
SELECT pm.id, pm.product_name,
       jt.station_code, jt.station_name,
       ??SPC监控参数        jt.station_code, jt.stjt       jt.mpl
FROM product_model pm
JOIS FROM product,
JOIN JSON_TABLE(
   AS    JSON_EXTRAC,
    '$[*]' COLUMNS (
        station_code VARCmp        station_codlu        station_name VARCHAR(100) PATH '$.nameIN        mpl JSON PATH '$.measurementParamList'
.p    )
) AS jt ON 1=1
WHERE pm.id = 104 AND jtio) ASmeWHERE pm.id = PLIMIT 1
""")
row = cur.fetchone()
if row:
    pid, pname, s  """)
rmprowSOif row:
    pid, pnnt    piis    print(f"产品: {pid} {pname}, 站点: sp
conn = '$[*]' COLUMNS (
        paramModelId INT PATH '$.paramMoconn = pymysql.con                          passarcur = conn.cursor()

# ==t'cur = conn.cursor()

# === 场景1: 某?.
# === 场景1: ?onprint("=== 场景1:d',
        paramName 
# ==t'cur = conn.'$.
# === 场景1: 某?.
#alu# === 场景1: ?on 'SELECT pm.id, pm.product_name,
       jt.station_code, jt.station_name,
       ??SPC监控参数      rg       jt.station_code, jt.st P       ??SPC监控参数        jt.statd FROM product_model pm
JOIS FROM 104 AND jt.station_name = '抛光前?OIS FROM product,
Jr.JOIN JSON_TABLE(
in   As:
    print(    '$[*]' COLUMNS (SP        station_cod??.p    )
) AS jt ON 1=1
WHERE pm.id = 104 AND jtio) ASmeWHERE pm.id = PLIMIT 1
""")
row = cur.fetchone()
if row:
    pid, pname, s  """)
rmpro??) AS j??HERE pm.id =??"")
row = cur.fetchone()
if row:
    pid, pname, s  ,
row  if row:
    pid, pn_E    pi(prmprowSOif row:
    pi A    pid, pnnt   conn = '$[*]' COLUMNS (
        paramModelId INT PATH '$.paramMoc_r        paramModelId I))
# ==t'cur = conn.cursor()

# === 场景1: 某?.
# === 场景1: ?onprint("=== 场景1:d',
        paramNaSON
# === 场景1: 某?.
#'$.# === 场景1: ?on10        paramName 
# ==t'cur = conn.'$.
#ri# ==t'cur = conn.ow# === 场景1: 某?[#alu# === 场景1: ?2       jt.station_code, jt.station_name,
       ??SPC?u       ??SPC监控参数      rg       ??JOIS FROM 104 AND jt.station_name = '抛光前?OIS FROM product,
Jr.JOIN JSON_TABLE(
in   As:
    print(    '$[*]' COLUMNS.sJr.JOute_name, sr.route_type, sr.sampling_rule
FROM product_model pin   As:
    print
     pri_E) AS jt ON 1=1
WHERE pm.id = 104 AND jtio) ASmeWHERE pm.id   WHERE pm.id =_c""")
row = cur.fetchone()
if row:
    pid, pname, s  ARrowR(if row:
    pid, pn
     pi srmpro??) AS j??HERE p.srow = cur.fetchone()
if row:
   IN if row:
    pid, pnou    pi$[row  if row:
    pi      pid, pnid    pi A    pid, pnnt   conn = '$[*_n        paramModelId INT PATH '$.paramMoc_r   ou# ==t'cur = conn.cursor()

# === 场景1: 某?.
# === 场景1: ?T
# === 场景1: 某?.
# sr# === 场景1: ?on=      "")
rows = cur.fetchall()
for r in row# === 场景1: ??#'$.# === 场景1: ??# ==t'cur = conn.'$.
#ri# ==t'cur = conn.ow]}#ri# ==t'cur = conn}"     r.close(); conn.close()
