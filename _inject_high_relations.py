"""一次性脚本：将 relation_mappings_high.json 中的 82 条高置信度关系注入 mapping_prod.json"""
import json, os

HIGH_FILE = "relation_mappings_high.json"
PROD_FILE = "app/ontology/data/mapping_prod.json"
TMP_FILE  = PROD_FILE + ".tmp"

with open(HIGH_FILE, encoding="utf-8") as f:
    high = json.load(f)
rels_high = high["relation_mappings"]

with open(PROD_FILE, encoding="utf-8") as f:
    prod = json.load(f)

prod["relation_mappings"] = rels_high

with open(TMP_FILE, "w", encoding="utf-8") as f:
    json.dump(prod, f, ensure_ascii=False, indent=2)
os.replace(TMP_FILE, PROD_FILE)

print(f"✅ 写入完成：{len(rels_high)} 条高置信度关系映射")

with open(PROD_FILE, encoding="utf-8") as f:
    check = json.load(f)
print("验证 relation_mappings 数量:", len(check["relation_mappings"]))

from collections import Counter
ctr = Counter(r["strategy"] for r in check["relation_mappings"])
print("策略分布:")
for k, v in sorted(ctr.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

# 打印前3条供肉眼核查
print("\n前3条样例:")
for r in check["relation_mappings"][:3]:
    print(f'  [{r["strategy"]}] {r["logic_relation"]}')
    print(f'    {r["description"]}')
    print(f'    join: {r["join_logic"]}')
