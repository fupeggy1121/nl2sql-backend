# LLM 提供商修复 - 问题解决

## 🔍 问题诊断

### 症状
后端返回: `"reasoning": "LLM provider not available"`

### 根本原因
在 `app/services/unified_query_service.py` 中，`IntentRecognizer` 被初始化时**没有传递 LLM 提供商**：

```python
# ❌ 错误的做法
class UnifiedQueryService:
    def __init__(self):
        self.intent_recognizer = IntentRecognizer()  # 没有 LLM 提供商！
        self.llm_provider = LLMProvider()  # 创建了但没用上
```

因为没有传递 LLM 提供商，`IntentRecognizer` 中的 `self.llm_provider` 为 `None`，导致 `_llm_based_match()` 方法返回：
```python
if not self.llm_provider:
    return {
        'reasoning': 'LLM provider not available'
    }
```

## ✅ 解决方案

### 修复步骤

**文件**: `app/services/unified_query_service.py`

#### 1. 更新导入
```python
# ❌ 之前
from app.services.llm_provider import LLMProvider

# ✅ 之后
from app.services.llm_provider import get_llm_provider
```

#### 2. 更新初始化逻辑
```python
# ❌ 之前
def __init__(self):
    self.intent_recognizer = IntentRecognizer()
    self.nl2sql_converter = get_enhanced_nl2sql_converter()
    self.query_executor = QueryExecutor()
    self.llm_provider = LLMProvider()

# ✅ 之后
def __init__(self):
    # 初始化 LLM 提供商
    self.llm_provider = get_llm_provider()
    
    # 初始化意图识别器，并传递 LLM 提供商
    self.intent_recognizer = IntentRecognizer(llm_provider=self.llm_provider)
    self.nl2sql_converter = get_enhanced_nl2sql_converter()
    self.query_executor = QueryExecutor()
```

## 🧪 验证修复

### 修复前
```json
{
  "reasoning": "LLM provider not available",
  "success": true
}
```

### 修复后
```json
{
  "reasoning": "用户查询的是OEE（Overall Equipment Effectiveness，设备综合效率）数据...",
  "methodsUsed": ["rule", "llm"],
  "confidence": 0.92,
  "success": true
}
```

### 测试命令
```bash
# 1. 重启后端
pkill -f "python.*run.py"
python run.py

# 2. 测试查询处理
curl -X POST http://localhost:8000/api/query/unified/process \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询今天的OEE数据", "execution_mode": "explain"}' | jq '.query_plan.query_intent.raw_intent_data'

# 3. 查看 reasoning 字段
# 应该包含详细的 LLM 分析而不是 "LLM provider not available"
```

## 📊 现在的工作流程

```
自然语言查询
    ↓
规则匹配 (快速)
    ↓
规则置信度 > 0.8?
    ├─ 是 → 返回结果
    └─ 否 ↓
         LLM 分析 (准确) ✅ 现在工作了！
    ↓
合并结果
    ↓
生成澄清问题或 SQL
```

## 🔧 相关代码

### IntentRecognizer 初始化
```python
class IntentRecognizer:
    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider  # 需要接收 LLM 提供商
```

### LLM 提供商工厂函数
```python
def get_llm_provider() -> LLMProvider:
    """获取配置的 LLM 提供商"""
    provider_name = os.getenv('LLM_PROVIDER', 'deepseek')
    
    if provider_name == 'deepseek':
        return DeepSeekProvider()
    elif provider_name == 'openai':
        return OpenAIProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")
```

## 🎯 影响

这个修复使得：
- ✅ 意图识别准确率提高 (从规则匹配提升到 LLM 混合)
- ✅ 澄清问题生成更准确
- ✅ SQL 生成质量提升
- ✅ 用户体验改善

## 📝 提交信息

```
fix: 修复 LLM 提供商未被传递给意图识别器的问题

问题：
- IntentRecognizer 初始化时未传递 LLM 提供商
- 导致意图识别只能使用规则匹配，无法进行 LLM 分析
- 返回 "LLM provider not available" 错误信息

解决：
- 更新导入：LLMProvider → get_llm_provider
- 初始化时先创建 LLM 提供商
- 将 LLM 提供商传递给 IntentRecognizer

验证：
- 测试查询现在返回完整的 LLM reasoning 字段
- 意图识别使用规则 + LLM 混合方式
- DeepSeek API 连接正常
```

## 📌 关键文件

- `app/services/unified_query_service.py` - 修复位置
- `app/services/intent_recognizer.py` - 意图识别实现
- `app/services/llm_provider.py` - LLM 提供商工厂
- `.env` - DeepSeek API 配置

