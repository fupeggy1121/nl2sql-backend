#!/usr/bin/env python
"""
批量批准列注解的脚本
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000/api"

# 待审核的列注解 IDs
PENDING_ANNOTATIONS = [
    "3f767ed9-7a60-45e1-abb3-3c96bdac7e87",  # order_number
    "c75454c8-fbc0-4792-99b1-e43376c0c1f8",  # quantity
    "e9cd0560-f6bb-4883-b74a-0e86513b4085",  # status
    "f75e2fb0-15ba-4e5a-bbdb-ae767a96934a",  # equipment_code
    "822b8df5-d535-4f10-9cb9-35e94d2a6ebd",  # equipment_type
]

def approve_annotation(annotation_id, notes="LLM-generated, auto-approved"):
    """批准单个注解"""
    url = f"{BASE_URL}/schema/columns/{annotation_id}/approve"
    
    payload = {
        "reviewed_by": "system_llm",
        "notes": notes
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 批准成功: {annotation_id}")
            print(f"   列: {data.get('annotation', {}).get('column_name_cn')} ({data.get('annotation', {}).get('column_name')})")
            print(f"   状态: {data.get('annotation', {}).get('status')}")
            return True
        else:
            print(f"❌ 批准失败: {annotation_id}")
            print(f"   状态码: {response.status_code}")
            print(f"   错误: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 错误: {annotation_id}")
        print(f"   {str(e)}")
        return False

def main():
    print("=" * 60)
    print("开始批量批准列注解")
    print("=" * 60)
    
    total = len(PENDING_ANNOTATIONS)
    approved = 0
    
    for idx, annotation_id in enumerate(PENDING_ANNOTATIONS, 1):
        print(f"\n[{idx}/{total}] 处理注解 {annotation_id}...")
        if approve_annotation(annotation_id):
            approved += 1
        print()
    
    print("=" * 60)
    print(f"批准完成: {approved}/{total} 个注解成功批准")
    print("=" * 60)
    
    # 验证最终状态
    print("\n验证最终状态...")
    try:
        response = requests.get(f"{BASE_URL}/schema/status")
        if response.status_code == 200:
            data = response.json()
            print(f"\n当前待审核状态:")
            print(f"  • 待审核表注解: {data['status']['pending_table_annotations']}")
            print(f"  • 待审核列注解: {data['status']['pending_column_annotations']}")
    except Exception as e:
        print(f"验证失败: {str(e)}")

if __name__ == "__main__":
    main()
