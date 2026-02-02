#!/bin/bash

# NL2SQL 连接检查脚本
# 用于快速诊断前后端连接问题

echo "🔍 NL2SQL 连接诊断工具"
echo "========================="
echo ""

# 后端 URL
BACKEND_URL="https://nl2sql-backend-amok.onrender.com"
API_ENDPOINT="$BACKEND_URL/api/query/health"

echo "📡 检查后端连接..."
echo "目标: $API_ENDPOINT"
echo ""

# 检查后端连接
if command -v curl &> /dev/null; then
    echo "⏳ 发送请求..."
    
    response=$(curl -s -w "\n%{http_code}" "$API_ENDPOINT")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    echo "HTTP 状态码: $http_code"
    echo ""
    
    if [ "$http_code" = "200" ]; then
        echo "✅ 后端响应正常！"
        echo ""
        echo "📋 响应内容:"
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
        echo ""
        
        # 检查 Supabase 连接状态
        supabase_status=$(echo "$body" | python3 -c "import sys, json; print(json.load(sys.stdin).get('supabase', 'unknown'))" 2>/dev/null)
        
        if [ "$supabase_status" = "connected" ]; then
            echo "✅ Supabase 已连接"
        elif [ "$supabase_status" = "disconnected" ]; then
            echo "⚠️  Supabase 未连接"
            echo ""
            echo "🔧 解决方案:"
            echo "   1. 在 Render 仪表板中添加环境变量:"
            echo "      - SUPABASE_URL: https://your-project.supabase.co"
            echo "      - SUPABASE_SERVICE_KEY: your-service-role-key"
            echo "   2. 保存后等待服务重新部署"
            echo "   3. 重新运行此脚本验证"
        else
            echo "❓ Supabase 状态未知: $supabase_status"
        fi
        
    else
        echo "❌ 后端响应异常"
        echo "HTTP 状态码: $http_code"
        echo ""
        echo "📋 响应内容:"
        echo "$body"
        echo ""
        echo "🔧 可能的原因:"
        echo "   1. 后端服务未启动或已崩溃"
        echo "   2. Render 仪表板中查看日志"
        echo "   3. 检查 URL 是否正确"
    fi
else
    echo "⚠️  未找到 curl 命令，请手动在浏览器中访问:"
    echo "   $API_ENDPOINT"
    echo ""
    echo "或使用以下 JavaScript 代码在浏览器 Console 中测试:"
    cat << 'EOF'

fetch('https://nl2sql-backend-amok.onrender.com/api/query/health')
  .then(r => r.json())
  .then(data => {
    console.log('✅ 后端响应:', data);
    if (data.supabase === 'connected') {
      console.log('✅ Supabase 已连接');
    } else {
      console.log('⚠️  Supabase 未连接，需要配置环境变量');
    }
  })
  .catch(err => console.error('❌ 连接失败:', err));

EOF
fi

echo ""
echo "========================="
echo "诊断完成！"
