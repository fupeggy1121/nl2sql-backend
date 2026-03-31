"""
本体建模技能 — 单元测试

覆盖:
  1. Spec 解析
  2. Preview 校验（正常 + 错误场景）
  3. Commit（新增类/关系/值映射）
  4. Diagnose
  5. 幂等性：重复 commit 不产生副作用
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# 确保使用测试用的数据目录
TEST_DIR = Path(tempfile.mkdtemp(prefix="ontology_skill_test_"))


@pytest.fixture(autouse=True)
def _setup_test_env(tmp_path):
    """为每个测试创建独立的 TTL + mapping 文件"""
    # 复制生产文件到临时目录
    src_data = Path(__file__).resolve().parent.parent / "app" / "ontology" / "data"
    ttl_src = src_data / "semi-cim-ontology.ttl"
    mapping_src = src_data / "mapping_prod.json"

    ttl_dst = tmp_path / "semi-cim-ontology.ttl"
    mapping_dst = tmp_path / "mapping_test.json"
    versions_dir = tmp_path / "versions"
    versions_dir.mkdir(exist_ok=True)

    if ttl_src.exists():
        shutil.copy(ttl_src, ttl_dst)
    else:
        # 最小 TTL
        ttl_dst.write_text("""
@prefix semi: <http://www.semanticweb.org/semi-mes/ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

semi:Wafer a owl:Class ; rdfs:label "晶圆(Wafer)" .
semi:Material a owl:Class ; rdfs:label "物料" .
semi:Equipment a owl:Class ; rdfs:label "设备(Equipment)" .
semi:ProcessStation a owl:Class ; rdfs:label "工站(ProcessStation)" .
semi:belongsToLot a owl:ObjectProperty ; rdfs:domain semi:Wafer ; rdfs:range semi:ProductionLot .
semi:ProductionLot a owl:Class ; rdfs:label "批次(ProductionLot)" .
""", encoding="utf-8")

    if mapping_src.exists():
        shutil.copy(mapping_src, mapping_dst)
    else:
        mapping_dst.write_text(json.dumps({
            "version": "test",
            "object_mappings": [
                {
                    "logic_class": "semi:Wafer",
                    "physical_table": "wafers",
                    "primary_key": "id",
                    "label_cn": "晶圆",
                    "key_columns": ["id", "wafer_code"],
                    "properties": {}
                }
            ],
            "relation_mappings": [],
            "value_mappings": {},
            "business_rules": [],
            "metric_definitions": {}
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    # Monkeypatch 路径
    import app.ontology.config as cfg
    original_ttl = cfg.DEFAULT_TTL_PATH
    original_data_dir = cfg.ONTOLOGY_DATA_DIR
    cfg.DEFAULT_TTL_PATH = ttl_dst
    cfg.ONTOLOGY_DATA_DIR = tmp_path

    yield tmp_path, ttl_dst, mapping_dst

    # 恢复
    cfg.DEFAULT_TTL_PATH = original_ttl
    cfg.ONTOLOGY_DATA_DIR = original_data_dir


def _make_skill(mapping_file: Path):
    from app.ontology.skill import OntologyBuilderSkill
    return OntologyBuilderSkill(mapping_file=mapping_file)


# ══════════════════════════════════════════════════════════════════
# 1. 基础加载 & 诊断
# ══════════════════════════════════════════════════════════════════

class TestLoadAndDiagnose:
    def test_load(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        skill = _make_skill(mapping)
        skill.load()
        assert skill._loaded

    def test_diagnose(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        skill = _make_skill(mapping).load()
        result = skill.diagnose()
        assert "ttl_classes" in result
        assert "mapping_object_classes" in result
        assert "coverage" in result
        assert result["ttl_classes"] > 0


# ══════════════════════════════════════════════════════════════════
# 2. Preview 校验
# ══════════════════════════════════════════════════════════════════

class TestPreview:
    def test_preview_new_class(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        from app.ontology.skill import ClassSpec, OntologySpec
        spec = OntologySpec(classes=[
            ClassSpec(
                uri="semi:TestNewClass",
                label="测试类(TestNewClass)",
                comment="测试用类",
                parent_uri="semi:Material",
                physical_table="test_new_table",
                primary_key="id",
                label_cn="测试类",
                key_columns=["id", "code"],
            )
        ])
        skill = _make_skill(mapping).load()
        skill.stage(spec)
        result = skill.preview()
        assert len(result.ttl_additions) >= 1 or len(result.ttl_updates) >= 1
        assert len(result.mapping_additions) >= 1 or len(result.mapping_updates) >= 1
        assert not result.has_errors

    def test_preview_error_missing_parent(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        from app.ontology.skill import ClassSpec, OntologySpec
        spec = OntologySpec(classes=[
            ClassSpec(
                uri="semi:OrphanClass",
                label="孤儿类",
                parent_uri="semi:NonExistentParent",
                physical_table="orphan_table",
                primary_key="id",
                label_cn="孤儿",
            )
        ])
        skill = _make_skill(mapping).load()
        skill.stage(spec)
        result = skill.preview()
        assert result.has_errors
        assert any("NonExistentParent" in i.message for i in result.issues)

    def test_preview_error_fk_missing_join_logic(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        from app.ontology.skill import OntologySpec, RelationSpec
        spec = OntologySpec(relations=[
            RelationSpec(
                uri="semi:testBadRelation",
                domain_uri="semi:Wafer",
                range_uri="semi:Equipment",
                strategy="ForeignKey",
                join_logic={},  # Missing required fields
            )
        ])
        skill = _make_skill(mapping).load()
        skill.stage(spec)
        result = skill.preview()
        assert result.has_errors
        assert any("source_table" in i.message for i in result.issues)

    def test_preview_no_spec_staged(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        skill = _make_skill(mapping).load()
        result = skill.preview()
        assert any(i.level == "warning" for i in result.issues)


# ══════════════════════════════════════════════════════════════════
# 3. Commit — 新增类
# ══════════════════════════════════════════════════════════════════

class TestCommitClass:
    def test_add_class_success(self, _setup_test_env):
        _, ttl_path, mapping = _setup_test_env
        from app.ontology.skill import ClassSpec, OntologyBuilderSkill

        skill = OntologyBuilderSkill(mapping_file=mapping)
        result = skill.add_class(ClassSpec(
            uri="semi:TestDevice",
            label="测试设备(TestDevice)",
            comment="用于单元测试的设备类",
            parent_uri="semi:Equipment",
            physical_table="test_devices",
            primary_key="id",
            label_cn="测试设备",
            display_column="device_code",
            key_columns=["id", "device_code", "status"],
            properties={"semi:hasDeviceCode": "device_code"},
        ))

        assert result.success
        assert result.changes_count >= 1

        # 验证 mapping 文件已更新
        with open(mapping, encoding="utf-8") as f:
            data = json.load(f)
        classes = [om["logic_class"] for om in data["object_mappings"]]
        assert "semi:TestDevice" in classes

        # 验证 TTL 文件已更新
        ttl_content = ttl_path.read_text(encoding="utf-8")
        assert "TestDevice" in ttl_content

    def test_add_class_rejects_missing_parent(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        from app.ontology.skill import ClassSpec, OntologyBuilderSkill

        skill = OntologyBuilderSkill(mapping_file=mapping)
        result = skill.add_class(ClassSpec(
            uri="semi:BadClass",
            label="坏类",
            parent_uri="semi:NoSuchParent",
            physical_table="bad_table",
            primary_key="id",
            label_cn="坏类",
        ))
        assert not result.success
        assert "error" in result.message.lower() or "validation" in result.message.lower()


# ══════════════════════════════════════════════════════════════════
# 4. Commit — 新增关系
# ══════════════════════════════════════════════════════════════════

class TestCommitRelation:
    def test_add_relation_success(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        from app.ontology.skill import OntologyBuilderSkill, RelationSpec

        skill = OntologyBuilderSkill(mapping_file=mapping)
        result = skill.add_relation(RelationSpec(
            uri="semi:testNewRel",
            label="测试关系",
            domain_uri="semi:Wafer",
            range_uri="semi:Equipment",
            strategy="ForeignKey",
            description="晶圆关联设备",
            join_logic={
                "source_table": "wafers",
                "source_key": "equipment_id",
                "target_table": "equipment",
                "target_key": "id",
            },
        ))

        assert result.success

        # 验证 mapping 文件
        with open(mapping, encoding="utf-8") as f:
            data = json.load(f)
        rels = [rm["logic_relation"] for rm in data["relation_mappings"]]
        assert "semi:testNewRel" in rels


# ══════════════════════════════════════════════════════════════════
# 5. Commit — 值映射
# ══════════════════════════════════════════════════════════════════

class TestCommitValueMapping:
    def test_add_value_mapping_success(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        from app.ontology.skill import OntologyBuilderSkill, ValueMappingSpec

        skill = OntologyBuilderSkill(mapping_file=mapping)
        result = skill.add_value_mapping(ValueMappingSpec(
            domain="semi:TestStatus",
            semantic_value="Active",
            description="活跃状态",
            physical_condition="status = 1",
            applies_to_table="test_table",
            applies_to_column="status",
        ))

        assert result.success

        with open(mapping, encoding="utf-8") as f:
            data = json.load(f)
        assert "semi:TestStatus" in data["value_mappings"]
        assert "Active" in data["value_mappings"]["semi:TestStatus"]


# ══════════════════════════════════════════════════════════════════
# 6. 批量构建
# ══════════════════════════════════════════════════════════════════

class TestBuildFromSpec:
    def test_build_full_spec(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        from app.ontology.skill import build_from_dict

        spec_dict = {
            "message": "Batch build test",
            "author": "test",
            "classes": [{
                "uri": "semi:BatchTestClass",
                "label": "批量测试类(BatchTestClass)",
                "comment": "批量构建测试",
                "physical_table": "batch_test",
                "primary_key": "id",
                "label_cn": "批量测试",
                "key_columns": ["id"],
            }],
            "relations": [{
                "uri": "semi:batchTestRel",
                "label": "批量测试关系",
                "domain_uri": "semi:BatchTestClass",
                "range_uri": "semi:Wafer",
                "strategy": "ForeignKey",
                "join_logic": {
                    "source_table": "batch_test",
                    "source_key": "wafer_id",
                    "target_table": "wafers",
                    "target_key": "id",
                },
            }],
            "value_mappings": [{
                "domain": "semi:BatchTestStatus",
                "semantic_value": "Done",
                "description": "完成",
                "physical_condition": "status = 'done'",
            }],
        }

        result = build_from_dict(spec_dict, mapping_file=mapping)
        assert result.success
        assert result.changes_count >= 3


# ══════════════════════════════════════════════════════════════════
# 7. 幂等性
# ══════════════════════════════════════════════════════════════════

class TestIdempotency:
    def test_double_commit_idempotent(self, _setup_test_env):
        _, _, mapping = _setup_test_env
        from app.ontology.skill import ClassSpec, OntologyBuilderSkill

        spec = ClassSpec(
            uri="semi:IdempotentClass",
            label="幂等测试类",
            physical_table="idemp_table",
            primary_key="id",
            label_cn="幂等类",
            key_columns=["id"],
        )

        # 第一次
        r1 = OntologyBuilderSkill(mapping_file=mapping).add_class(spec)
        assert r1.success

        # 第二次相同
        r2 = OntologyBuilderSkill(mapping_file=mapping).add_class(spec)
        assert r2.success

        # mapping 中只有一条
        with open(mapping, encoding="utf-8") as f:
            data = json.load(f)
        count = sum(1 for om in data["object_mappings"] if om["logic_class"] == "semi:IdempotentClass")
        assert count == 1


# ══════════════════════════════════════════════════════════════════
# 8. Changelog
# ══════════════════════════════════════════════════════════════════

class TestChangelog:
    def test_changelog_appended(self, _setup_test_env):
        tmp_path, _, mapping = _setup_test_env
        from app.ontology.skill import ClassSpec, OntologyBuilderSkill

        changelog_path = tmp_path / "mapping_changelog.jsonl"

        skill = OntologyBuilderSkill(mapping_file=mapping)
        skill.add_class(ClassSpec(
            uri="semi:ChangelogTest",
            label="日志测试",
            physical_table="changelog_test",
            primary_key="id",
            label_cn="日志测试",
            key_columns=["id"],
        ))

        assert changelog_path.exists()
        lines = changelog_path.read_text(encoding="utf-8").strip().split("\n")
        last_entry = json.loads(lines[-1])
        assert last_entry["action"] == "ontology_skill_commit"
        assert last_entry["details"]["classes_count"] == 1
