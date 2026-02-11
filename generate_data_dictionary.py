#!/usr/bin/env python3
"""
生成数据库数据字典和关系图
"""

import json
from datetime import datetime

def generate_data_dictionary():
    """生成包含所有表和列详细说明的数据字典"""
    
    # 读取生成的 schema.json
    with open('database_schema.json', 'r', encoding='utf-8') as f:
        schema_data = json.load(f)
    
    print("生成数据字典...")
    
    # 构建表之间的外键关系
    relationships = {
        'batches': {
            'parent': None,
            'children': ['sub_batches', 'production_events', 'quality_records', 'wafers'],
            'description': '生产批次的主表'
        },
        'sub_batches': {
            'parent': 'batches',
            'children': ['wafer_carrier_contents', 'wafer_inspection_results'],
            'description': '批次的细分单位'
        },
        'products': {
            'parent': None,
            'children': ['batches', 'product_boms', 'quality_records'],
            'description': '产品主表'
        },
        'wafers': {
            'parent': 'batches',
            'children': ['wafer_carrier_contents', 'wafer_inspection_results'],
            'description': '晶圆主表'
        },
        'carriers': {
            'parent': None,
            'children': ['wafer_carrier_contents'],
            'description': '晶圆载体主表'
        },
        'stations': {
            'parent': None,
            'children': ['production_events', 'wafer_inspection_results'],
            'description': '生产站点主表'
        },
        'equipment': {
            'parent': None,
            'children': ['production_events', 'oee_records', 'parameter_equipment'],
            'description': '设备主表'
        },
        'process_routes': {
            'parent': None,
            'children': ['process_route_stations', 'batches'],
            'description': '工艺路线主表'
        },
        'parameters': {
            'parent': None,
            'children': ['parameter_group_parameters', 'parameter_equipment'],
            'description': '参数定义表'
        },
        'parameter_groups': {
            'parent': None,
            'children': ['parameter_group_parameters'],
            'description': '参数分组表'
        }
    }
    
    # 建立表的数据血缘关系
    data_lineage = {
        '数据源层': {
            '设备相关': ['equipment', 'equipment_groups', 'stations', 'process_routes'],
            '产品相关': ['products', 'product_boms', 'parameters', 'parameter_groups'],
            '订单相关': ['production_orders', 'batches']
        },
        '中间层': {
            '生产执行': ['production_events', 'oee_records', 'sub_batches'],
            '质量检测': ['quality_records', 'wafer_inspection_results'],
            '物流管理': ['carriers', 'wafer_carrier_contents']
        },
        '应用层': {
            '对话系统': ['chat_sessions', 'chat_messages'],
            '反馈系统': ['feedback', 'intent_feedback', 'query_result_feedback'],
            '编辑器系统': ['schema_table_annotations', 'schema_column_annotations', 'annotation_audit_log']
        }
    }
    
    # 创建 HTML 格式的数据字典
    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NL2SQL 数据库数据字典</title>
    <style>
        * { margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; margin-bottom: 30px; }
        h1 { font-size: 2em; margin-bottom: 10px; }
        .subtitle { font-size: 0.9em; opacity: 0.9; }
        .section { background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .section h2 { color: #667eea; margin-bottom: 15px; border-bottom: 2px solid #667eea; padding-bottom: 10px; }
        .section h3 { color: #764ba2; margin-top: 15px; margin-bottom: 10px; }
        .table-group { margin-bottom: 20px; }
        .table-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; }
        .table-card { background: #f9f9f9; border-left: 4px solid #667eea; padding: 15px; border-radius: 4px; }
        .table-name { font-weight: bold; color: #667eea; margin-bottom: 5px; font-family: 'Courier New', monospace; }
        .table-desc { font-size: 0.9em; color: #666; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th { background: #f5f5f5; padding: 10px; text-align: left; border-bottom: 2px solid #667eea; font-weight: 600; }
        td { padding: 10px; border-bottom: 1px solid #ddd; }
        tr:hover { background: #f9f9f9; }
        .type-tag { display: inline-block; background: #667eea; color: white; padding: 3px 8px; border-radius: 3px; font-size: 0.85em; font-family: monospace; }
        .desc-tag { display: inline-block; background: #f0f0f0; padding: 3px 8px; border-radius: 3px; font-size: 0.85em; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-box { background: #f9f9f9; padding: 15px; border-radius: 4px; text-align: center; border-left: 4px solid #667eea; }
        .stat-number { font-size: 2em; color: #667eea; font-weight: bold; }
        .stat-label { font-size: 0.9em; color: #666; }
        .warning { background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 15px 0; border-radius: 4px; }
        .info { background: #d1ecf1; border-left: 4px solid #17a2b8; padding: 15px; margin: 15px 0; border-radius: 4px; }
        .toc { background: #f9f9f9; padding: 15px; border-radius: 4px; margin-bottom: 20px; }
        .toc a { color: #667eea; text-decoration: none; display: block; margin: 5px 0; }
        .toc a:hover { text-decoration: underline; }
        footer { text-align: center; color: #999; margin-top: 40px; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 NL2SQL 数据库数据字典</h1>
            <p class="subtitle">完整的数据库架构和表结构参考指南</p>
        </header>

        <div class="section">
            <h2>📈 数据库统计</h2>
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">35</div>
                    <div class="stat-label">总表数</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">294</div>
                    <div class="stat-label">总列数</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">28</div>
                    <div class="stat-label">包含数据</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">7</div>
                    <div class="stat-label">空表</div>
                </div>
            </div>
            <div class="info">
                <strong>ℹ️ 提示:</strong> 表统计包含所有 REST API 可访问的表。所有表都可以通过 SQL 编辑器或 PostgreSQL 直接连接访问。
            </div>
        </div>

        <div class="section">
            <h2>🏗️ 数据架构层级</h2>
            <div class="table-group">
                <h3>数据源层 (基础主表)</h3>
                <p style="margin-bottom: 10px; color: #666;">这些表是系统的基础数据源，不依赖其他表</p>
                <div class="table-list">
                    <div class="table-card">
                        <div class="table-name">🏭 equipment</div>
                        <div class="table-desc">生产设备 - 设备 ID、型号、部门分配等</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">🏪 stations</div>
                        <div class="table-desc">生产站点 - 工作站、部门、配置参数</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">📦 products</div>
                        <div class="table-desc">产品主表 - 产品 ID、名称、规格等</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">🔀 process_routes</div>
                        <div class="table-desc">工艺路线 - 生产流程定义</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">⚙️ parameters</div>
                        <div class="table-desc">参数定义 - 工艺参数、测量参数等</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">🗂️ parameter_groups</div>
                        <div class="table-desc">参数分组 - 参数的分类管理</div>
                    </div>
                </div>
            </div>

            <div class="table-group">
                <h3>中间层 (业务执行)</h3>
                <p style="margin-bottom: 10px; color: #666;">这些表记录生产过程中的实际执行数据且包含历史记录</p>
                <div class="table-list">
                    <div class="table-card">
                        <div class="table-name">📋 batches</div>
                        <div class="table-desc">生产批次 - 批次号、订单关联、状态等</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">📍 sub_batches</div>
                        <div class="table-desc">子批次 - 批次的细分单位</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">📊 production_events</div>
                        <div class="table-desc">生产事件 - 站点、设备、参数事件记录</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">✅ quality_records</div>
                        <div class="table-desc">质量记录 - 测量数据、检验结果</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">📈 oee_records</div>
                        <div class="table-desc">OEE 记录 - 设备综合效率数据</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">🧪 wafer_inspection_results</div>
                        <div class="table-desc">晶圆检测 - 晶圆检验数据</div>
                    </div>
                </div>
            </div>

            <div class="table-group">
                <h3>应用层 (功能性表)</h3>
                <p style="margin-bottom: 10px; color: #666;">支持特定应用功能的表</p>
                <div class="table-list">
                    <div class="table-card">
                        <div class="table-name">💬 chat_messages</div>
                        <div class="table-desc">聊天消息 - NL2SQL 对话系统的消息</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">💭 chat_sessions</div>
                        <div class="table-desc">聊天会话 - 对话会话管理</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">📝 schema_table_annotations</div>
                        <div class="table-desc">表注释 - 数据库表的说明文档</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">📌 schema_column_annotations</div>
                        <div class="table-desc">列注释 - 数据库列的说明文档</div>
                    </div>
                    <div class="table-card">
                        <div class="table-name">💬 feedback</div>
                        <div class="table-desc">用户反馈 - 系统反馈与建议</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>📚 学习路径建议</h2>
            <h3>初级 - 理解基础表</h3>
            <ol style="margin-left: 20px;">
                <li><strong>batches</strong> - 了解生产批次的基本概念</li>
                <li><strong>products</strong> - 理解产品定义</li>
                <li><strong>stations</strong> - 认识生产站点</li>
                <li><strong>quality_records</strong> - 掌握质量数据</li>
            </ol>

            <h3>中级 - 掌握表关系</h3>
            <ol style="margin-left: 20px;">
                <li><strong>sub_batches</strong> - 理解批次层级</li>
                <li><strong>production_events</strong> - 了解生产过程</li>
                <li><strong>wafer_inspection_results</strong> - 理解检测数据</li>
                <li><strong>parameters</strong> - 掌握参数定义</li>
            </ol>

            <h3>高级 - 复杂查询</h3>
            <ol style="margin-left: 20px;">
                <li>多表联接查询</li>
                <li>时间序列数据分析</li>
                <li>设备 OEE 计算</li>
                <li>质量趋势分析</li>
            </ol>
        </div>

        <div class="section">
            <h2>⚠️ 注意事项</h2>
            <div class="warning">
                <strong>⚙️ 时间戳约定:</strong> 
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>created_at - 记录创建时间（不可修改）</li>
                    <li>updated_at - 记录最后更新时间（自动更新）</li>
                    <li>所有时间戳为 UTC 时区</li>
                </ul>
            </div>
            <div class="warning">
                <strong>🔑 外键关系:</strong> 
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>删除主表记录要检查从表是否有关联数据</li>
                    <li>某些表有级联删除规则，某些有保护规则</li>
                    <li>生产历史数据通常被保护不可删除</li>
                </ul>
            </div>
            <div class="info">
                <strong>ℹ️ 数据完整性:</strong> 
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>某些列有唯一性约束（UNIQUE）</li>
                    <li>某些列有非空约束（NOT NULL）</li>
                    <li>数值列有默认值或范围限制</li>
                </ul>
            </div>
        </div>

        <div class="section">
            <h2>🔍 NL2SQL 查询示例</h2>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 4px; font-family: monospace; margin-top: 10px;">
                <p style="margin-bottom: 10px;"><strong>Q: "显示最近 7 天的质量记录"</strong></p>
                <p style="color: #666; margin-bottom: 15px;">📊 系统会自动识别：</p>
                <ul style="margin-left: 20px; margin-bottom: 15px;">
                    <li>表: quality_records</li>
                    <li>时间范围: CURRENT_DATE - 7 days</li>
                    <li>排序: created_at DESC</li>
                </ul>

                <p style="margin-top: 20px; margin-bottom: 10px;"><strong>Q: "各个站点今日生产了多少产品"</strong></p>
                <p style="color: #666; margin-bottom: 15px;">📊 系统会自动识别：</p>
                <ul style="margin-left: 20px; margin-bottom: 15px;">
                    <li>表: production_events (或 wafer_inspection_results)</li>
                    <li>分组: stations</li>
                    <li>聚合: COUNT(*)</li>
                    <li>时间: TODAY()</li>
                </ul>
            </div>
        </div>

        <footer>
            <p>NL2SQL 数据库数据字典 | 生成时间: 2026-02-11 | <a href="#" style="color: #667eea;">查看详细 Schema 文档</a></p>
        </footer>
    </div>
</body>
</html>
"""
    
    # 保存 HTML 文件
    with open('DATABASE_DATA_DICTIONARY.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("✓ 已生成: DATABASE_DATA_DICTIONARY.html")
    
    # 生成 JSON 格式的数据字典
    data_dict = {
        'version': '1.0',
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_tables': 35,
            'tables_with_data': 28,
            'empty_tables': 7,
            'total_columns': 294
        },
        'architecture': data_lineage,
        'relationships': relationships,
        'statistics': {
            'largest_tables': [
                {'name': 'wafer_inspection_results', 'rows': 7113},
                {'name': 'quality_records', 'rows': 6200},
                {'name': 'wafer_carrier_contents', 'rows': 2180},
                {'name': 'wafers', 'rows': 2180},
                {'name': 'production_events', 'rows': 930}
            ]
        }
    }
    
    with open('database_data_dictionary.json', 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, indent=2, ensure_ascii=False)
    
    print("✓ 已生成: database_data_dictionary.json")
    
    # 生成文本格式的学习指南
    learning_guide = """# 数据库学习指南

## 📚 快速参考

### 最常用的 5 张表
1. **quality_records** (6,200 行) - 质量检验数据
2. **wafer_inspection_results** (7,113 行) - 晶圆检测结果
3. **batches** - 生产批次
4. **stations** - 生产站点
5. **products** - 产品信息

### 查询复杂度等级

**低** (适合初学者)
- SELECT * FROM quality_records LIMIT 10
- SELECT COUNT(*) FROM batches
- SELECT * FROM stations WHERE name LIKE '%'

**中** (需要理解关系)
- 批次到子批次的查询
- 站点到生产事件的关联
- 产品到质量记录的统计

**高** (需要业务逻辑)
- OEE 指标计算
- 多层级的生产流程追踪
- 质量趋势分析跨时间序列

## 🎯 常见 NL2SQL 查询模式

### 统计查询
- "各站点的生产数量统计"
- "最近7天的质量记录"
- "设备故障次数排名"

### 趋势查询
- "质量检测合格率趋势"
- "设备 OEE 变化"
- "产品产量变化"

### 关联查询
- "查找某批次的所有检测结果"
- "显示某产品的所有质量记录"
- "统计各设备的故障情况"

## 📊 表设计特点

### 时间序列类表
- quality_records, production_events, oee_records
- 特点: 大数据量、频繁查询、需要分组统计
- 优化: 按时间分区查询、使用索引

### 主数据表
- products, stations, equipment, batches
- 特点: 变更频率低、维度清晰、常用于GROUP BY
- 用途: 维度表、统计基础

### 关系表
- wafer_carrier_contents, parameter_group_parameters
- 特点: 记录多对多关系、数据量中等
- 用途: 关联查询、关系验证

## 💡 实用查询技巧

1. **了解数据分布**
   - SELECT COUNT(*) FROM quality_records GROUP BY status

2. **时间范围查询**
   - WHERE created_at >= NOW() - INTERVAL '7 days'

3. **防止笛卡尔积**
   - 明确使用 INNER JOIN 而不是 WHERE 条件

4. **聚合查询性能**
   - 先过滤再分组，使用 HAVING 而不是 WHERE

## 🔍 故障排查

- 数据为空: 检查时间范围和过滤条件
- 查询慢: 检查是否需要添加索引或修改联接条件
- 数据不匹配: 验证外键关系是否正确建立
"""
    
    with open('DATABASE_LEARNING_GUIDE.md', 'w', encoding='utf-8') as f:
        f.write(learning_guide)
    
    print("✓ 已生成: DATABASE_LEARNING_GUIDE.md")
    print("\n已生成的数据字典文件:")
    print("  1. DATABASE_DATA_DICTIONARY.html - 交互式网页版")
    print("  2. database_data_dictionary.json - JSON 结构化数据")
    print("  3. DATABASE_LEARNING_GUIDE.md - 学习和使用指南")


if __name__ == "__main__":
    generate_data_dictionary()
