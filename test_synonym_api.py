#!/usr/bin/env python3
"""
测试同义词管理 API
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app


def test_synonym_api():
    """测试同义词管理 API 端点"""
    app = create_app('testing')
    client = app.test_client()

    print("=" * 60)
    print("  同义词管理 API 测试")
    print("=" * 60)

    passed = 0
    failed = 0

    def check(name, response, expected_status=200):
        nonlocal passed, failed
        ok = response.status_code == expected_status
        data = response.get_json()
        status = "✅" if ok else "❌"
        print(f"\n{status} {name}")
        print(f"   HTTP {response.status_code} (期望 {expected_status})")
        if data:
            print(f"   Response: {json.dumps(data, ensure_ascii=False)[:200]}")
        if ok:
            passed += 1
        else:
            failed += 1
        return data

    # 1. GET /api/synonyms - 列表
    data = check("GET /api/synonyms",
                 client.get('/api/synonyms'))

    # 2. GET /api/synonyms/tables - 表摘要
    check("GET /api/synonyms/tables",
          client.get('/api/synonyms/tables'))

    # 3. GET /api/synonyms/map - 映射表
    data = check("GET /api/synonyms/map",
                 client.get('/api/synonyms/map'))
    if data and data.get('data'):
        print(f"   映射总数: {data.get('total', 0)}")

    # 4. GET /api/synonyms/lookup?keyword=片篮
    data = check("GET /api/synonyms/lookup?keyword=片篮",
                 client.get('/api/synonyms/lookup?keyword=片篮'))
    if data:
        print(f"   片篮 -> {data.get('table_name')}, matched={data.get('matched')}")

    # 5. GET /api/synonyms/lookup - 未匹配词
    data = check("GET /api/synonyms/lookup?keyword=不存在的表",
                 client.get('/api/synonyms/lookup?keyword=不存在的表'))
    if data:
        print(f"   不存在的表 -> {data.get('table_name')}, matched={data.get('matched')}")

    # 6. GET /api/synonyms/stats
    check("GET /api/synonyms/stats",
          client.get('/api/synonyms/stats'))

    # 7. POST /api/synonyms - 添加 (可能因无 DB 而失败，但不应 500)
    data = check("POST /api/synonyms (添加)",
                 client.post('/api/synonyms',
                             json={"table_name": "carriers", "synonym": "test_alias_api"}),
                 expected_status=201)

    # 8. GET /api/synonyms/unmatched
    check("GET /api/synonyms/unmatched",
          client.get('/api/synonyms/unmatched'))

    # 9. GET /api/synonyms/audit-log
    check("GET /api/synonyms/audit-log",
          client.get('/api/synonyms/audit-log'))

    # 10. 参数校验: POST 缺少 table_name
    check("POST /api/synonyms (缺少 table_name)",
          client.post('/api/synonyms', json={"synonym": "test"}),
          expected_status=400)

    # 11. 参数校验: POST 缺少 synonym
    check("POST /api/synonyms (缺少 synonym)",
          client.post('/api/synonyms', json={"table_name": "carriers"}),
          expected_status=400)

    # 12. 参数校验: lookup 缺少 keyword
    check("GET /api/synonyms/lookup (缺少 keyword)",
          client.get('/api/synonyms/lookup'),
          expected_status=400)

    print("\n" + "=" * 60)
    print(f"  结果: 通过 {passed}/{passed + failed}, 失败 {failed}")
    print("=" * 60)
    return failed == 0


if __name__ == '__main__':
    success = test_synonym_api()
    sys.exit(0 if success else 1)
