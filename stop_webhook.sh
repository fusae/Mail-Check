#!/bin/bash

# 停止企业微信Webhook服务器

cd "$(dirname "$0")"

if [ ! -f "webhook.pid" ]; then
    echo "Webhook服务器未运行"
    exit 0
fi

PID=$(cat webhook.pid)

if ! ps -p $PID > /dev/null 2>&1; then
    echo "Webhook服务器已停止"
    rm webhook.pid
    exit 0
fi

echo "正在停止Webhook服务器 (PID: $PID)..."
kill $PID

sleep 2

if ps -p $PID > /dev/null 2>&1; then
    echo "强制停止..."
    kill -9 $PID
fi

rm webhook.pid
echo "Webhook服务器已停止"
