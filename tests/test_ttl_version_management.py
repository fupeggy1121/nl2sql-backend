"""
TTL 版本管理 API 测试

覆盖：
  1. GET  /api/v1/ontology/ttl           — 获取当前 TTL
  2. POST /api/v1/ontology/ttl/upload    — 上传新 TTL
  3. GET  /api/v1/ontology/ttl/versions  — 版本历史列表
  4. GET  /api/v1/ontology/ttl/versions/{v} — 获取历史版本内容
  5. POST /api/v1/ontology/ttl/rollback/{v} — 回滚
  6. GET  /api/v1/ontology/ttl/diff      — 版本对比
  7. version_manager 单元测试
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ── 准备独立的临时数据目录，避免污染真实数据 ──

TEMP_DIR = None
TEMP_DATA_DIR = None
TEMP_VERSIONS_DIR = None

SAMPLE_TTL = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix semi: <http://www.semanticweb.org/semi-mes/ontology#> .

semi:TestOntology a owl:Ontology .
semi:Equipment a owl:Class ;
    rdfs:label "Equipment"@en, "设备"@zh .
semi:Wafer a owl:Class ;
    rdfs:label "Wafer"@en, "晶圆"@zh .
"""

SAMPLE_TTL_V2 = """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix semi: <http://www.semanticweb.org/semi-mes/ontology#> .

semi:TestOntology a owl:Ontology .
semi:Equipment a owl:Class ;
    rdfs:label "Equipment"@en, "设备"@zh .
semi:Wafer a owl:Class ;
    rdfs:label "Wafer"@en, "晶圆"@zh .
semi:Station a owl:Class ;
    rdfs:label "Station"@en, "站点"@zh .
"""


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path):
    """为每个测试创建隔离的数据目录"""
    data_dir = tmp_path / "ontology" / "data"
    data_dir.mkdir(parents=True)
    versions_dir = data_dir / "versions"
    versions_dir.mkdir()

    # 写入初始 TTL
    ttl_path = data_dir / "semi-cim-ontology.ttl"
    ttl_path.write_text(SAMPLE_TTL, encoding="utf-8")

    # 复制 mapping JSON（从真实数据目录）
    real_mapping = Path(__file__).parent.parent / "app" / "ontology" / "data" / "mapping_demo_fab.json"
    if real_mapping.exists():
        shutil.copy(real_mapping, data_dir / "mapping_demo_fab.json")

    with patch("app.ontology.config.ONTOLOGY_DATA_DIR", data_dir), \
         patch("app.ontology.config.DEFAULT_TTL_PATH", ttl_path), \
         patch("app.ontology.version_manager.ONTOLOGY_DATA_DIR", data_dir), \
         patch("app.ontology.version_manager.DEFAULT_TTL_PATH", ttl_path), \
         patch("app.ontology.version_manager.VERSIONS_DIR", versions_dir), \
         patch("app.ontology.version_manager.VERSION_INDEX_FILE", versions_dir / "index.json"), \
         patch("app.ontology.loader._cached_graph", None), \
         patch("app.ontology.mapping._cached_mapping", None):
        yield {
            "data_dir": data_dir,
            "ttl_path": ttl_path,
            "versions_dir": versions_dir,
        }


@pytest.fixture
def client():
    """TestClient with isolated data"""
    from app.main import create_fastapi_app
    app = create_fastapi_app()
    return TestClient(app)


# ═══════════════════════════════════════════════
# Part A: version_manager 单元测试
# ═══════════════════════════════════════════════

class TestVersionManager:
    """版本管理器核心逻辑"""

    def test_get_current_ttl(self, isolated_data_dir):
        from app.ontology.version_manager import get_current_ttl
        content = get_current_ttl()
        assert "semi:Equipment" in content
        assert "owl:Ontology" in content

    def test_list_versions_empty(self, isolated_data_dir):
        from app.ontology.version_manager import list_versions
        versions = list_versions()
        assert versions == []

    def test_save_new_version(self, isolated_data_dir):
        from app.ontology.version_manager import save_new_version, list_versions
        entry = save_new_version(SAMPLE_TTL_V2, message="Add Station class", author="test")
        # 首次上传：v1 = auto-snapshot, v2 = 新上传
        assert entry["version"] == 2
        assert entry["author"] == "test"
        assert "Station" in entry["message"] or entry["message"] == "Add Station class"

        versions = list_versions()
        assert len(versions) == 2
        assert versions[0]["version"] == 2  # 最新在前
        assert versions[1]["version"] == 1  # 自动快照

    def test_get_version_content(self, isolated_data_dir):
        from app.ontology.version_manager import save_new_version, get_version_content
        save_new_version(SAMPLE_TTL_V2, message="v2")
        # v1 是原始快照
        v1_content = get_version_content(1)
        assert "semi:Equipment" in v1_content
        assert "semi:Station" not in v1_content
        # v2 是新上传
        v2_content = get_version_content(2)
        assert "semi:Station" in v2_content

    def test_rollback(self, isolated_data_dir):
        from app.ontology.version_manager import (
            save_new_version, rollback_to_version, get_current_ttl, list_versions,
        )
        save_new_version(SAMPLE_TTL_V2, message="v2 with Station")
        rollback_entry = rollback_to_version(1)
        assert rollback_entry["version"] == 3  # rollback creates v3
        assert "Rollback" in rollback_entry["message"]

        # 当前文件应该恢复为 v1 内容
        current = get_current_ttl()
        assert "semi:Station" not in current
        assert "semi:Equipment" in current

        versions = list_versions()
        assert len(versions) == 3

    def test_diff_versions(self, isolated_data_dir):
        from app.ontology.version_manager import save_new_version, diff_versions
        save_new_version(SAMPLE_TTL_V2, message="v2")
        diff = diff_versions(1, 2)
        assert diff["v1"] == 1
        assert diff["v2"] == 2
        assert diff["added"] > 0  # v2 多了 Station 相关行
        assert diff["v1_lines"] < diff["v2_lines"]

    def test_rollback_nonexistent_version(self, isolated_data_dir):
        from app.ontology.version_manager import rollback_to_version
        with pytest.raises(ValueError, match="not found"):
            rollback_to_version(999)


# ═══════════════════════════════════════════════
# Part B: API 端点测试
# ═══════════════════════════════════════════════

class TestTTLApiEndpoints:
    """TTL 版本管理 API 端点"""

    def test_get_ttl(self, client, isolated_data_dir):
        resp = client.get("/api/v1/ontology/ttl")
        assert resp.status_code == 200
        assert "semi:Equipment" in resp.text
        assert "text/turtle" in resp.headers.get("content-type", "")

    def test_upload_ttl(self, client, isolated_data_dir):
        resp = client.post(
            "/api/v1/ontology/ttl/upload",
            files={"file": ("test.ttl", SAMPLE_TTL_V2.encode(), "text/turtle")},
            data={"message": "Add Station", "author": "test-user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["version"]["version"] == 2

    def test_upload_invalid_extension(self, client, isolated_data_dir):
        resp = client.post(
            "/api/v1/ontology/ttl/upload",
            files={"file": ("bad.json", b'{"foo": 1}', "application/json")},
            data={"message": "bad"},
        )
        assert resp.status_code == 400

    def test_upload_invalid_content(self, client, isolated_data_dir):
        resp = client.post(
            "/api/v1/ontology/ttl/upload",
            files={"file": ("bad.ttl", b"this is not valid TTL at all", "text/turtle")},
            data={"message": "bad content"},
        )
        assert resp.status_code == 400

    def test_versions_empty(self, client, isolated_data_dir):
        resp = client.get("/api/v1/ontology/ttl/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_versions_after_upload(self, client, isolated_data_dir):
        client.post(
            "/api/v1/ontology/ttl/upload",
            files={"file": ("v2.ttl", SAMPLE_TTL_V2.encode(), "text/turtle")},
            data={"message": "v2"},
        )
        resp = client.get("/api/v1/ontology/ttl/versions")
        data = resp.json()
        assert data["total"] == 2  # v1 auto-snapshot + v2

    def test_get_version_content_api(self, client, isolated_data_dir):
        client.post(
            "/api/v1/ontology/ttl/upload",
            files={"file": ("v2.ttl", SAMPLE_TTL_V2.encode(), "text/turtle")},
            data={"message": "v2"},
        )
        resp = client.get("/api/v1/ontology/ttl/versions/1")
        assert resp.status_code == 200
        data = resp.json()
        assert "semi:Equipment" in data["content"]
        assert data["version"]["version"] == 1

    def test_get_version_not_found(self, client, isolated_data_dir):
        resp = client.get("/api/v1/ontology/ttl/versions/999")
        assert resp.status_code == 404

    def test_rollback_api(self, client, isolated_data_dir):
        # Upload v2
        client.post(
            "/api/v1/ontology/ttl/upload",
            files={"file": ("v2.ttl", SAMPLE_TTL_V2.encode(), "text/turtle")},
            data={"message": "v2"},
        )
        # Rollback to v1
        resp = client.post("/api/v1/ontology/ttl/rollback/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["version"]["version"] == 3

        # Verify current TTL is v1 content
        resp = client.get("/api/v1/ontology/ttl")
        assert "semi:Station" not in resp.text

    def test_rollback_not_found(self, client, isolated_data_dir):
        resp = client.post("/api/v1/ontology/ttl/rollback/999")
        assert resp.status_code == 404

    def test_diff_api(self, client, isolated_data_dir):
        client.post(
            "/api/v1/ontology/ttl/upload",
            files={"file": ("v2.ttl", SAMPLE_TTL_V2.encode(), "text/turtle")},
            data={"message": "v2"},
        )
        resp = client.get("/api/v1/ontology/ttl/diff?v1=1&v2=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["v1"] == 1
        assert data["v2"] == 2
        assert data["added"] > 0

    def test_viewer_page(self, client, isolated_data_dir):
        resp = client.get("/viewer")
        assert resp.status_code == 200
        assert "Ontology Viewer" in resp.text
