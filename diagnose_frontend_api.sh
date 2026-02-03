#!/bin/bash

# 前端 API 连接诊断脚本

echo "🔍 NL2SQL 前端-后端连接诊断"
echo "================================="
echo ""

# 1. 检查后端是否运行
echo "1️⃣ 检查后端服务..."
if curl -s http://localhost:8000/api/schema/status > /dev/null 2>&1; then
    echo "✅ 后端服务运行中"
    BACKEND_RUNNING=true
else
    echo "❌ 后端服务未运行"
    echo "   启动后端: python run.py"
    BACKEND_RUNNING=false
fi
echo ""

# 2. 测试 OPTIONS 请求 (预检)
echo "2️⃣ 测试 CORS 预检请求 (OPTIONS)..."
OPTIONS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X OPTIONS http://localhost:8000/api/query/unified/explain \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" 2>/dev/null)

if [ "$OPTIONS_RESPONSE" = "200" ]; then
    echo "✅ OPTIONS 请求返回 200"
else
    echo "❌ OPTIONS 请求返回 $OPTIONS_RESPONSE"
fi
echo ""

# 3. 测试 POST 请求到 explain 端点
echo "3️⃣ 测试 POST 请求到 /explain 端点..."
if [ "$BACKEND_RUNNING" = true ]; then
    EXPLAIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/query/unified/explain \
      -H "Content-Type: application/json" \
      -d '{"natural_language": "查询OEE"}')
    
    if echo "$EXPLAIN_RESPONSE" | grep -q "success"; then
        echo "✅ /explain 端点返回有效响应"
        echo "   响应: $(echo "$EXPLAIN_RESPONSE" | head -c 100)..."
    else
        echo "❌ /explain 端点返回无效响应"
        echo "   响应: $EXPLAIN_RESPONSE"
    fi
else
    echo "⏭️  跳过 (后端未运行)"
fi
echo ""

# 4. 测试 POST 请求到 process 端点
echo "4️⃣ 测试 POST 请求到 /process 端点..."
if [ "$BACKEND_RUNNING" = true ]; then
    PROCESS_RESPONSE=$(curl -s -X POST http://localhost:8000/api/query/unified/process \
      -H "Content-Type: application/json" \
      -d '{"natural_language": "查询OEE", "execution_mode": "explain"}')
    
    if echo "$PROCESS_RESPONSE" | grep -q "success"; then
        echo "✅ /process 端点返回有效响应"
        echo "   响应: $(echo "$PROCESS_RESPONSE" | head -c 100)..."
    else
        echo "❌ /process 端点返回无效响应"
        echo "   响应: $PROCESS_RESPONSE"
    fi
else
    echo "⏭️  跳过 (后端未运行)"
fi
echo ""

# 5. 测试 GET 请求到推荐端点
echo "5️⃣ 测试 GET 请求到 /query-recommendations 端点..."
if [ "$BACKEND_RUNNING" = true ]; then
    RECOMMEND_RESPONSE=$(curl -s -X GET http://localhost:8000/api/query/unified/query-recommendations)
    
    if echo "$RECOMMEND_RESPONSE" | grep -q "recommendations"; then
        echo "✅ /query-recommendations 端点返回有效响应"
        echo "   响应: $(echo "$RECOMMEND_RESPONSE" | head -c 100)..."
    else
        echo "❌ /query-recommendations 端点返回无效响应"
        echo "   响应: $RECOMMEND_RESPONSE"
    fi
else
    echo "⏭️  跳过 (后端未运行)"
fi
echo ""

# 6. 显示诊断总结
echo "📊 诊断总结"
echo "================================="
if [ "$BACKEND_RUNNING" = true ]; then
    echo "✅ 后端服务: 运行中"
else
    echo "❌ 后端服务: 未运行"
    echo "   → 请运行: python run.py"
fi

if [ "$OPTIONS_RESPONSE" = "200" ]; then
    echo "✅ CORS 预检: 正常"
else
    echo "⚠️  CORS 预检: 失败 (响应 $OPTIONS_RESPONSE)"
fi

echo ""
echo "💡 前端调试建议:"
echo "  1. 打开浏览器开发者工具 (F12)"
echo "  2. 切换到 Network 标签"
echo "  3. 在前端输入查询"
echo "  4. 查看请求 URL 是否为:"
echo "     http://localhost:8000/api/query/unified/explain"
echo "  5. 检查响应状态码是否为 200"
echo ""
echo "📚 详细指南请查看:"
echo "  FRONTEND_API_FETCH_ERROR_FIX.md"
