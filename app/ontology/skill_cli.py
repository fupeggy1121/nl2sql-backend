#!/usr/bin/env python3
"""
本体建模技能 CLI 入口

用法:
  # 从 JSON 文件构建
  python -m app.ontology.skill_cli build spec.json

  # 预览变更（不写文件）
  python -m app.ontology.skill_cli preview spec.json

  # 诊断当前本体健康状况
  python -m app.ontology.skill_cli diagnose

  # 从 stdin 读取 JSON
  cat spec.json | python -m app.ontology.skill_cli build -

示例 spec.json:
{
  "message": "添加新的设备子类",
  "author": "admin",
  "classes": [
    {
      "uri": "semi:RobotArm",
      "label": "机械臂(RobotArm)",
      "comment": "自动化搬运设备",
      "parent_uri": "semi:Equipment",
      "physical_table": "robot_arms",
      "primary_key": "id",
      "label_cn": "机械臂",
      "display_column": "arm_code",
      "key_columns": ["id", "arm_code", "status"]
    }
  ],
  "relations": [
    {
      "uri": "semi:operatedByArm",
      "label": "由机械臂操作",
      "domain_uri": "semi:ProcessStation",
      "range_uri": "semi:RobotArm",
      "strategy": "ForeignKey",
      "description": "工站关联机械臂",
      "join_logic": {
        "source_table": "matrix_routerx_config_process",
        "source_key": "robot_arm_id",
        "target_table": "robot_arms",
        "target_key": "id"
      }
    }
  ],
  "data_properties": [
    {
      "uri": "semi:hasArmCode",
      "label": "机械臂编码",
      "domain_uris": ["semi:RobotArm"],
      "range_type": "xsd:string"
    }
  ],
  "value_mappings": [
    {
      "domain": "semi:RobotArmStatus",
      "semantic_value": "Idle",
      "description": "机械臂空闲",
      "physical_condition": "status = 0",
      "applies_to_table": "robot_arms",
      "applies_to_column": "status"
    }
  ]
}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _run_build(spec_path: str, preview_only: bool = False) -> None:
    """执行构建或预览"""
    from app.ontology.skill import build_from_dict, preview_from_dict

    # 读取 spec
    if spec_path == "-":
        data = json.load(sys.stdin)
    else:
        with open(spec_path, "r", encoding="utf-8") as f:
            data = json.load(f)

    if preview_only:
        result = preview_from_dict(data)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        if result.has_errors:
            sys.exit(1)
    else:
        result = build_from_dict(data)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        if not result.success:
            sys.exit(1)


def _run_diagnose() -> None:
    """执行诊断"""
    from app.ontology.skill import diagnose_ontology
    result = diagnose_ontology()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m app.ontology.skill_cli <command> [args]")
        print("Commands: build <spec.json>, preview <spec.json>, diagnose")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "build":
        if len(sys.argv) < 3:
            print("Usage: python -m app.ontology.skill_cli build <spec.json | ->")
            sys.exit(1)
        _run_build(sys.argv[2], preview_only=False)
    elif cmd == "preview":
        if len(sys.argv) < 3:
            print("Usage: python -m app.ontology.skill_cli preview <spec.json | ->")
            sys.exit(1)
        _run_build(sys.argv[2], preview_only=True)
    elif cmd == "diagnose":
        _run_diagnose()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
