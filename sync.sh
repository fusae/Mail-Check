#!/bin/bash

# 代码同步到服务器脚本
# 用法: ./sync.sh [环境]

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 配置（根据你的服务器修改）
SERVER_USER="${SERVER_USER:-root}"           # SSH用户名
SERVER_HOST="${SERVER_HOST:-43.129.17.66}"         # 服务器地址
SERVER_PATH="${SERVER_PATH:-/root/mail_check}"  # 服务器上的路径

# 解析参数
ENVIRONMENT="${1:-prod}"

echo -e "${BLUE}=================================="
echo "   代码同步到服务器"
echo "==================================${NC}"
echo ""

# 根据环境设置配置
if [ "$ENVIRONMENT" == "test" ]; then
    echo -e "${YELLOW}测试环境同步${NC}"
    # 可以设置测试服务器的不同配置
    # SERVER_USER="test_user"
    # SERVER_HOST="test.server.com"
elif [ "$ENVIRONMENT" == "prod" ]; then
    echo -e "${YELLOW}生产环境同步${NC}"
else
    echo -e "${RED}未知环境: $ENVIRONMENT"
    echo "用法: $0 [test|prod]"
    exit 1
fi

echo -e "${BLUE}服务器: ${SERVER_USER}@${SERVER_HOST}${NC}"
echo -e "${BLUE}路径: ${SERVER_PATH}${NC}"
echo ""

# 检查本地代码
echo -e "${BLUE}检查本地代码...${NC}"
if [ ! -d "src" ] || [ ! -d "config" ]; then
    echo -e "${RED}错误: 未找到 src 或 config 目录${NC}"
    echo "请在项目根目录运行此脚本"
    exit 1
fi

# 同步代码
echo -e "${BLUE}开始同步代码...${NC}"
echo ""

rsync -avz --progress \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'logs/*.log' \
  --exclude 'data/*.db' \
  --exclude 'data/*.db-*' \
  --exclude '.git' \
  --exclude '*.pyc' \
  --exclude 'node_modules' \
  ./ ${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/

# 检查同步结果
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ 代码同步完成${NC}"
    echo ""
    echo -e "${YELLOW}下一步操作:${NC}"
    echo "  1. 连接服务器: ssh ${SERVER_USER}@${SERVER_HOST}"
    echo "  2. 查看状态: cd ${SERVER_PATH} && ./status.sh"
    echo "  3. 重启服务: ./stop.sh && ./run.sh --daemon"
    echo ""
    
    # 询问是否重启服务
    read -p "是否立即重启服务? (y/n): " restart_choice
    if [ "$restart_choice" == "y" ] || [ "$restart_choice" == "Y" ]; then
        echo ""
        echo -e "${BLUE}重启服务...${NC}"
        ssh ${SERVER_USER}@${SERVER_HOST} \
          "cd ${SERVER_PATH} && ./stop.sh && sleep 2 && ./run.sh --daemon"
        
        echo ""
        echo -e "${GREEN}✓ 服务重启完成${NC}"
        echo ""
        echo -e "${YELLOW}查看服务状态:${NC}"
        ssh ${SERVER_USER}@${SERVER_HOST} \
          "cd ${SERVER_PATH} && ./status.sh"
    fi
else
    echo ""
    echo -e "${RED}✗ 代码同步失败${NC}"
    exit 1
fi