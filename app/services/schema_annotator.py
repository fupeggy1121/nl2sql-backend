"""
Schema 语义标注服务
用于对数据库 schema 进行 LLM 自动标注和手动审核
"""
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.services.supabase_client import get_supabase_client
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)


class SchemaAnnotator:
    """Schema 语义标注器"""
    
    # Supabase 表名
    SCHEMA_TABLES_TABLE = "schema_table_annotations"
    SCHEMA_COLUMNS_TABLE = "schema_column_annotations"
    SCHEMA_RELATIONS_TABLE = "schema_relation_annotations"
    
    def __init__(self, supabase_client=None):
        """初始化标注器
        
        Args:
            supabase_client: Supabase 客户端实例，如果为 None 则自动获取
        """
        self.supabase = supabase_client or get_supabase_client()
        self.llm = get_llm_provider()
    
    def get_database_schema(self, database_name: str = None) -> Dict[str, Any]:
        """
        从 PostgreSQL 信息模式获取数据库 schema
        
        Args:
            database_name: 数据库名称
            
        Returns:
            Schema 信息字典
        """
        try:
            # 获取所有表
            tables_result = self.supabase.table("information_schema").select(
                "table_name, table_schema"
            ).execute()
            
            schema = {
                "tables": [],
                "relations": []
            }
            
            # 由于 REST API 的限制，我们使用另一种方式
            # 这里需要用 SQL 查询获取完整的 schema
            logger.info("Getting database schema from information_schema")
            
            return schema
        except Exception as e:
            logger.error(f"Failed to get database schema: {str(e)}")
            raise
    
    def get_schema_from_sql(self, sql_query: str = None) -> Dict[str, Any]:
        """
        通过 SQL 查询获取 schema 信息
        适用于 Supabase 的 PostgreSQL
        
        Args:
            sql_query: 自定义 SQL 查询（可选）
            
        Returns:
            Schema 信息
        """
        # 获取所有表和列的完整信息
        query = """
        SELECT 
            t.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.ordinal_position
        FROM information_schema.tables t
        JOIN information_schema.columns c ON t.table_name = c.table_name
        WHERE t.table_schema = 'public'
        ORDER BY t.table_name, c.ordinal_position
        """
        
        try:
            logger.info("Executing schema query")
            # 由于 Supabase SDK 的 REST API 限制，这里返回结构化数据
            # 实际需要使用 SQL query builder 或直接 HTTP 调用
            
            schema = {
                "tables": [],
                "columns_by_table": {},
                "relations": []
            }
            
            logger.info(f"Schema retrieved with {len(schema['tables'])} tables")
            return schema
        except Exception as e:
            logger.error(f"Failed to get schema from SQL: {str(e)}")
            raise
    
    async def auto_annotate_table(self, table_name: str, columns: List[Dict]) -> Dict[str, Any]:
        """
        使用 LLM 自动为表生成标注
        
        Args:
            table_name: 表名
            columns: 列信息列表
            
        Returns:
            自动生成的标注
        """
        columns_info = "\n".join([
            f"- {col['name']} ({col['type']})" 
            for col in columns
        ])
        
        prompt = f"""
请为以下数据库表生成中英文语义标注。

表名: {table_name}
列信息:
{columns_info}

请生成以下信息（JSON 格式）：
{{
    "table_name_cn": "中文表名",
    "table_name_en": "{table_name}",
    "description_cn": "表的中文描述",
    "description_en": "Table description in English",
    "business_meaning": "业务含义说明",
    "use_case": "使用场景",
    "columns": [
        {{
            "column_name": "列名",
            "column_name_cn": "中文列名",
            "data_type": "数据类型",
            "description_cn": "中文描述",
            "description_en": "English description",
            "example_value": "示例值",
            "business_meaning": "业务含义",
            "range": "取值范围（如适用）"
        }}
    ]
}}

请确保输出是有效的 JSON 格式。
"""
        
        try:
            logger.info(f"Generating auto-annotation for table: {table_name}")
            response = await self.llm.generate(prompt)
            
            # 解析 JSON 响应
            annotation = json.loads(response)
            logger.info(f"✅ Auto-annotation generated for {table_name}")
            return annotation
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            return {"error": "Failed to parse LLM response", "raw_response": response}
        except Exception as e:
            logger.error(f"Failed to auto-annotate table: {str(e)}")
            raise
    
    async def save_table_annotation(self, annotation: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存表级标注到数据库
        
        Args:
            annotation: 标注数据
            
        Returns:
            保存结果
        """
        try:
            record = {
                "table_name": annotation.get("table_name_en"),
                "table_name_cn": annotation.get("table_name_cn"),
                "description_cn": annotation.get("description_cn"),
                "description_en": annotation.get("description_en"),
                "business_meaning": annotation.get("business_meaning"),
                "use_case": annotation.get("use_case"),
                "status": "pending",  # pending, approved, rejected
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "created_by": "system",
                "reviewed_by": None
            }
            
            # 使用 Supabase 保存
            result = self.supabase.table(self.SCHEMA_TABLES_TABLE).insert(record).execute()
            
            logger.info(f"✅ Table annotation saved for: {annotation.get('table_name_en')}")
            return result.data[0] if result.data else record
        except Exception as e:
            logger.error(f"Failed to save table annotation: {str(e)}")
            raise
    
    async def save_column_annotations(self, table_name: str, columns: List[Dict]) -> List[Dict]:
        """
        保存列级标注到数据库
        
        Args:
            table_name: 表名
            columns: 列的标注数据列表
            
        Returns:
            保存的记录列表
        """
        try:
            records = []
            for col in columns:
                record = {
                    "table_name": table_name,
                    "column_name": col.get("column_name"),
                    "column_name_cn": col.get("column_name_cn"),
                    "data_type": col.get("data_type"),
                    "description_cn": col.get("description_cn"),
                    "description_en": col.get("description_en"),
                    "example_value": col.get("example_value"),
                    "business_meaning": col.get("business_meaning"),
                    "value_range": col.get("range"),
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "created_by": "system",
                    "reviewed_by": None
                }
                records.append(record)
            
            # 批量插入
            result = self.supabase.table(self.SCHEMA_COLUMNS_TABLE).insert(records).execute()
            
            logger.info(f"✅ {len(records)} column annotations saved for table: {table_name}")
            return result.data if result.data else records
        except Exception as e:
            logger.error(f"Failed to save column annotations: {str(e)}")
            raise
    
    def get_pending_annotations(self, annotation_type: str = "table") -> List[Dict]:
        """
        获取待审核的标注
        
        Args:
            annotation_type: 标注类型 (table, column, relation)
            
        Returns:
            待审核标注列表
        """
        try:
            table_map = {
                "table": self.SCHEMA_TABLES_TABLE,
                "column": self.SCHEMA_COLUMNS_TABLE,
                "relation": self.SCHEMA_RELATIONS_TABLE
            }
            
            table_name = table_map.get(annotation_type, self.SCHEMA_TABLES_TABLE)
            
            result = self.supabase.table(table_name).select("*").eq(
                "status", "pending"
            ).execute()
            
            logger.info(f"Retrieved {len(result.data)} pending {annotation_type} annotations")
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Failed to get pending annotations: {str(e)}")
            return []
    
    def approve_annotation(
        self, 
        annotation_id: str, 
        annotation_type: str = "table",
        reviewer: str = "admin"
    ) -> Dict[str, Any]:
        """
        审核通过标注
        
        Args:
            annotation_id: 标注 ID
            annotation_type: 标注类型
            reviewer: 审核人
            
        Returns:
            更新结果
        """
        try:
            table_map = {
                "table": self.SCHEMA_TABLES_TABLE,
                "column": self.SCHEMA_COLUMNS_TABLE,
                "relation": self.SCHEMA_RELATIONS_TABLE
            }
            
            table_name = table_map.get(annotation_type, self.SCHEMA_TABLES_TABLE)
            
            result = self.supabase.table(table_name).update({
                "status": "approved",
                "reviewed_by": reviewer,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", annotation_id).execute()
            
            logger.info(f"✅ Annotation {annotation_id} approved by {reviewer}")
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Failed to approve annotation: {str(e)}")
            raise
    
    def reject_annotation(
        self,
        annotation_id: str,
        annotation_type: str = "table",
        reason: str = "",
        reviewer: str = "admin"
    ) -> Dict[str, Any]:
        """
        拒绝标注并要求修改
        
        Args:
            annotation_id: 标注 ID
            annotation_type: 标注类型
            reason: 拒绝原因
            reviewer: 审核人
            
        Returns:
            更新结果
        """
        try:
            table_map = {
                "table": self.SCHEMA_TABLES_TABLE,
                "column": self.SCHEMA_COLUMNS_TABLE,
                "relation": self.SCHEMA_RELATIONS_TABLE
            }
            
            table_name = table_map.get(annotation_type, self.SCHEMA_TABLES_TABLE)
            
            result = self.supabase.table(table_name).update({
                "status": "rejected",
                "reviewed_by": reviewer,
                "rejection_reason": reason,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", annotation_id).execute()
            
            logger.info(f"✅ Annotation {annotation_id} rejected by {reviewer}")
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Failed to reject annotation: {str(e)}")
            raise
    
    def update_annotation(
        self,
        annotation_id: str,
        annotation_type: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        更新标注内容（手动审核/编辑）
        
        Args:
            annotation_id: 标注 ID
            annotation_type: 标注类型
            updates: 更新的字段
            
        Returns:
            更新结果
        """
        try:
            table_map = {
                "table": self.SCHEMA_TABLES_TABLE,
                "column": self.SCHEMA_COLUMNS_TABLE,
                "relation": self.SCHEMA_RELATIONS_TABLE
            }
            
            table_name = table_map.get(annotation_type, self.SCHEMA_TABLES_TABLE)
            
            updates["updated_at"] = datetime.utcnow().isoformat()
            
            result = self.supabase.table(table_name).update(updates).eq(
                "id", annotation_id
            ).execute()
            
            logger.info(f"✅ Annotation {annotation_id} updated")
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Failed to update annotation: {str(e)}")
            raise
    
    def get_approved_schema_metadata(self) -> Dict[str, Any]:
        """
        获取所有已审核通过的 schema 元数据
        用于改进 NL2SQL 的理解
        
        Returns:
            完整的 schema 元数据
        """
        try:
            # 获取已审核的表标注
            tables_result = self.supabase.table(self.SCHEMA_TABLES_TABLE).select("*").eq(
                "status", "approved"
            ).execute()
            
            # 获取已审核的列标注
            columns_result = self.supabase.table(self.SCHEMA_COLUMNS_TABLE).select("*").eq(
                "status", "approved"
            ).execute()
            
            # 构建元数据结构
            metadata = {
                "tables": {},
                "columns": {},
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # 整理表数据
            for table in tables_result.data or []:
                table_name = table.get("table_name")
                metadata["tables"][table_name] = {
                    "name_cn": table.get("table_name_cn"),
                    "description_cn": table.get("description_cn"),
                    "description_en": table.get("description_en"),
                    "business_meaning": table.get("business_meaning"),
                    "use_case": table.get("use_case")
                }
            
            # 整理列数据
            for column in columns_result.data or []:
                table_name = column.get("table_name")
                column_name = column.get("column_name")
                
                if table_name not in metadata["columns"]:
                    metadata["columns"][table_name] = {}
                
                metadata["columns"][table_name][column_name] = {
                    "name_cn": column.get("column_name_cn"),
                    "data_type": column.get("data_type"),
                    "description_cn": column.get("description_cn"),
                    "description_en": column.get("description_en"),
                    "example": column.get("example_value"),
                    "business_meaning": column.get("business_meaning"),
                    "range": column.get("value_range")
                }
            
            logger.info(f"✅ Schema metadata retrieved: {len(metadata['tables'])} tables, "
                       f"{len(metadata['columns'])} tables with columns")
            return metadata
        except Exception as e:
            logger.error(f"Failed to get approved schema metadata: {str(e)}")
            return {}


# 创建全局实例
schema_annotator = SchemaAnnotator()
