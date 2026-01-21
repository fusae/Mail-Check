#!/bin/bash
# 舆情监控日志查看快捷脚本

case "$1" in
  live)
    echo "实时查看日志..."
    tail -f logs/sentiment_monitor.log
    ;;
  recent)
    echo "查看最近 50 行日志..."
    tail -50 logs/sentiment_monitor.log
    ;;
  errors)
    echo "查看所有错误..."
    grep -i "error\|exception\|traceback" logs/sentiment_monitor.log
    ;;
  negative)
    echo "查看负面舆情记录..."
    grep "发现负面舆情" logs/sentiment_monitor.log
    ;;
  hospitals)
    echo "查看医院名称提取..."
    grep "提取到医院名称" logs/sentiment_monitor.log
    ;;
  status)
    echo "查看程序运行状态..."
    tail -10 logs/sentiment_monitor.log
    ;;
  *)
    echo "用法: ./log.sh [选项]"
    echo ""
    echo "选项:"
    echo "  live    - 实时查看日志"
    echo "  recent  - 查看最近 50 行"
    echo "  errors  - 查看所有错误"
    echo "  negative- 查看负面舆情记录"
    echo "  hospitals- 查看医院名称提取"
    echo "  status  - 查看程序运行状态"
    ;;
esac
