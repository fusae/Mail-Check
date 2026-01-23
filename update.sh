#!/bin/bash
#
# 从 GitHub 更新代码（无需服务器安装 Git）
# 适用于生产环境自动化部署
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
GITHUB_REPO="fusae/Mail-Check"
GITHUB_URL="https://github.com/${GITHUB_REPO}"
DOWNLOAD_URL="${GITHUB_URL}/archive/refs/heads/main.zip"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
PROJECT_ROOT=$(pwd)

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

# 检查是否在项目根目录
check_project_root() {
    if [ ! -f "run.sh" ] && [ ! -f "start_all.sh" ]; then
        log_error "请在项目根目录执行此脚本"
        exit 1
    fi
}

# 备份数据库
backup_database() {
    log_info "备份数据库..."

    mkdir -p "$BACKUP_DIR"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)

    if [ -f "data/processed_emails.db" ]; then
        cp data/processed_emails.db "$BACKUP_DIR/database_$TIMESTAMP.db"
        log_success "数据库备份: $BACKUP_DIR/database_$TIMESTAMP.db"
    else
        log_warn "数据库文件不存在，跳过备份"
    fi
}

# 备份代码
backup_code() {
    log_info "备份当前代码..."

    mkdir -p "$BACKUP_DIR"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    CODE_BACKUP="$BACKUP_DIR/code_$TIMESTAMP"

    # 复制当前代码（排除虚拟环境、数据、日志等）
    mkdir -p "$CODE_BACKUP"
    rsync -av \
        --exclude='venv' \
        --exclude='data/*.db' \
        --exclude='logs' \
        --exclude='backups' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='*.pid' \
        --exclude='.git' \
        ./ "$CODE_BACKUP/" > /dev/null 2>&1 || true

    log_success "代码备份: $CODE_BACKUP"
}

# 停止服务
stop_services() {
    log_info "停止服务..."

    if [ -f "stop_all.sh" ]; then
        ./stop_all.sh > /dev/null 2>&1 || true
    fi

    sleep 2
    log_success "服务已停止"
}

# 从 GitHub 下载最新代码
download_latest() {
    log_info "从 GitHub 下载最新代码..."
    log_info "仓库: $GITHUB_REPO"

    TEMP_DIR=$(mktemp -d)
    ZIP_FILE="$TEMP_DIR/mail_check.zip"

    # 下载代码
    if command -v wget > /dev/null 2>&1; then
        wget -q "$DOWNLOAD_URL" -O "$ZIP_FILE"
    elif command -v curl > /dev/null 2>&1; then
        curl -sL "$DOWNLOAD_URL" -o "$ZIP_FILE"
    else
        log_error "未找到 wget 或 curl，无法下载代码"
        rm -rf "$TEMP_DIR"
        exit 1
    fi

    # 检查下载是否成功
    if [ ! -f "$ZIP_FILE" ] || [ ! -s "$ZIP_FILE" ]; then
        log_error "下载失败，请检查网络连接"
        rm -rf "$TEMP_DIR"
        exit 1
    fi

    # 解压
    unzip -q "$ZIP_FILE" -d "$TEMP_DIR"

    # 获取解压后的目录名
    EXTRACTED_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "Mail-Check-*" | head -n 1)

    if [ -z "$EXTRACTED_DIR" ]; then
        log_error "解压失败"
        rm -rf "$TEMP_DIR"
        exit 1
    fi

    log_success "代码下载完成"
    echo "$EXTRACTED_DIR"
}

# 更新代码
update_code() {
    EXTRACTED_DIR=$1

    log_info "更新代码..."

    # 复制新代码到项目目录（排除虚拟环境和数据）
    rsync -av --delete \
        --exclude='venv' \
        --exclude='data/*.db' \
        --exclude='logs' \
        --exclude='backups' \
        --exclude='*.pid' \
        "$EXTRACTED_DIR/" "$PROJECT_ROOT/" > /dev/null 2>&1

    # 清理临时文件
    rm -rf "$TEMP_DIR"

    log_success "代码更新完成"
}

# 检查并更新依赖
check_dependencies() {
    log_info "检查 Python 依赖..."

    if [ -f "requirements.txt" ] && [ -d "venv" ]; then
        source venv/bin/activate
        log_info "正在安装/更新依赖..."
        if pip install -r requirements.txt; then
            log_success "依赖检查完成"
        else
            log_error "依赖安装失败，请手动安装"
            log_info "手动安装命令: source venv/bin/activate && pip install -r requirements.txt"
        fi
    else
        log_warn "虚拟环境不存在，跳过依赖检查"
    fi
}

# 启动服务
start_services() {
    log_info "启动服务..."

    if [ -f "start_all.sh" ]; then
        ./start_all.sh
    else
        log_error "未找到启动脚本 start_all.sh"
        exit 1
    fi
}

# 查看服务状态
check_status() {
    sleep 2

    if [ -f "status_all.sh" ]; then
        log_info "服务状态:"
        echo ""
        ./status_all.sh
    fi
}

# 回滚功能
rollback() {
    CODE_BACKUP=$1

    log_warn "开始回滚到: $CODE_BACKUP"

    # 恢复代码
    rsync -av --delete \
        --exclude='venv' \
        --exclude='data/*.db' \
        --exclude='logs' \
        --exclude='backups' \
        "$CODE_BACKUP/" "$PROJECT_ROOT/" > /dev/null 2>&1

    log_success "代码已回滚"

    # 重启服务
    if [ -f "start_all.sh" ]; then
        ./start_all.sh
    fi
}

# 主函数
main() {
    echo "=================================================================="
    echo "            从 GitHub 更新代码"
    echo "=================================================================="
    echo ""
    echo "仓库: $GITHUB_REPO"
    echo "下载地址: $DOWNLOAD_URL"
    echo ""

    # 检查环境
    check_project_root

    # 确认更新
    read -p "确认更新代码? (y/n): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        log_warn "已取消更新"
        exit 0
    fi

    # 备份
    echo ""
    backup_database
    backup_code

    # 记录备份路径（用于回滚）
    CODE_BACKUP="$BACKUP_DIR/code_$(date +%Y%m%d_%H%M%S)"

    # 停止服务
    echo ""
    stop_services

    # 下载和更新
    echo ""
    EXTRACTED_DIR=$(download_latest)

    # 更新前再次确认
    echo ""
    log_warn "即将更新代码，旧代码已备份"
    read -p "继续? (y/n): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        log_warn "已取消更新"
        exit 0
    fi

    update_code "$EXTRACTED_DIR"

    # 检查依赖
    echo ""
    check_dependencies

    # 启动服务
    echo ""
    start_services

    # 检查状态
    echo ""
    check_status

    echo ""
    echo "=================================================================="
    log_success "更新完成！"
    echo "=================================================================="
    echo ""
    echo "备份位置:"
    echo "  代码: $CODE_BACKUP"
    echo "  数据库: $BACKUP_DIR/database_$(date +%Y%m%d)_*.db"
    echo ""
    echo "如遇问题，可手动回滚:"
    echo "  ./update.sh --rollback $CODE_BACKUP"
    echo "=================================================================="
}

# 回滚模式
if [ "$1" == "--rollback" ] && [ -n "$2" ]; then
    echo "=================================================================="
    echo "            代码回滚"
    echo "=================================================================="
    echo ""

    check_project_root

    if [ ! -d "$2" ]; then
        log_error "备份目录不存在: $2"
        exit 1
    fi

    # 停止服务
    stop_services

    # 回滚代码
    rollback "$2"

    # 检查状态
    echo ""
    check_status

    echo ""
    log_success "回滚完成！"
    exit 0
fi

# 正常更新模式
main
