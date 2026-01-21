#!/bin/bash
#
# Mail_Check 一键部署脚本
# 适用于 Ubuntu/Debian/CentOS 系统
#

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 打印分隔线
print_line() {
    echo "=================================================================="
}

# 检查是否为root用户
check_root() {
    if [ "$EUID" -eq 0 ]; then
        log_warn "不建议使用root用户运行此脚本"
        read -p "是否继续? (y/n): " continue_as_root
        if [ "$continue_as_root" != "y" ] && [ "$continue_as_root" != "Y" ]; then
            exit 1
        fi
    fi
}

# 检测系统类型
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VER=$(lsb_release -sr)
    else
        log_error "无法检测操作系统类型"
        exit 1
    fi
    
    log_info "检测到操作系统: $OS $VER"
}

# 检查Python版本
check_python() {
    log_info "检查Python版本..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        log_info "当前Python版本: $PYTHON_VERSION"
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            log_success "Python版本满足要求 (>= 3.8)"
        else
            log_error "Python版本过低，需要 Python 3.8 或更高版本"
            log_info "请升级Python或安装较新版本"
            exit 1
        fi
    else
        log_error "未找到Python3，请先安装Python3"
        exit 1
    fi
}

# 安装系统依赖
install_system_dependencies() {
    log_info "安装系统依赖..."
    
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        log_info "使用 apt 包管理器..."
        sudo apt-get update
        sudo apt-get install -y python3-venv python3-pip curl git
        
        # Playwright 依赖
        log_info "安装 Playwright 浏览器依赖..."
        sudo apt-get install -y \
            libnss3 \
            libnspr4 \
            libdbus-1-3 \
            libatk1.0-0 \
            libatk-bridge2.0-0 \
            libcups2 \
            libdrm2 \
            libxkbcommon0 \
            libxcomposite1 \
            libxdamage1 \
            libxfixes3 \
            libxrandr2 \
            libgbm1 \
            libasound2
            
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        log_info "使用 yum 包管理器..."
        sudo yum install -y python3 python3-pip curl git
        
        # Playwright 依赖
        log_info "安装 Playwright 浏览器依赖..."
        sudo yum install -y \
            nss \
            nspr \
            dbus-libs \
            atk \
            at-spi2-atk \
            cups-libs \
            libdrm \
            libxkbcommon \
            libXcomposite \
            libXdamage \
            libXfixes \
            libXrandr \
            mesa-libgbm \
            alsa-lib
    else
        log_warn "未知操作系统类型，请手动安装系统依赖"
    fi
    
    log_success "系统依赖安装完成"
}

# 创建虚拟环境
create_virtual_env() {
    log_info "创建Python虚拟环境..."
    
    if [ -d "venv" ]; then
        log_warn "虚拟环境已存在，删除旧环境..."
        rm -rf venv
    fi
    
    python3 -m venv venv
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip setuptools wheel
    
    log_success "虚拟环境创建完成"
}

# 安装Python依赖
install_python_dependencies() {
    log_info "安装Python依赖包..."
    
    source venv/bin/activate
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        log_warn "未找到 requirements.txt，手动安装基本依赖..."
        pip install pyyaml requests playwright zhipuai
    fi
    
    log_success "Python依赖安装完成"
}

# 安装Playwright浏览器
install_playwright() {
    log_info "安装Playwright浏览器..."
    
    source venv/bin/activate
    
    # 安装Chromium浏览器
    playwright install chromium
    
    # 安装浏览器依赖
    playwright install-deps chromium
    
    log_success "Playwright浏览器安装完成"
}

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."
    
    mkdir -p logs data config
    
    log_success "目录创建完成"
}

# 配置文件检查
check_config() {
    log_info "检查配置文件..."
    
    if [ ! -f "config/config.yaml" ]; then
        log_error "配置文件不存在: config/config.yaml"
        log_info "请先创建配置文件并填写相关信息"
        exit 1
    fi
    
    # 检查关键配置项
    if ! grep -q "email_address:" config/config.yaml; then
        log_warn "配置文件中可能缺少 email_address 配置"
    fi
    
    if ! grep -q "api_key:" config/config.yaml; then
        log_warn "配置文件中可能缺少 api_key 配置"
    fi
    
    log_success "配置文件检查完成"
}

# 设置权限
set_permissions() {
    log_info "设置文件权限..."
    
    chmod +x run.sh
    chmod +x stop.sh 2>/dev/null || true
    chmod +x status.sh 2>/dev/null || true
    
    log_success "权限设置完成"
}

# 创建停止脚本
create_stop_script() {
    cat > stop.sh << 'EOF'
#!/bin/bash

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# 查找进程ID
PID=$(pgrep -f "python.*main.py")

if [ -n "$PID" ]; then
    echo -e "${GREEN}正在停止舆情监控系统...${NC}"
    kill $PID
    sleep 2
    
    # 检查是否还在运行
    if ps -p $PID > /dev/null; then
        echo -e "${RED}进程未正常停止，强制终止...${NC}"
        kill -9 $PID
    fi
    
    echo -e "${GREEN}舆情监控系统已停止${NC}"
else
    echo -e "${RED}未找到运行中的舆情监控系统${NC}"
fi
EOF
    
    chmod +x stop.sh
    log_success "停止脚本创建完成"
}

# 创建状态查看脚本
create_status_script() {
    cat > status.sh << 'EOF'
#!/bin/bash

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "舆情监控系统状态"
echo "=================================================================="

# 检查进程
PID=$(pgrep -f "python.*main.py")
if [ -n "$PID" ]; then
    echo -e "进程状态: ${GREEN}运行中${NC}"
    echo "进程ID: $PID"
    echo "运行时间: $(ps -o etime= -p $PID | tr -d ' ')"
    echo "内存使用: $(ps -o rss= -p $PID | awk '{print $1/1024 "MB"}')"
else
    echo -e "进程状态: ${RED}未运行${NC}"
fi

echo ""

# 检查日志
if [ -f "logs/sentiment_monitor.log" ]; then
    echo "日志文件: logs/sentiment_monitor.log"
    LOG_SIZE=$(du -h logs/sentiment_monitor.log | cut -f1)
    echo "日志大小: $LOG_SIZE"
    echo ""
    echo "最近5条日志:"
    tail -5 logs/sentiment_monitor.log
else
    echo "日志文件不存在"
fi

echo ""
echo "=================================================================="

# 数据库状态
if [ -f "data/processed_emails.db" ]; then
    DB_SIZE=$(du -h data/processed_emails.db | cut -f1)
    echo -e "数据库: ${GREEN}存在${NC} (大小: $DB_SIZE)"
else
    echo -e "数据库: ${YELLOW}不存在${NC}"
fi
EOF
    
    chmod +x status.sh
    log_success "状态脚本创建完成"
}

# 部署总结
print_summary() {
    print_line
    log_success "部署完成！"
    print_line
    echo ""
    echo "常用命令:"
    echo "  启动服务: ./run.sh"
    echo "  停止服务: ./stop.sh"
    echo "  查看状态: ./status.sh"
    echo "  查看日志: tail -f logs/sentiment_monitor.log"
    echo ""
    echo "下一步操作:"
    echo "  1. 检查配置文件: config/config.yaml"
    echo "  2. 确保配置文件中的邮箱、AI密钥等信息正确"
    echo "  3. 运行测试: ./status.sh"
    echo "  4. 启动服务: ./run.sh"
    echo ""
    print_line
}

# 主函数
main() {
    print_line
    echo "             Mail_Check 舆情监控系统 一键部署"
    print_line
    echo ""
    
    # 执行部署步骤
    check_root
    detect_os
    check_python
    install_system_dependencies
    create_directories
    create_virtual_env
    install_python_dependencies
    install_playwright
    check_config
    create_stop_script
    create_status_script
    set_permissions
    
    # 完成总结
    print_summary
}

# 运行主函数
main