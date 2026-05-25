#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

cd "$(dirname "$0")"
source ./env.sh

PID=$(pgrep -f "python .*src/main.py")
if [ -n "$PID" ]; then
    echo -e "${YELLOW}舆情监控系统已在运行中 (PID: $PID)${NC}"
    read -p "是否重启? (y/n): " restart_choice
    if [ "$restart_choice" != "y" ] && [ "$restart_choice" != "Y" ]; then
        exit 0
    fi
    echo -e "${YELLOW}正在停止现有进程...${NC}"
    kill "$PID"
    sleep 2
    if ps -p "$PID" > /dev/null; then
        kill -9 "$PID"
    fi
fi

echo -e "${GREEN}=================================="
echo "   舆情监控系统启动"
echo -e "==================================${NC}"
echo ""

echo -e "${BLUE}检查运行环境...${NC}"
ensure_runtime || exit 1

if [ ! -f "config/config.yaml" ]; then
    echo -e "${RED}错误: 配置文件不存在: config/config.yaml${NC}"
    exit 1
fi

mkdir -p logs

if [ "$1" == "--daemon" ] || [ "$1" == "-d" ]; then
    echo -e "${BLUE}以后台模式启动...${NC}"
    nohup env PATH="$ENV_BIN:$PATH" LD_LIBRARY_PATH="${ENV_PREFIX}/lib:${LD_LIBRARY_PATH:-}" PLAYWRIGHT_NODEJS_PATH="$NODE_BIN" "$PYTHON_BIN" src/main.py > logs/startup.log 2>&1 &
    NEW_PID=$!
    sleep 3

    if ps -p "$NEW_PID" > /dev/null; then
        echo -e "${GREEN}舆情监控系统已成功启动 (PID: $NEW_PID)${NC}"
        echo ""
        echo "查看日志:"
        echo "  实时日志: tail -f logs/sentiment_monitor.log"
        echo "  启动日志: tail -f logs/startup.log"
        echo "  API日志: tail -f logs/api_server.log"
        echo ""
        echo "管理命令:"
        echo "  停止服务: ./stop_all.sh"
        echo "  查看状态: ./status_all.sh"
    else
        echo -e "${RED}启动失败，请查看日志: logs/startup.log${NC}"
        exit 1
    fi
else
    echo ""
    echo -e "${GREEN}=================================="
    echo "   启动舆情监控程序"
    echo -e "==================================${NC}"
    echo ""
    echo -e "${YELLOW}按 Ctrl+C 停止程序${NC}"
    echo ""
    run_in_env "$PYTHON_BIN" src/main.py
fi
