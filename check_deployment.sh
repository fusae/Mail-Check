#!/bin/bash
# 检查部署状态的脚本

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "  舆情监控系统部署状态检查"
echo "=========================================="
echo ""

# 1. 检查目录结构
echo -e "${GREEN}[1/8]${NC} 检查目录结构..."
if [ -d "venv" ] && [ -d "logs" ] && [ -d "data" ] && [ -d "config" ]; then
    echo -e "  ${GREEN}✓${NC} 目录结构完整"
else
    echo -e "  ${RED}✗${NC} 目录结构不完整"
fi
echo ""

# 2. 检查Python虚拟环境
echo -e "${GREEN}[2/8]${NC} 检查Python虚拟环境..."
if [ -f "venv/bin/python3" ]; then
    PYTHON_VER=$(./venv/bin/python3 --version 2>/dev/null)
    echo -e "  ${GREEN}✓${NC} 虚拟环境已创建: $PYTHON_VER"
else
    echo -e "  ${RED}✗${NC} 虚拟环境不存在"
fi
echo ""

# 3. 检查Python依赖
echo -e "${GREEN}[3/8]${NC} 检查Python依赖..."
if ./venv/bin/pip list | grep -q "playwright"; then
    echo -e "  ${GREEN}✓${NC} 依赖已安装"
else
    echo -e "  ${RED}✗${NC} 依赖未安装"
fi
echo ""

# 4. 检查Playwright浏览器
echo -e "${GREEN}[4/8]${NC} 检查Playwright浏览器..."
if ./venv/bin/playwright install --help > /dev/null 2>&1; then
    if [ -d "$HOME/.cache/ms-playwright" ]; then
        echo -e "  ${GREEN}✓${NC} Playwright浏览器已安装"
    else
        echo -e "  ${YELLOW}△${NC} Playwright已安装但浏览器未下载"
    fi
else
    echo -e "  ${RED}✗${NC} Playwright未安装"
fi
echo ""

# 5. 检查配置文件
echo -e "${GREEN}[5/8]${NC} 检查配置文件..."
if [ -f "config/config.yaml" ]; then
    echo -e "  ${GREEN}✓${NC} 配置文件存在"
    
    # 检查关键配置
    if grep -q "email_address:" config/config.yaml && \
       grep -q "app_password:" config/config.yaml && \
       grep -q "api_key:" config/config.yaml; then
        echo -e "  ${GREEN}✓${NC} 配置文件包含必要信息"
    else
        echo -e "  ${YELLOW}△${NC} 配置文件可能缺少必要信息"
    fi
else
    echo -e "  ${RED}✗${NC} 配置文件不存在"
fi
echo ""

# 6. 检查脚本文件
echo -e "${GREEN}[6/8]${NC} 检查脚本文件..."
SCRIPTS_OK=true
for script in run.sh stop.sh status.sh; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            echo -e "  ${GREEN}✓${NC} $script (可执行)"
        else
            echo -e "  ${YELLOW}△${NC} $script (不可执行)"
            SCRIPTS_OK=false
        fi
    else
        echo -e "  ${RED}✗${NC} $script (不存在)"
        SCRIPTS_OK=false
    fi
done
echo ""

# 7. 检查运行状态
echo -e "${GREEN}[7/8]${NC} 检查运行状态..."
PID=$(pgrep -f "python.*main.py")
if [ -n "$PID" ]; then
    echo -e "  ${GREEN}✓${NC} 程序正在运行 (PID: $PID)"
    echo -e "  运行时间: $(ps -o etime= -p $PID | tr -d ' ')"
else
    echo -e "  ${YELLOW}△${NC} 程序未运行"
fi
echo ""

# 8. 检查日志
echo -e "${GREEN}[8/8]${NC} 检查日志..."
if [ -f "logs/sentiment_monitor.log" ]; then
    LOG_SIZE=$(du -h logs/sentiment_monitor.log | cut -f1)
    echo -e "  ${GREEN}✓${NC} 日志文件存在 (大小: $LOG_SIZE)"
    echo ""
    echo "  最近的5条日志:"
    echo "  ----------------------------------------"
    tail -5 logs/sentiment_monitor.log | while read line; do
        echo "  $line"
    done
else
    echo -e "  ${YELLOW}△${NC} 日志文件不存在"
fi
echo ""

echo "=========================================="
echo "  部署状态检查完成"
echo "=========================================="
echo ""
echo "如果程序未运行，执行以下命令启动:"
echo "  ./run.sh"
echo ""
echo "查看详细状态:"
echo "  ./status.sh"
echo "=========================================="
