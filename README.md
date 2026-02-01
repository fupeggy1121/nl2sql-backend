# AI 报表工具 - NL2SQL 后端

一个基于 AI 的报表工具后端，能够将自然语言转换为 SQL 查询并执行查询返回数据。

## 功能特性

- **自然语言到 SQL 转换**: 使用 DeepSeek AI 将用户输入的自然语言转换为 SQL 查询语句
- **多 LLM 支持**: 支持 DeepSeek 和 OpenAI，可灵活切换
- **SQL 执行**: 连接数据库并执行转换后的 SQL 查询
- **RESTful API**: 提供完整的 HTTP API 接口供前端调用
- **错误处理**: 完善的错误处理和日志记录机制
- **CORS 支持**: 支持跨域请求
- **自动备份方案**: LLM 调用失败时使用关键词匹配

## 项目结构

```
NL2SQL/
├── app/                           # 应用主目录
│   ├── __init__.py               # 应用初始化
│   ├── routes/                   # 路由处理
│   │   ├── __init__.py
│   │   └── query_routes.py       # 查询相关路由
│   ├── services/                 # 业务逻辑服务
│   │   ├── nl2sql.py            # NL2SQL 转换服务
│   │   ├── query_executor.py    # 查询执行服务
│   │   └── llm_provider.py      # LLM 提供商抽象层（DeepSeek/OpenAI）
│   └── models/                   # 数据模型
│       ├── __init__.py
│       └── schemas.py            # 数据模型定义
├── config/                        # 配置文件
│   ├── __init__.py
│   ├── config.py                # Flask 配置
│   └── database.py              # 数据库配置
├── tests/                         # 测试文件
│   └── test_routes.py           # 路由测试
├── run.py                        # 应用启动文件
├── requirements.txt             # 项目依赖
├── .env                         # 环境变量（本地）
├── .env.example                 # 环境变量示例
└── .gitignore                  # Git 忽略文件
```

## 安装与运行

### 1. 克隆项目

```bash
cd /Users/fupeggy/NL2SQL
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库和 LLM API 密钥
```

### 5. 配置 DeepSeek API

在 `.env` 文件中配置：

```env
# DeepSeek Configuration
DEEPSEEK_API_KEY=sk-xxxxxx  # 从 https://www.deepseek.com 获取
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# 选择使用 DeepSeek 作为 LLM 提供商
LLM_PROVIDER=deepseek
```

### 6. 启动应用

```bash
python run.py
```

应用将在 `http://localhost:8000` 启动

## API 文档

### 1. 健康检查

**请求:**
```
GET /api/query/health
```

**响应:**
```json
{
  "status": "healthy",
  "service": "NL2SQL Report Backend"
}
```

### 2. 自然语言转 SQL

**请求:**
```
POST /api/query/nl-to-sql
Content-Type: application/json

{
  "natural_language": "查询所有用户信息"
}
```

**响应:**
```json
{
  "success": true,
  "sql": "SELECT * FROM users",
  "natural_language": "查询所有用户信息",
  "message": "Conversion successful"
}
```

> 使用配置的 LLM 提供商（默认为 DeepSeek）进行转换

### 3. 执行 SQL 查询

**请求:**
```
POST /api/query/execute
Content-Type: application/json

{
  "sql": "SELECT * FROM users LIMIT 10"
}
```

**响应:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "张三",
      "email": "zhangsan@example.com"
    }
  ],
  "count": 1,
  "columns": ["id", "name", "email"]
}
```

### 4. 自然语言直接执行查询

**请求:**
```
POST /api/query/nl-execute
Content-Type: application/json

{
  "natural_language": "查询所有用户"
}
```

**响应:**
```json
{
  "success": true,
  "sql": "SELECT * FROM users",
  "data": [...],
  "count": 10,
  "columns": ["id", "name", "email"]
}
```

## DeepSeek API 集成说明

### 功能特性

- **智能 NL2SQL 转换**: 使用 DeepSeek 的强大语言模型实现自然语言到 SQL 的转换
- **多 LLM 支持**: 支持 DeepSeek 和 OpenAI，可通过环境变量切换
- **自动备份方案**: 当 LLM API 调用失败时，自动使用关键词匹配方案
- **Schema 感知**: 支持将数据库 Schema 传递给 LLM 以生成更准确的 SQL
- **温度控制**: 调整 LLM 的 temperature 参数以控制输出的创意性与准确性

### 切换 LLM 提供商

在 `.env` 文件中修改 `LLM_PROVIDER` 变量：

```env
# 使用 DeepSeek
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key

# 或使用 OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
```

### 架构设计

```
NL2SQL Converter
    ├── LLM Provider (抽象层)
    │   ├── DeepSeek Provider
    │   └── OpenAI Provider
    └── Fallback (关键词匹配)
```

### 常见错误排查

1. **API 密钥错误**
   ```
   Error: DeepSeek API key not configured
   解决: 检查 .env 文件中的 DEEPSEEK_API_KEY
   ```

2. **API 调用超时**
   ```
   Error: DeepSeek API request timeout
   解决: 检查网络连接，增加 timeout 参数值
   ```

3. **无效的 API 响应**
   ```
   Error: Invalid response from DeepSeek API
   解决: 检查 API 余额，确保使用正确的模型名称
   ```

## 环境变量配置

编辑 `.env` 文件：

```env
# Flask 配置
FLASK_ENV=development
FLASK_APP=run.py
DEBUG=True

# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=report_db

# OpenAI 配置（可选）
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-3.5-turbo

# DeepSeek 配置
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# LLM 提供商选择 (openai 或 deepseek)
LLM_PROVIDER=deepseek

# Flask 密钥
SECRET_KEY=your_secret_key_here
PORT=8000
```

### 获取 DeepSeek API 密钥

1. 访问 [DeepSeek 官网](https://www.deepseek.com)
2. 注册账户或登录
3. 进入 API 管理页面
4. 创建新的 API 密钥
5. 将密钥复制到 `.env` 文件的 `DEEPSEEK_API_KEY` 字段

## 运行测试

```bash
pytest tests/ -v
```

## 开发指南

### 添加新的路由

1. 在 `app/routes/` 目录下创建新的路由文件
2. 定义蓝图和路由处理函数
3. 在 `app/__init__.py` 的 `register_blueprints()` 中注册

### 添加新的服务

1. 在 `app/services/` 目录下创建新的服务文件
2. 定义服务类和方法
3. 在需要的路由中导入和使用

### 代码规范

- 使用 Black 格式化代码: `black app/`
- 使用 Flake8 检查代码: `flake8 app/`
- 为所有函数添加文档字符串
- 添加适当的类型提示

## 技术栈

- **框架**: Flask 3.0.0
- **数据库**: MySQL
- **ORM**: SQLAlchemy
- **API**: Flask-CORS
- **AI/LLM**: DeepSeek API (默认) / OpenAI API (可选)
- **测试**: Pytest
- **代码质量**: Black, Flake8

## 后续改进计划

- [x] 集成 DeepSeek API 实现强大的 NL2SQL 转换
- [x] 支持多个 LLM 提供商（OpenAI、DeepSeek）
- [ ] 添加 SQL 验证和安全检查
- [ ] 实现数据库连接池
- [ ] 添加查询缓存机制
- [ ] 完善错误处理和日志
- [ ] 添加用户认证和授权
- [ ] 实现数据库 Schema 管理
- [ ] 添加性能监控和指标

## 许可证

MIT
