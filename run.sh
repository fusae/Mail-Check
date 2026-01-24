#!/bin/bash

# 舆情监控系统启动脚本（服务器版）

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 确保在项目根目录
cd "$(dirname "$0")"

# 检查进程是否已在运行
PID=$(pgrep -f "python.*main.py")
if [ -n "$PID" ]; then
    echo -e "${YELLOW}舆情监控系统已在运行中 (PID: $PID)${NC}"
    read -p "是否重启? (y/n): " restart_choice
    if [ "$restart_choice" != "y" ] && [ "$restart_choice" != "Y" ]; then
        exit 0
    fi
    echo -e "${YELLOW}正在停止现有进程...${NC}"
    kill $PID
    sleep 2
    if ps -p $PID > /dev/null; then
        kill -9 $PID
    fi
fi

echo -e "${GREEN}=================================="
echo "   舆情监控系统启动"
echo "==================================${NC}"
echo ""

# 激活虚拟环境
echo -e "${BLUE}激活虚拟环境...${NC}"
if [ ! -d "venv" ]; then
    echo -e "${RED}错误: 虚拟环境不存在，请先运行部署脚本${NC}"
    exit 1
fi
source venv/bin/activate

# 检查配置文件
echo -e "${BLUE}检查配置文件...${NC}"
if [ ! -f "config/config.yaml" ]; then
    echo -e "${RED}错误: 配置文件不存在: config/config.yaml${NC}"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 检查是否后台运行
if [ "$1" == "--daemon" ] || [ "$1" == "-d" ]; then
    echo -e "${BLUE}以后台模式启动...${NC}"
    nohup python3 src/main.py > logs/startup.log 2>&1 &
    NEW_PID=$!
    sleep 2

    # 检查是否启动成功
    if ps -p $NEW_PID > /dev/null; then
        echo -e "${GREEN}舆情监控系统已成功启动 (PID: $NEW_PID)${NC}"
        echo ""
        echo "查看日志:"
        echo "  实时日志: tail -f logs/sentiment_monitor.log"
        echo "  启动日志: tail -f logs/startup.log"
        echo "  API日志: tail -f logs/api_server.log"
        echo ""
        echo "管理命令:"
        echo "  停止服务: ./stop.sh"
        echo "  查看状态: ./status.sh"
    else
        echo -e "${RED}启动失败，请查看日志: logs/startup.log${NC}"
        exit 1
    fi
else
    # 前台运行
    echo ""
    echo -e "${GREEN}=================================="
    echo "   启动舆情监控程序"
    echo "==================================${NC}"
    echo ""
    echo -e "${YELLOW}按 Ctrl+C 停止程序${NC}"
    echo ""
    
    python3 src/main.py
fi
