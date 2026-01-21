#!/bin/bash

# 快速部署脚本 - 适用于已经配置好的服务器
# 使用本脚本前请确保：
# 1. 已经上传代码到服务器
# 2. 已经配置好 config/config.yaml

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=================================="
echo "   快速部署脚本"
echo "==================================${NC}"
echo ""

# 检查配置文件
if [ ! -f "config/config.yaml" ]; then
    echo -e "${YELLOW}警告: config/config.yaml 不存在${NC}"
    echo "请先配置好配置文件后再运行此脚本"
    echo ""
    echo "如需完整部署，请运行: ./deploy.sh"
    exit 1
fi

# 创建虚拟环境
echo -e "${BLUE}1. 创建虚拟环境...${NC}"
python3 -m venv venv
source venv/bin/activate

# 升级pip
pip install --upgrade pip setuptools wheel

# 安装依赖
echo -e "${BLUE}2. 安装Python依赖...${NC}"
pip install -r requirements.txt

# 安装Playwright
echo -e "${BLUE}3. 安装Playwright浏览器...${NC}"
playwright install chromium
playwright install-deps chromium

# 创建目录
echo -e "${BLUE}4. 创建必要目录...${NC}"
mkdir -p logs data config

# 设置权限
echo -e "${BLUE}5. 设置权限...${NC}"
chmod +x run.sh stop.sh status.sh deploy.sh

# 创建管理脚本
echo -e "${BLUE}6. 创建管理脚本...${NC}"
cat > stop.sh << 'EOF'
#!/bin/bash
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

PID=$(pgrep -f "python.*main.py")
if [ -n "$PID" ]; then
    echo -e "${GREEN}正在停止舆情监控系统...${NC}"
    kill $PID
    sleep 2
    if ps -p $PID > /dev/null; then
        kill -9 $PID
    fi
    echo -e "${GREEN}舆情监控系统已停止${NC}"
else
    echo -e "${RED}未找到运行中的舆情监控系统${NC}"
fi
EOF

chmod +x stop.sh

cat > status.sh << 'EOF'
#!/bin/bash
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "舆情监控系统状态"
echo "=================================================================="

PID=$(pgrep -f "python.*main.py")
if [ -n "$PID" ]; then
    echo -e "进程状态: ${GREEN}运行中${NC}"
    echo "进程ID: $PID"
else
    echo -e "进程状态: ${RED}未运行${NC}"
fi

if [ -f "logs/sentiment_monitor.log" ]; then
    echo ""
    echo "最近5条日志:"
    tail -5 logs/sentiment_monitor.log
fi

echo ""
echo "=================================================================="
EOF

chmod +x status.sh

echo ""
echo -e "${GREEN}=================================="
echo "   快速部署完成！"
echo "==================================${NC}"
echo ""
echo "现在可以运行以下命令："
echo "  启动服务: ./run.sh --daemon"
echo "  停止服务: ./stop.sh"
echo "  查看状态: ./status.sh"
echo "  查看日志: tail -f logs/sentiment_monitor.log"
echo ""