#!/usr/bin/env python3
"""
generate_mapping_prod.py
─────────────────────────────────────────────────────────────────────────────
从生产 PostgreSQL 库自动读取表结构，生成 mapping_prod.json。

用法（在能访问生产库的机器上运行）:
    python generate_mapping_prod.py

输出: app/ontology/data/mapping_prod.json（自动写入，可直接审查）
─────────────────────────────────────────────────────────────────────────────
"""

import json
import os
import sys
from pathlib import Path

# ── 配置（优先读环境变量，或直接改这里）──────────────────────────────────────────
DB_HOST     = os.getenv("PROD_DB_HOST",     "10.60.120.33")
DB_PORT     = int(os.getenv("PROD_DB_PORT", "3336"))
DB_NAME     = os.getenv("PROD_DB_NAME",     "cc_semi_mvp")
DB_USER     = os.getenv("PROD_DB_USER",     "root")
DB_PASSWORD = os.getenv("PROD_DB_PASSWORD", "Csxw@2024")
DATABASE_URL = os.getenv("DATABASE_URL", "")   # 仅用于显示，连接用 psycopg2 kwargs

OUTPUT_FILE = Path(__file__).parent / "app/ontology/data/mapping_prod.json"

# 排除这些系统/NL2SQL 元数据表
EXCLUDE_TABLES = {
    "table_annotations", "column_annotations",          # NL2SQL 元数据表
    "django_migrations", "django_content_type",          # Django 系统表
    "auth_user", "auth_group", "auth_permission",
    "django_admin_log", "django_session",
}

# 半导体领域关键词 → 语义类映射（根据表名猜测 logic_class，可审查修正）
KEYWORD_CLASS_MAP = [
    (["wafer"],                     "semi:Wafer",         "晶圆"),
    (["lot", "batch"],              "semi:ProductionLot", "批次"),
    (["sub_batch", "sublot"],       "semi:Sublot",        "子批次"),
    (["station", "process_step"],   "semi:ProcessStation","工艺站点"),
    (["equip"],                     "semi:Equipment",     "设备"),
    (["carrier", "cassette"],       "semi:Carrier",       "载具"),
    (["recipe"],                    "semi:Recipe",        "配方"),
    (["route", "flow"],             "semi:Route",         "工艺路线"),
    (["product"],                   "semi:Product",       "产品"),
    (["work_order", "workorder"],   "semi:WorkOrder",     "工单"),
    (["defect", "inspection"],      "semi:Defect",        "缺陷"),
    (["material"],                  "semi:Material",      "物料"),
    (["operation", "operation"],    "semi:Operation",     "操作"),
    (["measure", "measurement"],    "semi:Measurement",   "测量"),
    (["alarm"],                     "semi:Alarm",         "报警"),
    (["operator", "employee"],      "semi:Person",        "人员"),
    (["tool"],                      "semi:Tool",          "工具"),
]


def guess_class_and_label(table_name: str) -> tuple[str, str]:
    t = table_name.lower()
    for keywords, logic_class, label_cn in KEYWORD_CLASS_MAP:
        if any(kw in t for kw in keywords):
            return logic_class, label_cn
    # fallback: PascalCase from table name
    pascal = "".join(w.capitalize() for w in t.split("_"))
    return f"semi:{pascal}", table_name


def guess_display_column(columns: list[str]) -> str:
    """Choose the most likely display column."""
    preferred = ["name", "code", "title", "label", "no", "number",
                 "serial_no", "serial_number"]
    for p in preferred:
        for col in columns:
            if col.lower() == p:
                return col
    # second pass: endswith
    for p in preferred:
        for col in columns:
            if col.lower().endswith(f"_{p}") or col.lower().endswith(f"_{p[:-1]}"):
                return col
    return columns[0] if columns else "id"


def main():
    try:
        import psycopg2
    except ImportError:
        sys.exit("❌ 请先安装 psycopg2: pip install psycopg2-binary")

    connect_kwargs = dict(host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                          user=DB_USER, password=DB_PASSWORD, connect_timeout=10)
    print(f"🔌 连接数据库: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    try:
        conn = psycopg2.connect(**connect_kwargs)
    except Exception as e:
        sys.exit(f"❌ 连接失败: {e}")

    cur = conn.cursor()

    # 获取所有用户表
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall() if row[0] not in EXCLUDE_TABLES]
    print(f"📋 发现 {len(tables)} 张表: {', '.join(tables)}")

    # 获取主键
    cur.execute("""
        SELECT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = 'public';
    """)
    pk_map = {row[0]: row[1] for row in cur.fetchall()}

    # 获取列信息
    cur.execute("""
        SELECT table_name, column_name, data_type, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """)
    col_rows = cur.fetchall()

    cols_by_table: dict[str, list[str]] = {}
    for table, col, dtype, _ in col_rows:
        if table not in EXCLUDE_TABLES:
            cols_by_table.setdefault(table, []).append(col)

    conn.close()

    # ── 构建 object_mappings ──────────────────────────────────────────────────
    object_mappings = []
    for table in tables:
        columns = cols_by_table.get(table, [])
        pk = pk_map.get(table, "id")
        logic_class, label_cn = guess_class_and_label(table)
        display_col = guess_display_column([c for c in columns if c != pk])

        # 选 key_columns：pk + display + 常见业务列（去重保序，最多 15 列）
        priority = [pk, display_col, "status", "code", "name", "created_at",
                    "updated_at", "type", "description"]
        key_cols = []
        for c in priority + columns:
            if c in columns and c not in key_cols:
                key_cols.append(c)
            if len(key_cols) >= 15:
                break

        object_mappings.append({
            "logic_class": logic_class,
            "physical_table": table,
            "primary_key": pk,
            "label_cn": label_cn,
            "display_column": display_col,
            "properties": {"semi:hasState": "status"} if "status" in columns else {},
            "key_columns": key_cols,
        })

    # ── 构建 relation_mappings（基于外键）────────────────────────────────────
    conn = psycopg2.connect(**connect_kwargs)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            kcu.table_name   AS source_table,
            kcu.column_name  AS source_col,
            ccu.table_name   AS target_table,
            ccu.column_name  AS target_col
        FROM information_schema.referential_constraints rc
        JOIN information_schema.key_column_usage kcu
            ON rc.constraint_name = kcu.constraint_name
           AND kcu.table_schema = 'public'
        JOIN information_schema.constraint_column_usage ccu
            ON rc.unique_constraint_name = ccu.constraint_name
           AND ccu.table_schema = 'public'
        ORDER BY kcu.table_name, kcu.column_name;
    """)
    fk_rows = cur.fetchall()
    conn.close()

    relation_mappings = []
    for src_tbl, src_col, tgt_tbl, tgt_col in fk_rows:
        if src_tbl in EXCLUDE_TABLES or tgt_tbl in EXCLUDE_TABLES:
            continue
        src_label = next((m["label_cn"] for m in object_mappings
                          if m["physical_table"] == src_tbl), src_tbl)
        tgt_label = next((m["label_cn"] for m in object_mappings
                          if m["physical_table"] == tgt_tbl), tgt_tbl)
        relation_mappings.append({
            "logic_property": "semi:relatedTo",
            "source_table":   src_tbl,
            "source_column":  src_col,
            "target_table":   tgt_tbl,
            "target_column":  tgt_col,
            "label_cn":       f"{src_label}→{tgt_label}",
        })

    # ── 写文件 ────────────────────────────────────────────────────────────────
    mapping = {
        "version":          "2026-V2",
        "customer":         "Prod",
        "description":      "生产库 cc_semi_mvp 本体→物理表映射字典（自动生成，请审查 label_cn / display_column）",
        "object_mappings":  object_mappings,
        "relation_mappings": relation_mappings,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(mapping, ensure_ascii=False, indent=2))
    print(f"\n✅ 已写入: {OUTPUT_FILE}")
    print(f"   object_mappings:   {len(object_mappings)} 张表")
    print(f"   relation_mappings: {len(relation_mappings)} 条外键关系")
    print("\n📝 请审查以下内容后可直接使用:")
    print("   1. label_cn（中文名）是否准确")
    print("   2. display_column（首选展示列）是否合适")
    print("   3. 有无需要排除的内部系统表（加入 EXCLUDE_TABLES 后重新运行）")


if __name__ == "__main__":
    main()
