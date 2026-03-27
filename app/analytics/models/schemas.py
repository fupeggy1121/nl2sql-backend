"""
Pydantic schemas — 分析 API 请求/响应模型
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── 数据源配置 ──

class DataSourceConfig(BaseModel):
    """数据获取来源配置。"""

    type: str = Field(
        ...,
        description="数据来源类型: sql / table / data",
        pattern=r"^(sql|table|data)$",
    )
    sql: Optional[str] = Field(None, description="SQL 查询语句 (type=sql 时必填)")
    table: Optional[str] = Field(None, description="表名 (type=table 时必填)")
    filters: Optional[Dict[str, Any]] = Field(
        None, description="WHERE 筛选条件 (type=table 时可选)"
    )
    columns: Optional[List[str]] = Field(
        None, description="需要的列名列表 (type=table 时可选)"
    )
    data: Optional[List[Dict[str, Any]]] = Field(
        None, description="行内数据 (type=data 时必填，来自上轮查询结果)"
    )
    limit: Optional[int] = Field(
        None, ge=1, le=100000, description="最大返回行数"
    )


# ── 分析请求 ──

class AnalysisRequest(BaseModel):
    """通用分析请求。"""

    method: str = Field(..., description="分析方法名称 (如 descriptive, spc, anova)")
    data_source: DataSourceConfig = Field(..., description="数据来源配置")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="分析方法参数 (各方法不同)"
    )


class PreviewRequest(BaseModel):
    """数据预览请求。"""

    data_source: DataSourceConfig = Field(..., description="数据来源配置")
    preprocess: bool = Field(False, description="是否执行预处理")


class SPCRequest(BaseModel):
    """SPC 专用请求（高频使用场景简化入参）。"""

    data_source: DataSourceConfig = Field(..., description="数据来源配置")
    value_column: str = Field(..., description="数值列名 (量测值列)")
    group_column: Optional[str] = Field(None, description="分组列名 (子组划分)")
    subgroup_size: int = Field(5, ge=2, le=50, description="子组大小")
    usl: Optional[float] = Field(None, description="规格上限 (计算 Cpk 用)")
    lsl: Optional[float] = Field(None, description="规格下限 (计算 Cpk 用)")


# ── 分析响应 ──

class AnalysisResponse(BaseModel):
    """分析结果响应。"""

    success: bool
    method: str
    summary: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    charts: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class PreviewResponse(BaseModel):
    """数据预览响应。"""

    success: bool
    rows_count: int = 0
    columns: List[str] = Field(default_factory=list)
    dtypes: Dict[str, str] = Field(default_factory=dict)
    sample: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class MethodInfo(BaseModel):
    """分析方法信息。"""

    name: str
    label: str
    description: str
    params_schema: Dict[str, Any] = Field(default_factory=dict)
