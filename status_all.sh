#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=================================="
echo "   舆情监控系统 - 服务状态"
echo "==================================${NC}"
echo ""

# 1. 检查主程序
echo -e "${BLUE}【舆情监控主程序】${NC}"
MAIN_PID=$(ps -eo pid,command | grep "src/main.py" | grep -v grep | awk '{print $1}' | head -1)
if [ -n "$MAIN_PID" ]; then
    echo -e "  状态: ${GREEN}运行中${NC}"
    echo "  进程ID: $MAIN_PID"
    echo "  运行时间: $(ps -o etime= -p $MAIN_PID | tr -d ' ')"
    echo "  内存: $(ps -o rss= -p $MAIN_PID | awk '{print int($1/1024)"MB"}')"
else
    echo -e "  状态: ${RED}未运行${NC}"
fi
echo ""

# 2. 检查API服务
echo -e "${BLUE}【API服务】${NC}"
API_PID=$(pgrep -f "api_server.py" | head -1)
if [ -n "$API_PID" ]; then
    echo -e "  状态: ${GREEN}运行中${NC}"
    echo "  进程ID: $API_PID"
    echo "  端口: 5003"
    echo -e "  访问: http://localhost:5003/feedback"
else
    echo -e "  状态: ${RED}未运行${NC}"
fi
echo ""

# 3. 检查数据库
echo -e "${BLUE}【数据库】${NC}"
if [ -f "data/processed_emails.db" ]; then
    DB_SIZE=$(du -h data/processed_emails.db | cut -f1)
    echo -e "  状态: ${GREEN}存在${NC} (大小: $DB_SIZE)"
else
    echo -e "  状态: ${YELLOW}不存在${NC}"
fi
echo ""

# 4. 最近日志
echo -e "${BLUE}【最近日志】${NC}"
if [ -f "logs/sentiment_monitor.log" ]; then
    echo "  主程序:"
    tail -3 logs/sentiment_monitor.log | sed 's/^/    /'
fi
echo ""

echo -e "${BLUE}=================================="
echo "常用命令:"
echo "  一键启动: ./start_all.sh"
echo "  一键停止: ./stop_all.sh"
echo "  主程序日志: tail -f logs/sentiment_monitor.log"
echo "  API日志: tail -f logs/api_server.log"
echo "==================================${NC}"
