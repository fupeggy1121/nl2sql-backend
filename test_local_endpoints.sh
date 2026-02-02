#!/bin/bash
# 本地测试 NL2SQL 后端所有端点的脚本

# 设置颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:5000/api/query"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}🧪 NL2SQL 后端端点测试脚本${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# 检查后端是否运行
echo -e "${BLUE}1️⃣ 检查后端服务是否运行...${NC}"
if curl -s "$BASE_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 后端服务正在运行${NC}"
else
    echo -e "${RED}❌ 后端服务未运行${NC}"
    echo "请先启动: python run.py"
    exit 1
fi
echo ""

# 测试健康检查
echo -e "${BLUE}2️⃣ 测试健康检查 (/health)${NC}"
echo "请求: GET $BASE_URL/health"
RESPONSE=$(curl -s "$BASE_URL/health")
echo "响应: $RESPONSE"
echo ""

# 测试 NL 转 SQL
echo -e "${BLUE}3️⃣ 测试 NL 转 SQL (/nl-to-sql)${NC}"
echo "请求: POST $BASE_URL/nl-to-sql"
echo "数据: {\"natural_language\":\"查询所有用户\"}"
RESPONSE=$(curl -s -X POST "$BASE_URL/nl-to-sql" \
  -H "Content-Type: application/json" \
  -d '{"natural_language":"查询所有用户"}')
echo "响应: $RESPONSE"
echo ""

# 测试意图识别 (关键端点)
echo -e "${BLUE}4️⃣ 测试意图识别 (/recognize-intent) ⭐ 关键${NC}"
echo "请求: POST $BASE_URL/recognize-intent"
echo "数据: {\"query\":\"查询wafers表的前300条数据\"}"
RESPONSE=$(curl -s -X POST "$BASE_URL/recognize-intent" \
  -H "Content-Type: application/json" \
  -d '{"query":"查询wafers表的前300条数据"}')

if echo "$RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✅ 响应:${NC}"
else
    echo -e "${RED}❌ 响应:${NC}"
fi
echo "$RESPONSE" | python -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# 测试 Supabase Schema
echo -e "${BLUE}5️⃣ 测试 Supabase Schema (/supabase/schema)${NC}"
echo "请求: GET $BASE_URL/supabase/schema"
RESPONSE=$(curl -s "$BASE_URL/supabase/schema")
echo "响应: $RESPONSE"
echo ""

# 测试连接检查
echo -e "${BLUE}6️⃣ 测试连接检查 (/check-connection)${NC}"
echo "请求: GET $BASE_URL/check-connection"
RESPONSE=$(curl -s "$BASE_URL/check-connection")
echo "响应: $RESPONSE" | python -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# 测试 NL 执行
echo -e "${BLUE}7️⃣ 测试 NL 执行 (/nl-execute)${NC}"
echo "请求: POST $BASE_URL/nl-execute"
echo "数据: {\"natural_language\":\"查询所有用户\"}"
RESPONSE=$(curl -s -X POST "$BASE_URL/nl-execute" \
  -H "Content-Type: application/json" \
  -d '{"natural_language":"查询所有用户"}')
echo "响应: $RESPONSE" | python -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✅ 测试完成！${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "📝 提示:"
echo "- 如果任何端点返回 404，说明路由未正确注册"
echo "- 如果返回 500，可能是服务初始化问题"
echo "- 关键端点: /recognize-intent (意图识别)"
echo "- 如需查看详细日志，查看终端运行 python run.py 的输出"
echo ""
