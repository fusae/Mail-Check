#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=================================="
echo "   舆情监控系统 - 一键停止"
echo "==================================${NC}"
echo ""

# 1. 停止主程序
echo -e "${BLUE}[1/2] 停止舆情监控主程序...${NC}"
MAIN_PIDS=$(ps -eo pid,command | grep "src/main.py" | grep -v grep | awk '{print $1}')
if [ -n "$MAIN_PIDS" ]; then
    for pid in $MAIN_PIDS; do
        kill $pid 2>/dev/null
    done
    sleep 1
    echo -e "${GREEN}✓ 已停止主程序${NC}"
else
    echo -e "${YELLOW}✗ 主程序未运行${NC}"
fi
echo ""

# 2. 停止反馈服务
echo -e "${BLUE}[2/2] 停止反馈服务...${NC}"
FB_PID=$(pgrep -f "feedback_web_server")
if [ -n "$FB_PID" ]; then
    kill $FB_PID 2>/dev/null
    sleep 1
    echo -e "${GREEN}✓ 已停止反馈服务${NC}"
else
    echo -e "${YELLOW}✗ 反馈服务未运行${NC}"
fi

echo ""
echo -e "${GREEN}=================================="
echo "   所有服务已停止"
echo "==================================${NC}"
