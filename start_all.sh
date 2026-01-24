#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=================================="
echo "   舆情监控系统 - 一键启动"
echo "==================================${NC}"
echo ""

# 1. 启动 API/反馈服务
echo -e "${BLUE}[1/2] 启动 API/反馈服务...${NC}"
API_PID=$(pgrep -f "api_server.py")
if [ -n "$API_PID" ]; then
    echo -e "${YELLOW}API服务已在运行 (PID: $API_PID)${NC}"
else
    if [ -d "venv" ]; then
        source venv/bin/activate
        mkdir -p logs
        nohup python3 src/api_server.py > logs/api_server.log 2>&1 &
        echo $! > api_server.pid
        sleep 2
        if ps -p $(cat api_server.pid) > /dev/null 2>&1; then
            echo -e "${GREEN}✓ API服务启动成功 (端口: 5003)${NC}"
        else
            echo -e "${YELLOW}✗ API服务启动失败${NC}"
            rm -f api_server.pid
        fi
    else
        echo -e "${YELLOW}虚拟环境不存在，跳过API服务${NC}"
    fi
fi
echo ""

# 2. 启动主程序
echo -e "${BLUE}[2/2] 启动舆情监控主程序...${NC}"
if [ -f "run.sh" ]; then
    ./run.sh --daemon
else
    echo -e "${YELLOW}run.sh 不存在，请先创建${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=================================="
echo "   启动完成！"
echo "==================================${NC}"
echo ""
echo "服务状态:"
echo "  主程序: ./status.sh"
echo "  查看日志: tail -f logs/sentiment_monitor.log"
echo "  API日志: tail -f logs/api_server.log"
echo ""
echo "停止服务:"
echo "  ./stop_all.sh"
echo "=================================="
