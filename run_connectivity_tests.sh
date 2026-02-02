#!/usr/bin/env bash

# NL2SQL 服务联通性测试快速启动脚本
# 用途: 一键运行所有测试并生成报告

set -e

PROJECT_DIR="/Users/fupeggy/NL2SQL"
VENV_PATH="$PROJECT_DIR/.venv"
REPORT_FILE="$PROJECT_DIR/test_report_$(date +%Y%m%d_%H%M%S).txt"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函数: 打印标题
print_header() {
    echo -e "\n${BLUE}═════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═════════════════════════════════════${NC}\n"
}

# 函数: 打印成功
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# 函数: 打印错误
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 函数: 打印提示
print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# 主程序
main() {
    print_header "NL2SQL 服务联通性测试"
    
    # 检查项目目录
    if [ ! -d "$PROJECT_DIR" ]; then
        print_error "项目目录不存在: $PROJECT_DIR"
        exit 1
    fi
    
    print_info "项目目录: $PROJECT_DIR"
    print_info "报告文件: $REPORT_FILE"
    
    # 激活虚拟环境
    print_header "激活虚拟环境"
    
    if [ ! -f "$VENV_PATH/bin/activate" ]; then
        print_error "虚拟环境不存在，请先运行: python -m venv $VENV_PATH"
        exit 1
    fi
    
    source "$VENV_PATH/bin/activate"
    print_success "虚拟环境已激活"
    
    # 运行测试
    print_header "运行测试套件"
    
    cd "$PROJECT_DIR"
    
    print_info "运行后端连通性测试..."
    python test_connectivity.py 2>&1 | tee -a "$REPORT_FILE"
    
    # 检查测试结果
    print_header "测试完成"
    print_success "报告已生成: $REPORT_FILE"
    
    # 显示总结
    print_header "测试总结"
    tail -20 "$REPORT_FILE"
    
    print_info "完整报告位置: $REPORT_FILE"
    print_success "测试运行完成！"
}

# 运行主程序
main "$@"
