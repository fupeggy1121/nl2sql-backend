# 🔧 前端后端集成故障排查 & Supabase 环境变量配置

## 📋 问题诊断

### 前端错误：`Failed to fetch`
```
TypeError: Failed to fetch at Q.window.fetch
at Object.checkConnection (/.../nl2sqlApi.js:10:30)
```

**原因：**
1. 前端调用的 API 地址配置不正确
2. 后端服务未响应或 CORS 未配置
3. 网络连接问题

### 后端错误：`"supabase":"disconnected"`

**原因：**
Render 环境中缺少 Supabase 环境变量：
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

---

## ✅ 解决方案

### 第一步：修复前端 API 配置

#### 方案 A：在 Bolt.new 中直接配置（推荐用于开发）

在你的 Bolt 项目中，找到 `src/services/nl2sqlApi.js`（或创建它）：

```javascript
// src/services/nl2sqlApi.js

const API_BASE_URL = 'https://nl2sql-backend-amok.onrender.com/api/query';

// 健康检查 - 检查数据库连接
export const nl2sqlApi = {
  checkConnection: async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        return {
          connected: false,
          error: `HTTP ${response.status}`,
        };
      }
      
      const data = await response.json();
      return {
        connected: data.supabase === 'connected',
        status: data.status,
        supabase: data.supabase,
        tables: data.tables || [],
      };
    } catch (error) {
      console.error('Connection check failed:', error);
      return {
        connected: false,
        error: error.message,
      };
    }
  },

  // 执行 NL 查询
  executeNLQuery: async (naturalLanguage) => {
    try {
      const response = await fetch(`${API_BASE_URL}/nl-execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          natural_language: naturalLanguage,
        }),
      });

      if (!response.ok) {
        return {
          success: false,
          error: `HTTP ${response.status}`,
        };
      }

      return await response.json();
    } catch (error) {
      console.error('Query execution failed:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  },

  // NL 转 SQL（仅转换，不执行）
  convertNLToSQL: async (naturalLanguage) => {
    try {
      const response = await fetch(`${API_BASE_URL}/nl-to-sql`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          natural_language: naturalLanguage,
        }),
      });

      if (!response.ok) {
        return {
          success: false,
          error: `HTTP ${response.status}`,
        };
      }

      return await response.json();
    } catch (error) {
      console.error('NL to SQL conversion failed:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  },
};

export default nl2sqlApi;
```

---

### 第二步：在 Render 中配置 Supabase 环境变量

#### 步骤 1：获取 Supabase 凭证

1. 登录 [Supabase Dashboard](https://app.supabase.com)
2. 选择你的项目
3. 进入 **Settings** → **API**
4. 复制以下信息：
   - **Project URL** → 对应 `SUPABASE_URL`
   - **Service Role Secret** → 对应 `SUPABASE_SERVICE_KEY`

**示例：**
```
SUPABASE_URL = https://kgmyhukvyygudsllypgv.supabase.co
SUPABASE_SERVICE_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 步骤 2：在 Render 中添加环境变量

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 找到你的后端服务 `nl2sql-backend-amok`
3. 进入 **Environment** 标签页
4. 点击 **Add Environment Variable**
5. 添加以下两个变量：

| Key | Value |
|-----|-------|
| `SUPABASE_URL` | `https://kgmyhukvyygudsllypgv.supabase.co` |
| `SUPABASE_SERVICE_KEY` | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |

**⚠️ 重要提示：**
- `SUPABASE_SERVICE_KEY` 是敏感信息，只在服务器端使用
- 永远不要在前端代码或 GitHub 中暴露
- 在 Render 中，它自动加密存储

#### 步骤 3：保存并重新部署

1. 点击 **Save Changes**
2. Render 会自动重新部署你的服务
3. 等待部署完成（约 1-2 分钟）

**验证部署状态：**
```bash
# 在浏览器中测试
curl https://nl2sql-backend-amok.onrender.com/api/query/health
```

预期响应：
```json
{
  "service": "NL2SQL Report Backend",
  "status": "healthy",
  "supabase": "connected"  ← 应该是 "connected"
}
```

---

### 第三步：更新后端代码以处理缺少的凭证

编辑 `app/routes/query_routes.py`：

```python
# 健康检查端点 - 优化错误处理
@bp.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    try:
        supabase = get_supabase()
        supabase_status = 'connected' if supabase else 'disconnected'
    except Exception as e:
        logger.warning(f"Supabase connection check failed: {str(e)}")
        supabase_status = 'disconnected'
    
    return jsonify({
        'service': 'NL2SQL Report Backend',
        'status': 'healthy',
        'supabase': supabase_status,
        'timestamp': datetime.now().isoformat(),
    }), 200
```

编辑 `app/services/supabase_client.py`：

```python
import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class SupabaseClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化 Supabase 客户端"""
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
            
            if not supabase_url or not supabase_key:
                logger.warning(
                    "Supabase credentials not configured. "
                    "Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
                )
                self.client = None
                return
            
            self.client = create_client(supabase_url, supabase_key)
            logger.info("✅ Supabase client initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase client: {str(e)}")
            self.client = None

    def get_client(self) -> Client:
        """获取 Supabase 客户端"""
        if self.client is None:
            logger.warning("Supabase client is not initialized")
        return self.client

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.client is not None
```

---

## 🧪 测试连接

### 方法 1：在浏览器中测试

打开浏览器开发者工具（F12），在 Console 中运行：

```javascript
// 测试后端连接
fetch('https://nl2sql-backend-amok.onrender.com/api/query/health')
  .then(r => r.json())
  .then(console.log);

// 预期输出：
// {
//   "service": "NL2SQL Report Backend",
//   "status": "healthy",
//   "supabase": "connected"  ← 应该显示这个
// }
```

### 方法 2：在 Bolt 项目中测试

在 Bolt 的 Console 中运行：

```javascript
import nl2sqlApi from './services/nl2sqlApi';

// 测试连接
const result = await nl2sqlApi.checkConnection();
console.log('Connection status:', result);
```

### 方法 3：使用 curl（如果有命令行）

```bash
curl -X GET https://nl2sql-backend-amok.onrender.com/api/query/health
```

---

## 🐛 常见问题排查

### ❌ 问题 1：仍然显示 `"supabase":"disconnected"`

**检查清单：**
1. ✅ 环境变量是否已正确添加到 Render？
2. ✅ Render 服务是否已重新部署？
3. ✅ `SUPABASE_URL` 格式是否正确（应该包含 `.supabase.co`）？
4. ✅ `SUPABASE_SERVICE_KEY` 是否是完整的密钥（不是 `anon` key）？

**解决方法：**
```bash
# 在 Render 仪表板中查看日志
# 搜索 "Supabase" 关键词找到相关错误
```

### ❌ 问题 2：前端仍然报 `Failed to fetch`

**检查清单：**
1. ✅ API URL 是否正确？(`https://nl2sql-backend-amok.onrender.com/api/query`)
2. ✅ 网络连接是否正常？
3. ✅ 后端服务是否已启动？（检查 Render 仪表板）
4. ✅ CORS 是否已配置？

**验证后端是否在运行：**
```bash
# 访问 Render URL
https://nl2sql-backend-amok.onrender.com/
# 应该显示 404 或欢迎信息，不应该连接超时
```

### ❌ 问题 3：执行查询但无数据返回

**可能原因：**
1. 数据库中没有数据
2. SQL 查询有误
3. 数据库权限问题

**解决方法：**
1. 在 Supabase 仪表板中手动检查表是否存在
2. 尝试简单查询：`SELECT * FROM users LIMIT 1`
3. 检查 Render 日志中的数据库错误

---

## 📝 完整的 Render 环境变量配置

更新你的 `render.yaml` 文件：

```yaml
services:
  - type: web
    name: nl2sql-backend
    runtime: python311
    pythonVersion: 3.11.9
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --bind 0.0.0.0:$PORT run:app
    envVars:
      # Flask 配置
      - key: FLASK_ENV
        value: production
      - key: DEBUG
        value: "False"
      - key: PORT
        value: $PORT
      
      # Supabase 配置（必需）
      - key: SUPABASE_URL
        sync: false  # 从 Render 仪表板获取
      - key: SUPABASE_SERVICE_KEY
        sync: false  # 从 Render 仪表板获取
      
      # LLM 配置
      - key: DEEPSEEK_API_KEY
        sync: false
      - key: DEEPSEEK_BASE_URL
        value: https://api.deepseek.com
      - key: DEEPSEEK_MODEL
        value: deepseek-chat
      - key: LLM_PROVIDER
        value: deepseek
```

提交更新：
```bash
git add render.yaml
git commit -m "Update: Add Supabase environment variables to Render config"
git push origin main
```

---

## ✨ 验证成功标志

当所有配置正确时，你应该看到：

### ✅ 后端健康检查
```json
{
  "service": "NL2SQL Report Backend",
  "status": "healthy",
  "supabase": "connected"
}
```

### ✅ 前端连接状态
在 Bolt 的统一聊天界面顶部应该显示：
```
✅ 已连接  (而不是 ❌ 未连接)
```

### ✅ 查询执行
提交查询后，应该返回：
```
✅ 查询成功执行，返回 X 条数据
```

---

## 📞 需要帮助？

如果问题仍未解决，请提供：
1. Render 服务的实时日志
2. 浏览器控制台错误信息的完整堆栈跟踪
3. 你的 Supabase 项目 URL（不需要密钥）

记住：**永远不要在任何地方公开你的 SUPABASE_SERVICE_KEY**！

