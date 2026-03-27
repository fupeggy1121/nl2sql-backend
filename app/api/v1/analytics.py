"""
POST /api/v1/analytics/* — 数据分析 API 端点

API 直接调用模式 — 前端按钮触发分析，无需经过 Agent 管道。
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from app.analytics.data_source import load_dataframe
from app.analytics.engine import AnalysisEngine
from app.analytics.models.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    MethodInfo,
    PreviewRequest,
    PreviewResponse,
)
from app.analytics.preprocessing.pipeline import auto_preprocess

# 确保方法注册 (触发 @register_method 装饰器)
import app.analytics.methods  # noqa: F401

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["Data Analytics"])


# ── 分析方法列表 ──

@router.get("/methods", response_model=list[MethodInfo])
async def list_methods():
    """列出所有可用的分析方法及参数说明。"""
    methods = AnalysisEngine.list_available_methods()
    return [MethodInfo(**m) for m in methods]


# ── 数据预览 ──

@router.post("/preview", response_model=PreviewResponse)
async def preview_data(req: PreviewRequest):
    """
    加载数据源并返回预览信息（列名、类型、样本行）。
    可选执行预处理 (preprocess=true)。
    """
    try:
        df = load_dataframe(req.data_source.model_dump())

        if req.preprocess and not df.empty:
            df, _ = auto_preprocess(df)

        sample = df.head(20).to_dict(orient="records") if not df.empty else []
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}

        return PreviewResponse(
            success=True,
            rows_count=len(df),
            columns=df.columns.tolist(),
            dtypes=dtypes,
            sample=_sanitize_records(sample),
        )
    except Exception as e:
        logger.error(f"[analytics/preview] error: {e}", exc_info=True)
        return PreviewResponse(success=False, error=str(e))


# ── 通用分析入口 ──

@router.post("/run", response_model=AnalysisResponse)
async def run_analysis(req: AnalysisRequest):
    """
    执行指定分析方法。

    1. 加载数据源 → DataFrame
    2. 调用 AnalysisEngine.run(method, df, params)
    3. 返回分析结果（统计量 + Plotly 图表 JSON）
    """
    try:
        df = load_dataframe(req.data_source.model_dump())

        if df.empty:
            return AnalysisResponse(
                success=False, method=req.method, error="数据为空"
            )

        result = AnalysisEngine.run(req.method, df, req.params)

        return AnalysisResponse(
            success=result.success,
            method=result.method,
            summary=result.summary,
            data=result.data,
            charts=result.charts,
            metadata=result.metadata,
            error=result.error,
        )
    except Exception as e:
        logger.error(f"[analytics/run] error: {e}", exc_info=True)
        return AnalysisResponse(
            success=False, method=req.method, error=str(e)
        )


def _sanitize_records(records: list[dict]) -> list[dict]:
    """清理 DataFrame 记录，确保 JSON 可序列化。"""
    import math

    clean = []
    for row in records:
        clean_row = {}
        for k, v in row.items():
            if v is None:
                clean_row[k] = None
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean_row[k] = None
            else:
                clean_row[k] = v
        clean.append(clean_row)
    return clean
