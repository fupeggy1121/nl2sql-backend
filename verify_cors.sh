#!/bin/bash
# 验证 Render 上的 CORS 配置

BACKEND_URL="https://nl2sql-backend-amok.onrender.com"
HEALTH_ENDPOINT="$BACKEND_URL/api/query/health"

echo "================================================================"
echo "验证 Render 后端 CORS 配置"
echo "================================================================"
echo ""

# 测试 1: 基本 GET 请求
echo "1️⃣ 测试基本 GET 请求..."
echo "   URL: $HEALTH_ENDPOINT"
RESPONSE=$(curl -s -w "\n%{http_code}" "$HEALTH_ENDPOINT")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ 返回状态码: $HTTP_CODE"
    echo "   响应体: $(echo $BODY | head -c 100)..."
else
    echo "   ❌ 返回状态码: $HTTP_CODE"
fi

echo ""

# 测试 2: OPTIONS 预检请求（检查 CORS headers）
echo "2️⃣ 测试 CORS 预检请求 (OPTIONS)..."
echo "   来源: https://test.local-credentialless.webcontainer-api.io"
OPTIONS_RESPONSE=$(curl -s -i -X OPTIONS "$HEALTH_ENDPOINT" \
  -H "Origin: https://test.local-credentialless.webcontainer-api.io" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: content-type")

echo "   响应头:"
echo "$OPTIONS_RESPONSE" | grep -i "access-control" || echo "   ❌ 未找到 CORS 头"

echo ""

# 测试 3: 模拟来自 Bolt.new 的请求
echo "3️⃣ 测试来自 Bolt.new 的 GET 请求..."
echo "   来源: https://test.local-credentialless.webcontainer-api.io"
GET_RESPONSE=$(curl -s -i "$HEALTH_ENDPOINT" \
  -H "Origin: https://test.local-credentialless.webcontainer-api.io" \
  -H "Content-Type: application/json")

echo "   CORS 相关响应头:"
echo "$GET_RESPONSE" | grep -i "access-control" || echo "   ❌ 未找到 CORS 头"
echo "$GET_RESPONSE" | grep -i "access-control-allow-origin" && echo "   ✅ 允许来源头存在" || echo "   ❌ 缺少允许来源头"

echo ""

# 测试 4: 完整响应检查
echo "4️⃣ 完整响应检查..."
FULL_RESPONSE=$(curl -s "$HEALTH_ENDPOINT")

if echo "$FULL_RESPONSE" | grep -q '"status":"healthy"'; then
    echo "   ✅ 后端返回正常响应"
    echo "   后端状态: $(echo $FULL_RESPONSE | grep -o '"status":"[^"]*"')"
    echo "   Supabase: $(echo $FULL_RESPONSE | grep -o '"supabase":"[^"]*"')"
else
    echo "   ❌ 后端响应异常"
fi

echo ""
echo "================================================================"
echo "验证完成"
echo "================================================================"
