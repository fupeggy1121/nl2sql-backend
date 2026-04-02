"""
baselines API — 业务预警基线 CRUD 端点

路由前缀: /api/v1/baselines
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/baselines", tags=["baselines"])


# ------------------------------------------------------------------
# Pydantic 模型
# ------------------------------------------------------------------
class ThresholdItem(BaseModel):
    value: float
    level: str               # "target" | "warning" | "critical"
    label: str
    color: Optional[str] = None


class BaselineIn(BaseModel):
    id: Optional[str] = None
    metric_id: Optional[str] = None
    label: str
    field: str
    keywords: List[str] = Field(default_factory=list)
    scope: Optional[Dict[str, Any]] = None
    thresholds: List[ThresholdItem] = Field(default_factory=list)
    direction: Optional[str] = "below"       # "above" | "below"
    enabled: Optional[bool] = True
    created_by: Optional[str] = "system"


class BaselineUpdate(BaseModel):
    metric_id: Optional[str] = None
    label: Optional[str] = None
    field: Optional[str] = None
    keywords: Optional[List[str]] = None
    scope: Optional[Dict[str, Any]] = None
    thresholds: Optional[List[ThresholdItem]] = None
    direction: Optional[str] = None
    enabled: Optional[bool] = None


# ------------------------------------------------------------------
# 工具
# ------------------------------------------------------------------
def _get_service():
    from app.services.baseline_service import baseline_service
    return baseline_service


def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
    """确保 thresholds 是 list[dict]（从 jsonb 读出时已是 python 对象）"""
    return row


# ------------------------------------------------------------------
# 端点
# ------------------------------------------------------------------
@router.get("", summary="列出所有基线")
async def list_baselines(
    q: str = Query("", description="搜索关键词"),
    enabled_only: bool = Query(False, description="仅返回启用的基线"),
):
    rows = _get_service().list_baselines(q=q, enabled_only=enabled_only)
    return {"items": rows, "total": len(rows)}


@router.post("", summary="创建基线", status_code=201)
async def create_baseline(payload: BaselineIn):
    data = payload.model_dump(exclude_none=False)
    # 将 thresholds 序列化为 list[dict]
    data["thresholds"] = [t.model_dump() for t in payload.thresholds]
    try:
        created = _get_service().create_baseline(data)
        return {"item": _serialize(created)}
    except Exception as e:
        logger.error(f"create_baseline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{baseline_id}", summary="获取单条基线")
async def get_baseline(baseline_id: str):
    item = _get_service().get_baseline(baseline_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"基线 {baseline_id} 不存在")
    return {"item": _serialize(item)}


@router.put("/{baseline_id}", summary="更新基线")
async def update_baseline(baseline_id: str, payload: BaselineUpdate):
    data = payload.model_dump(exclude_none=True)
    if "thresholds" in data and payload.thresholds is not None:
        data["thresholds"] = [t.model_dump() for t in payload.thresholds]
    if not data:
        raise HTTPException(status_code=400, detail="没有可更新的字段")
    try:
        updated = _get_service().update_baseline(baseline_id, data)
        return {"item": _serialize(updated)}
    except Exception as e:
        logger.error(f"update_baseline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{baseline_id}", summary="删除基线", status_code=204)
async def delete_baseline(baseline_id: str):
    ok = _get_service().delete_baseline(baseline_id)
    if not ok:
        raise HTTPException(status_code=500, detail="删除失败")


@router.patch("/{baseline_id}/toggle", summary="切换基线启用状态")
async def toggle_baseline(baseline_id: str):
    try:
        updated = _get_service().toggle_baseline(baseline_id)
        return {"item": _serialize(updated)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"toggle_baseline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
