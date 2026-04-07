"""验证 deleted 过滤修复：确认 final_yield >= first_pass_yield"""
import requests, json, sys

BASE = "http://localhost:8000/api/v1/chat"
HEADERS = {"Content-Type": "application/json"}

def ask(question):
    payload = {"message": question, "session_id": "verify_deleted_fix"}
    try:
        r = requests.post(BASE, json=payload, headers=HEADERS, timeout=120)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# 查询一个时间跨度较大的范围，保证有数据
queries = [
    ("final_yield",      "查询 Y08 产品 2024年1月到2025年12月 的综合良率"),
    ("first_pass_yield", "查询 Y08 产品 2024年1月到2025年12月 的一次良率"),
]

results = {}
for name, q in queries:
    print(f"\n>>> {name}: {q}")
    resp = ask(q)
    answer = resp.get("answer") or resp.get("response") or resp.get("message") or json.dumps(resp)[:300]
    print(f"    {answer[:400]}")
    results[name] = answer

print("\n" + "="*60)
print("结论: 检查上方两个结果，确认综合良率 >= 一次良率")
print("="*60)
