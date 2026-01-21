#!/bin/bash

# 服务器端自动更新脚本
# 使用方法: 在服务器上执行 ./auto_update.sh

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=================================="
echo "   服务器自动更新"
echo "==================================${NC}"
echo ""

# 检查是否在项目目录
if [ ! -f "src/main.py" ]; then
    echo -e "${RED}错误: 请在项目根目录运行此脚本${NC}"
    exit 1
fi

# 检查是否为Git仓库
if [ ! -d ".git" ]; then
    echo -e "${RED}错误: 当前目录不是Git仓库${NC}"
    echo "请先使用Git管理代码"
    exit 1
fi

# 获取当前分支
CURRENT_BRANCH=$(git branch --show-current)
echo -e "${BLUE}当前分支: ${CURRENT_BRANCH}${NC}"
echo ""

# 检查是否有更新
echo -e "${BLUE}检查远程更新...${NC}"
git fetch origin

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/${CURRENT_BRANCH})

if [ "$LOCAL" == "$REMOTE" ]; then
    echo -e "${GREEN}✓ 已经是最新版本${NC}"
    echo ""
    echo "无需更新，退出"
    exit 0
fi

echo -e "${YELLOW}发现新版本${NC}"
echo ""
echo "本地版本: $(git log -1 --pretty=format:'%h - %s (%cr)' HEAD)"
echo "远程版本: $(git log -1 --pretty=format:'%h - %s (%cr)' origin/${CURRENT_BRANCH})"
echo ""

# 确认更新
read -p "是否更新到最新版本? (y/n): " update_choice
if [ "$update_choice" != "y" ] && [ "$update_choice" != "Y" ]; then
    echo "取消更新"
    exit 0
fi

# 停止服务
echo ""
echo -e "${BLUE}停止服务...${NC}"
./stop.sh

# 更新代码
echo -e "${BLUE}拉取最新代码...${NC}"
git pull origin ${CURRENT_BRANCH}

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ 代码拉取失败${NC}"
    echo "尝试重新启动服务..."
    ./run.sh --daemon
    exit 1
fi

# 检查依赖是否更新
echo -e "${BLUE}检查依赖更新...${NC}"
if [ "requirements.txt" -nt "venv/.last_update" ]; then
    echo -e "${YELLOW}检测到依赖更新，重新安装...${NC}"
    source venv/bin/activate
    pip install -r requirements.txt
    touch venv/.last_update
else
    echo "依赖无变化"
fi

# 重新启动服务
echo -e "${BLUE}重新启动服务...${NC}"
sleep 2
./run.sh --daemon

# 检查启动状态
sleep 3
PID=$(pgrep -f "python.*main.py")
if [ -n "$PID" ]; then
    echo -e "${GREEN}✓ 服务启动成功 (PID: $PID)${NC}"
else
    echo -e "${RED}✗ 服务启动失败${NC}"
    echo "请查看日志: tail -f logs/sentiment_monitor.log"
    exit 1
fi

echo ""
echo -e "${GREEN}=================================="
echo "   更新完成！"
echo "==================================${NC}"
echo ""
echo "查看服务状态: ./status.sh"
echo "查看运行日志: tail -f logs/sentiment_monitor.log"
echo ""