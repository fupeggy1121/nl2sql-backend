# DeepSeek 集成快速开始指南

## 概述

本项目已成功集成 DeepSeek API，用于将自然语言转换为 SQL 查询。

## 快速开始

### 1. 获取 DeepSeek API 密钥

1. 访问 [DeepSeek 官网](https://www.deepseek.com)
2. 注册或登录账户
3. 进入 API 管理页面
4. 创建新的 API 密钥
5. 复制密钥

### 2. 配置环境变量

编辑 `.env` 文件，添加你的 DeepSeek API 密钥：

```bash
# DeepSeek Configuration
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxx  # 替换为你的 API 密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 选择 DeepSeek 作为 LLM 提供商
LLM_PROVIDER=deepseek
```

### 3. 启动应用

```bash
cd /Users/fupeggy/NL2SQL
python run.py
```

应用将在 `http://localhost:8000` 启动

### 4. 测试 API

使用 curl 或 Postman 测试：

```bash
# 健康检查
curl http://localhost:8000/api/query/health

# 自然语言转 SQL
curl -X POST http://localhost:8000/api/query/nl-to-sql \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询所有用户"}'

# 自然语言直接执行（需要数据库配置）
curl -X POST http://localhost:8000/api/query/nl-execute \
  -H "Content-Type: application/json" \
  -d '{"natural_language": "查询用户表中所有数据"}'
```

## 功能说明

### DeepSeek 集成特性

✅ **智能 NL2SQL 转换**
- 使用 DeepSeek 的先进语言模型
- 支持复杂的 SQL 查询生成
- 自动理解数据库 schema

✅ **灵活的 LLM 提供商**
- 默认使用 DeepSeek
- 支持切换到 OpenAI
- 抽象层设计便于扩展

✅ **错误处理和备选方案**
- API 调用失败时自动使用关键词匹配
- 完善的日志记录
- 详细的错误信息

✅ **多语言支持**
- 支持中文和英文查询
- 自动检测语言
- 语法优化

## 项目结构

```
app/services/
├── llm_provider.py      # LLM 提供商抽象层（新增）
├── nl2sql.py           # NL2SQL 转换服务（已更新）
└── query_executor.py   # 查询执行服务
```

### 核心类

**LLMProvider (基类)**
- `convert_nl_to_sql()` - 转换方法

**DeepSeekProvider**
- 实现 DeepSeek API 调用
- 自动处理认证
- 错误重试机制

**OpenAIProvider**
- 实现 OpenAI API 调用
- 兼容现有代码

## API 使用示例

### 示例 1：基础转换

```python
import requests

response = requests.post(
    'http://localhost:8000/api/query/nl-to-sql',
    json={'natural_language': '查询销售额最高的产品'}
)

result = response.json()
print(result['sql'])  # SELECT ... 生成的 SQL
```

### 示例 2：带 Schema 的转换

查询会自动包含数据库 schema 信息（如果已配置）。

### 示例 3：直接执行

```python
response = requests.post(
    'http://localhost:8000/api/query/nl-execute',
    json={'natural_language': '2024年的订单统计'}
)

result = response.json()
print(result['data'])  # 查询结果
```

## 配置选项

### 切换到 OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4
```

### 自定义 DeepSeek 模型

```env
DEEPSEEK_MODEL=deepseek-code  # 用于代码相关查询
```

### 调整 LLM 参数

在 `app/services/llm_provider.py` 中修改：

```python
payload = {
    'temperature': 0.3,      # 降低创意性，提高准确性
    'max_tokens': 1000,      # 最大生成长度
}
```

## 故障排查

### Q: "DeepSeek API key not configured"

A: 检查 `.env` 文件中的 `DEEPSEEK_API_KEY` 配置

```bash
grep DEEPSEEK_API_KEY .env
```

### Q: "DeepSeek API request timeout"

A: 检查网络连接，可增加超时时间：

```python
response = requests.post(..., timeout=60)  # 增加超时到 60 秒
```

### Q: "Invalid response from DeepSeek API"

A: 
- 检查 API 余额
- 确保模型名称正确
- 检查请求格式

### Q: 如何切换回 OpenAI？

A: 修改 `.env` 文件：

```env
LLM_PROVIDER=openai
```

## 性能提示

1. **缓存结果** - 为常见查询设置缓存
2. **批量处理** - 合并多个请求
3. **异步调用** - 使用异步 API 提高吞吐量
4. **温度参数** - 调整 temperature 以获得最佳平衡

## 后续步骤

1. ✅ 集成 DeepSeek API
2. 🔄 添加 SQL 验证层
3. 🔄 实现查询缓存
4. 🔄 添加用户认证
5. 🔄 性能监控

## 支持

如有问题，请检查：
- 日志输出（控制台或日志文件）
- `.env` 配置是否正确
- API 密钥是否有效
- 网络连接是否正常

## 许可证

MIT
