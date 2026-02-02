# 后端意图识别 API - 集成方案分析

## 📊 当前后端架构分析

### 已有的 API 端点

```
POST /api/query/nl-to-sql              ← 自然语言转 SQL
POST /api/query/execute                ← 执行 SQL 查询
POST /api/query/nl-execute             ← NL 直接执行查询
POST /api/query/nl-execute-supabase    ← NL 执行 Supabase 查询
GET  /api/query/health                 ← 健康检查
GET  /api/query/supabase/schema        ← 获取 schema
GET  /api/query/supabase/connection    ← 检查连接状态
```

### 前端方案对比

| 方案 | 位置 | 特点 | 适用场景 |
|------|------|------|---------|
| **前端端处理** | 客户端 TypeScript | 无延迟、实时响应、独立 | 即时 UI 反馈 |
| **后端 API** | 服务器 Python | 集中管理、便于缓存、成本优化 | 完整流程处理 |

---

## 🎯 推荐方案：**双层架构**

### 最优设计（推荐）

```
┌─────────────────────────────────────────────────────────┐
│                      前端应用                             │
│  ┌──────────────────────────────────────────────────┐   │
│  │ UI 组件                                          │   │
│  │  ↓                                               │   │
│  │ 快速反馈（sync）← recognizeIntentSync()          │   │
│  │  ├─ 显示初步意图                                 │   │
│  │  └─ 实时 UI 反应 (< 5ms)                         │   │
│  └──────────────────────────────────────────────────┘   │
│                    ↓                                     │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 调用后端 API（异步）                             │   │
│  │  └─ POST /api/query/recognize-intent             │   │
│  │      返回完整意图 + 澄清 + 推理                   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                   后端服务                               │
│  IntentRecognizer (Python)                              │
│  ├─ 规则引擎                                            │
│  ├─ LLM 引擎 (DeepSeek)                                 │
│  ├─ 实体提取                                            │
│  └─ 澄清生成                                            │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ 答案：YES - 需要创建新的 API 接口

### 原因

1. **集中化管理**
   - 后端集中处理所有 AI 逻辑
   - 减少前端依赖

2. **成本优化**
   - 可在后端缓存结果
   - 减少 LLM API 调用次数
   - 节省 DeepSeek API 成本

3. **流程完整性**
   - 后端已有 NL2SQL 功能
   - 意图识别可作为 NL2SQL 的前置阶段
   - 形成完整的查询处理流程

4. **安全性**
   - API Key 在后端管理
   - 前端无需暴露敏感信息

5. **可维护性**
   - 统一版本管理
   - 便于持续优化

---

## 🏗️ 实现方案

### 步骤 1: 创建 Python 意图识别服务

**文件**: `app/services/intent_recognizer.py`

```python
from typing import Dict, List, Optional
import re
from app.services.llm_provider import LLMProvider
import logging

logger = logging.getLogger(__name__)

class IntentRecognizer:
    """
    MES 系统意图识别服务
    支持规则引擎 + LLM 混合方式
    """
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm_provider = llm_provider
        
        # 意图配置
        self.intents = {
            'direct_query': {
                'keywords': ['返回', '查询', '显示', '获取', '列出', '表'],
                'entities': ['table', 'limit', 'filters']
            },
            'query_production': {
                'keywords': ['产量', '生产', '产出', '完成', '输出'],
                'entities': ['timeRange', 'productLine']
            },
            'query_quality': {
                'keywords': ['良品率', '合格率', '质量', '不良', '缺陷'],
                'entities': ['timeRange', 'metrics', 'defectType']
            },
            'query_equipment': {
                'keywords': ['设备', '稼动率', 'OEE', '故障', '停机'],
                'entities': ['timeRange', 'equipment']
            },
            'generate_report': {
                'keywords': ['报表', '生成', '导出', '汇总'],
                'entities': ['reportType', 'timeRange']
            },
            'compare_analysis': {
                'keywords': ['对比', '比较', '同比', '分析', '趋势'],
                'entities': ['timeRange', 'metrics']
            }
        }
    
    def recognize(self, user_input: str) -> Dict:
        """
        混合方式识别意图
        1. 规则匹配（快速）
        2. LLM 确认（准确）
        """
        # 第一步：规则匹配
        rule_result = self._rule_based_match(user_input)
        
        if rule_result['confidence'] > 0.8:
            return {
                'success': True,
                'intent': rule_result['intent'],
                'confidence': rule_result['confidence'],
                'entities': rule_result['entities'],
                'methodsUsed': ['rule'],
                'clarifications': self._generate_clarifications(
                    rule_result['intent'],
                    rule_result['entities'],
                    rule_result['confidence']
                )
            }
        
        # 第二步：LLM 确认
        llm_result = self._llm_based_match(user_input)
        
        # 合并结果
        merged = self._merge_results(rule_result, llm_result)
        
        return {
            'success': True,
            'intent': merged['intent'],
            'confidence': merged['confidence'],
            'entities': merged['entities'],
            'methodsUsed': merged['methodsUsed'],
            'clarifications': self._generate_clarifications(
                merged['intent'],
                merged['entities'],
                merged['confidence']
            ),
            'reasoning': llm_result.get('reasoning')
        }
    
    def _rule_based_match(self, text: str) -> Dict:
        """基于关键词的快速匹配"""
        scores = {}
        
        for intent_name, config in self.intents.items():
            score = 0
            for keyword in config['keywords']:
                if keyword in text:
                    score += 1
            
            if score > 0:
                scores[intent_name] = score / len(config['keywords'])
        
        if not scores:
            return {
                'intent': 'other',
                'confidence': 0.0,
                'entities': {}
            }
        
        best_intent = max(scores, key=scores.get)
        return {
            'intent': best_intent,
            'confidence': scores[best_intent],
            'entities': self._extract_entities(text, best_intent)
        }
    
    def _llm_based_match(self, text: str) -> Dict:
        """使用 DeepSeek 进行意图识别"""
        if not self.llm_provider:
            return {'intent': 'other', 'confidence': 0.0, 'entities': {}}
        
        prompt = f"""分析用户在 MES 系统中的意图。

可能的意图类型:
1. direct_query - 直接查询表数据
2. query_production - 查询生产数据
3. query_quality - 查询质量数据
4. query_equipment - 查询设备数据
5. generate_report - 生成报表
6. compare_analysis - 对比分析

用户输入: {text}

请返回 JSON:
{{
    "intent": "意图类型",
    "confidence": 0.95,
    "entities": {{"timeRange": "时间范围"}},
    "reasoning": "判断理由"
}}"""
        
        response = self.llm_provider.generate(prompt)
        
        # 解析 JSON 结果
        import json
        try:
            result = json.loads(response)
            result['reasoning'] = result.get('reasoning', '')
            return result
        except:
            return {'intent': 'other', 'confidence': 0.0, 'entities': {}}
    
    def _extract_entities(self, text: str, intent: str) -> Dict:
        """提取实体信息"""
        entities = {}
        
        # 时间范围提取
        time_patterns = {
            r'今天|今日': 'today',
            r'昨天|昨日': 'yesterday',
            r'本周|这周': 'this_week',
            r'上周|上星期': 'last_week',
            r'本月|这个月': 'this_month',
        }
        
        for pattern, value in time_patterns.items():
            if re.search(pattern, text):
                entities['timeRange'] = value
                break
        
        # 表名提取
        table_match = re.search(r'(?:查询|返回|显示)\s*(\w+)\s*表', text)
        if table_match:
            entities['table'] = table_match.group(1)
        
        # LIMIT 提取
        limit_match = re.search(r'(?:前\s*)?(\d+)\s*(?:条|条数|行)', text)
        if limit_match:
            entities['limit'] = int(limit_match.group(1))
        
        return entities
    
    def _merge_results(self, rule_result: Dict, llm_result: Dict) -> Dict:
        """合并规则和 LLM 结果"""
        return {
            'intent': llm_result.get('intent', rule_result['intent']),
            'confidence': max(
                rule_result['confidence'],
                llm_result.get('confidence', 0)
            ),
            'entities': {
                **rule_result.get('entities', {}),
                **llm_result.get('entities', {})
            },
            'methodsUsed': ['rule', 'llm']
        }
    
    def _generate_clarifications(self, intent: str, entities: Dict, confidence: float) -> List[str]:
        """生成澄清问题"""
        clarifications = []
        
        if confidence < 0.5:
            clarifications.append('您的意图不够清晰，请提供更多信息。')
            return clarifications
        
        # 根据意图类型生成澄清
        if intent == 'query_production':
            if not entities.get('timeRange'):
                clarifications.append('请指定查询的时间范围（如：今天、本周、上月）')
        elif intent == 'query_quality':
            if not entities.get('metrics'):
                clarifications.append('您想查询哪个质量指标？• 良品率 • 合格率 • 缺陷率')
        elif intent == 'query_equipment':
            if not entities.get('metrics'):
                clarifications.append('您想查询哪个设备指标？• OEE • 稼动率 • 故障时间')
        elif intent == 'generate_report':
            if not entities.get('reportType'):
                clarifications.append('请指定报表类型（如：日报、周报、月报）')
        
        return clarifications
```

### 步骤 2: 创建 API 路由

**在 `app/routes/query_routes.py` 中添加**：

```python
from app.services.intent_recognizer import IntentRecognizer

# 初始化意图识别器
intent_recognizer = IntentRecognizer(llm_provider=converter.llm_provider)

@bp.route('/recognize-intent', methods=['POST'])
def recognize_intent():
    """
    识别用户查询意图
    
    请求体:
        {
            "query": "查询今天的产量"
        }
    
    返回:
        {
            "success": true,
            "intent": "query_production",
            "confidence": 0.92,
            "entities": {
                "timeRange": "today"
            },
            "clarifications": [],
            "methodsUsed": ["rule", "llm"]
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: query'
            }), 400
        
        query = data['query'].strip()
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query cannot be empty'
            }), 400
        
        # 识别意图
        result = intent_recognizer.recognize(query)
        
        logger.info(f"Intent recognized: {result['intent']} "
                   f"(confidence: {result['confidence']:.2f}, "
                   f"methods: {result['methodsUsed']})")
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error in recognize_intent: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

---

## 📋 实现建议

### 优先级 1：基础实现（推荐立即执行）
- ✅ 创建 Python 意图识别服务
- ✅ 添加 `/api/query/recognize-intent` API
- ✅ 测试和验证

### 优先级 2：优化（后续）
- 🔄 添加缓存机制
- 🔄 集成到 NL2SQL 流程
- 🔄 性能监控

---

## 🔗 前端集成方式

### 方式 1: 在前端先做快速反馈

```typescript
// 1. 快速反馈（前端规则引擎）
const quickResult = recognizeIntentSync(userInput);
displayInitialIntent(quickResult);  // 立即显示

// 2. 后台确认（调用后端 API）
const preciseResult = await fetch('/api/query/recognize-intent', {
  method: 'POST',
  body: JSON.stringify({ query: userInput })
});
displayFinalIntent(preciseResult);  // 显示确认结果
```

### 方式 2: 仅使用后端 API

```typescript
// 直接调用后端，获取完整结果
const result = await fetch('/api/query/recognize-intent', {
  method: 'POST',
  body: JSON.stringify({ query: userInput })
});

const intent = await result.json();
handleIntent(intent);
```

---

## 📊 成本效益分析

| 方面 | 仅前端 | 仅后端 | 混合（推荐） |
|------|--------|--------|------------|
| 响应延迟 | 极低 | 中等 | 最优 |
| API 成本 | 高（每次调用） | 中等 | 低（缓存） |
| 服务器负载 | 低 | 高 | 中等 |
| 用户体验 | 无初始反馈 | 良好 | 极佳 |
| 开发复杂度 | 低 | 中等 | 中等 |

**总体评分**: 混合方案 ⭐⭐⭐⭐⭐

---

## ✨ 总结

**建议方案**: 采用**双层架构**

1. **前端**: 保留 `recognizeIntentSync()` 用于即时 UI 反馈
2. **后端**: 新增 `/api/query/recognize-intent` API 用于精确识别

这样可以：
- ✅ 提供最佳用户体验（快速初始反馈 + 精确最终结果）
- ✅ 降低 LLM API 成本（后端缓存）
- ✅ 集中管理意图识别逻辑
- ✅ 便于未来的持续优化

