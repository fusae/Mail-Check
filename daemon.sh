#!/bin/bash
# 舆情监控守护进程脚本

SCRIPT_DIR="/Users/jamesyu/Documents/Opencode/Mail_Check"
LOG_FILE="$SCRIPT_DIR/logs/daemon.log"
PID_FILE="$SCRIPT_DIR/monitor.pid"
TMUX_SESSION="monitor"

cd "$SCRIPT_DIR"

# 创建日志目录
mkdir -p logs

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# 停止现有进程
stop_existing() {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            COMM=$(ps -p "$OLD_PID" -o comm= | tr -d ' ')
            log "停止现有进程 (PID: $OLD_PID, COMM: $COMM)..."
            kill "$OLD_PID"
            sleep 2
        fi
    fi

    # 兜底：按进程命令清理残留监控程序（绝对/相对路径）
    if pgrep -f "$SCRIPT_DIR/src/main.py" > /dev/null 2>&1 || pgrep -f "src/main.py" > /dev/null 2>&1; then
        log "清理残留监控进程..."
        pkill -f "$SCRIPT_DIR/src/main.py" 2>/dev/null
        pkill -f "src/main.py" 2>/dev/null
        sleep 2
    fi

    # 清理 tmux 会话
    /opt/homebrew/bin/tmux kill-session -t "$TMUX_SESSION" 2>/dev/null
}

# 启动监控程序
start_monitor() {
    log "启动舆情监控程序..."

    # 使用 tmux 后台运行
    /opt/homebrew/bin/tmux new -s "$TMUX_SESSION" -d "cd $SCRIPT_DIR && source venv/bin/activate && python3 $SCRIPT_DIR/src/main.py"

    # 获取监控程序的 PID（排除tmux本身）
    MONITOR_PID=""
    for _ in {1..10}; do
        MONITOR_PID=$(pgrep -f "$SCRIPT_DIR/src/main.py" | while read -r pid; do
            comm=$(ps -p "$pid" -o comm= | tr -d ' ')
            if [ "$comm" != "tmux" ]; then
                echo "$pid"
                break
            fi
        done)
        if [ -n "$MONITOR_PID" ]; then
            break
        fi
        sleep 1
    done

    if [ -n "$MONITOR_PID" ]; then
        log "程序已启动，PID: $MONITOR_PID"
        echo "$MONITOR_PID" > "$PID_FILE"
        log "守护进程已记录: $PID_FILE"
        log "使用 'tail -f $SCRIPT_DIR/logs/sentiment_monitor.log' 查看程序日志"
    else
        log "错误：无法获取监控程序 PID"
        return 1
    fi
}

# 检查程序状态
check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✓ 程序正在运行 (PID: $PID)"
            echo "  查看日志: tail -f $SCRIPT_DIR/logs/sentiment_monitor.log"
            echo "  连接会话: tmux attach -t $TMUX_SESSION"
            echo "  停止程序: $0 stop"
            return 0
        else
            echo "✗ PID文件存在但进程不存在"
            rm "$PID_FILE"
            return 1
        fi
    else
        echo "✗ 程序未运行"
        return 1
    fi
}

# 主逻辑
case "$1" in
    start)
        log "收到启动命令..."
        stop_existing
        start_monitor
        log "启动完成"
        ;;

    stop)
        log "收到停止命令..."
        stop_existing
        if [ -f "$PID_FILE" ]; then
            rm "$PID_FILE"
        fi
        log "程序已停止"
        ;;

    restart)
        log "收到重启命令..."
        stop_existing
        sleep 1
        start_monitor
        log "重启完成"
        ;;

    status)
        check_status
        ;;

    logs)
        echo "查看守护进程日志:"
        tail -30 "$LOG_FILE"
        ;;

    *)
        echo "舆情监控守护进程"
        echo ""
        echo "用法: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "命令:"
        echo "  start   - 启动监控程序"
        echo "  stop    - 停止监控程序"
        echo "  restart - 重启监控程序"
        echo "  status  - 查看程序状态"
        echo "  logs    - 查看守护进程日志"
        ;;
esac
