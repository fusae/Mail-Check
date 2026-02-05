#!/bin/bash
#
# Git 版本回滚（简化版）
# 依赖 Git 进行代码回滚，只处理数据库和配置文件
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
BACKUP_DIR="${BACKUP_DIR:-./backups}"

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

# 检查 Git 仓库
check_git() {
    if [ ! -d ".git" ]; then
        log_error "当前目录不是 Git 仓库"
        log_info "如果还没初始化 Git，请先运行:"
        echo "  git init"
        echo "  git add ."
        echo "  git commit -m 'Initial commit'"
        exit 1
    fi
}

# 备份数据库和配置（这些不在 git 里）
backup_data() {
    log_info "备份数据库和配置文件..."

    mkdir -p "$BACKUP_DIR"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)

    log_warn "当前使用MySQL，数据库备份请使用mysqldump"

    # 备份配置文件
    if [ -f "config/config.yaml" ]; then
        cp config/config.yaml "$BACKUP_DIR/config_$TIMESTAMP.yaml"
        log_success "配置文件备份: $BACKUP_DIR/config_$TIMESTAMP.yaml"
    fi
}

# 显示 Git 提交历史
show_commits() {
    log_info "Git 提交历史:"
    echo ""
    git log --oneline -10
    echo ""
}

# 停止服务
stop_services() {
    log_info "停止服务..."

    PIDS=$(ps -eo pid,command | grep "src/main.py" | grep -v grep | awk '{print $1}')
    for pid in $PIDS; do
        kill $pid 2>/dev/null || true
    done

    API_PID=$(pgrep -f "api_server.py")
    if [ -n "$API_PID" ]; then
        kill $API_PID 2>/dev/null || true
    fi

    sleep 2
    log_success "服务已停止"
}

# Git 回滚
git_rollback() {
    COMMIT=$1

    log_info "回滚到提交: $COMMIT"

    # 确认操作
    read -p "确认回滚到此版本? (y/n): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        log_warn "已取消回滚"
        exit 0
    fi

    # 先备份当前数据和配置
    backup_data

    # Git 回滚
    log_info "执行 Git 回滚..."
    git reset --hard $COMMIT

    log_success "代码已回滚"
}

# 恢复数据库
restore_database() {
    log_info "恢复数据库..."

    DB_BACKUPS=$(ls -t "$BACKUP_DIR"/database_*.db 2>/dev/null || true)

    if [ -z "$DB_BACKUPS" ]; then
        log_warn "没有找到数据库备份"
        return
    fi

    echo "可用的数据库备份:"
    INDEX=1
    for db_backup in $DB_BACKUPS; do
        echo "  [$INDEX] $(basename $db_backup)"
        INDEX=$((INDEX + 1))
    done
    echo ""

    log_warn "当前使用MySQL，请通过mysqldump备份文件手动恢复数据库"
}

# 重启服务
restart_services() {
    log_info "重启服务..."

    if [ -f "start_all.sh" ]; then
        ./start_all.sh
    elif [ -f "run.sh" ]; then
        ./run.sh --daemon
    else
        log_error "未找到启动脚本"
    fi
}

# 主函数
main() {
    echo "=================================================================="
    echo "            Git 版本回滚"
    echo "=================================================================="
    echo ""

    check_git

    # 显示提交历史
    show_commits

    # 选择提交
    read -p "输入要回滚的 commit hash 或 HEAD~N: " commit

    if [ -z "$commit" ]; then
        log_error "请输入有效的 commit hash"
        exit 1
    fi

    echo ""
    log_warn "即将回滚到: $commit"
    echo ""

    # 执行回滚
    stop_services
    git_rollback "$commit"

    echo ""
    read -p "是否需要恢复数据库? (y/n): " restore_db
    if [ "$restore_db" == "y" ] || [ "$restore_db" == "Y" ]; then
        restore_database
    fi

    echo ""
    read -p "是否需要重启服务? (y/n): " restart
    if [ "$restart" == "y" ] || [ "$restart" == "Y" ]; then
        restart_services
    fi

    echo ""
    echo "=================================================================="
    log_success "回滚完成！"
    echo "=================================================================="
    echo ""
    echo "当前 Git 版本:"
    git log --oneline -1
    echo ""
    echo "数据库和配置文件备份位置: $BACKUP_DIR"
    echo "=================================================================="
}

main
