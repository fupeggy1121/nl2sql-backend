"""
数据源管理 API — 数据源 CRUD 端点

路由前缀: /api/v1/data-sources
"""
import logging
from typing import Optional

import pymysql
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config.data_sources import DataSourceRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/data-sources", tags=["data-sources"])


# ------------------------------------------------------------------
# Pydantic 模型
# ------------------------------------------------------------------

class DataSourceIn(BaseModel):
    display_name: str = Field(..., description="显示名称")
    host: str = Field(..., description="数据库主机")
    port: int = Field(3306, description="端口")
    db: str = Field(..., description="数据库名")
    user: str = Field(..., description="用户名")
    password: str = Field("", description="密码")
    description: str = Field("", description="备注说明")
    read_timeout: int = Field(45, description="查询超时(秒)")


class DataSourceUpdate(BaseModel):
    display_name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    db: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    description: Optional[str] = None
    read_timeout: Optional[int] = None


# ------------------------------------------------------------------
# 路由
# ------------------------------------------------------------------

@router.get("")
def list_data_sources():
    """列出所有已配置的数据源（密码脱敏）。"""
    registry = DataSourceRegistry.get_instance()
    return {
        "success": True,
        "default_source_id": registry.default_id,
        "sources": registry.list_all(mask_password=True),
    }


@router.post("")
def create_data_source(source_id: str, body: DataSourceIn):
    """新增数据源。source_id 为路径参数。"""
    source_id = source_id.strip()
    if not source_id:
        raise HTTPException(status_code=400, detail="source_id 不能为空")

    registry = DataSourceRegistry.get_instance()
    if registry.has(source_id):
        raise HTTPException(status_code=409, detail=f"数据源 '{source_id}' 已存在，请使用 PUT 更新")

    cfg = registry.add_or_update(source_id, **body.model_dump())
    return {"success": True, "source": cfg.to_dict(mask_password=True)}


@router.put("/{source_id}")
def update_data_source(source_id: str, body: DataSourceUpdate):
    """更新数据源配置（仅更新传入的字段）。密码为空字符串时不修改密码。"""
    registry = DataSourceRegistry.get_instance()
    if not registry.has(source_id):
        raise HTTPException(status_code=404, detail=f"数据源 '{source_id}' 不存在")

    update_fields = {k: v for k, v in body.model_dump().items() if v is not None}
    # 密码为空字符串时保留原密码
    if "password" in update_fields and update_fields["password"] == "":
        del update_fields["password"]

    cfg = registry.add_or_update(source_id, **update_fields)
    return {"success": True, "source": cfg.to_dict(mask_password=True)}


@router.delete("/{source_id}")
def delete_data_source(source_id: str):
    """删除数据源（不能删除默认数据源）。"""
    registry = DataSourceRegistry.get_instance()
    try:
        registry.remove(source_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"success": True, "deleted": source_id}


@router.put("/{source_id}/default")
def set_default_data_source(source_id: str):
    """将指定数据源设为默认。"""
    registry = DataSourceRegistry.get_instance()
    try:
        registry.set_default(source_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"success": True, "default_source_id": source_id}


@router.post("/{source_id}/test")
def test_data_source_connection(source_id: str):
    """测试数据源连接是否可达。"""
    registry = DataSourceRegistry.get_instance()
    if not registry.has(source_id):
        raise HTTPException(status_code=404, detail=f"数据源 '{source_id}' 不存在")

    cfg = registry.get(source_id)
    kwargs = cfg.to_pymysql_kwargs()
    kwargs["connect_timeout"] = 5  # 测试时使用更短超时

    try:
        conn = pymysql.connect(**kwargs)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return {
            "success": True,
            "source_id": source_id,
            "message": f"连接成功: {cfg.host}:{cfg.port}/{cfg.db}",
        }
    except Exception as e:
        logger.warning("[DataSources] 连接测试失败 source_id=%s: %s", source_id, e)
        return {
            "success": False,
            "source_id": source_id,
            "message": str(e),
        }
