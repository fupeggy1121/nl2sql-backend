"""
模型定义
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class QueryRequest:
    """查询请求模型"""
    natural_language: str
    schema: Optional[Dict[str, Any]] = None

@dataclass
class QueryResponse:
    """查询响应模型"""
    success: bool
    sql: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    count: int = 0

@dataclass
class TableSchema:
    """表 schema 定义"""
    table_name: str
    columns: List[Dict[str, str]]  # 列信息，包含列名和类型
    primary_key: Optional[str] = None
