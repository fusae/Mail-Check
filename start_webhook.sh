#!/bin/bash

# 企业微信Webhook服务器启动脚本

cd "$(dirname "$0")"

echo "=================================="
echo "  启动企业微信Webhook服务器"
echo "=================================="
echo ""

# 检查是否在虚拟环境中
if [ ! -d "venv" ]; then
    echo "错误: 虚拟环境不存在"
    echo "请先运行部署脚本"
    exit 1
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 检查Flask是否安装
if ! python -c "import flask" 2>/dev/null; then
    echo "安装Flask..."
    pip install flask
fi

# 检查pycryptodome是否安装
if ! python -c "from Crypto.Cipher import AES" 2>/dev/null; then
    echo "安装pycryptodome..."
    pip install pycryptodome
fi

# 检查配置文件
echo "检查配置文件..."
if ! grep -q "corp_id:" config/config.yaml; then
    echo "警告: 企业应用未配置"
    echo "请在 config/config.yaml 中配置企业微信应用信息"
    echo ""
    echo "需要的配置项："
    echo "  wechat_work:"
    echo "    corp_id: \"企业ID\""
    echo "    agent_id: \"应用ID\""
    echo "    secret: \"应用Secret\""
    echo "    token: \"验证Token\""
    echo "    encoding_aes_key: \"加密密钥\""
    echo ""
fi

# 创建日志目录
mkdir -p logs

# 检查是否已运行
if [ -f "webhook.pid" ]; then
    OLD_PID=$(cat webhook.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "Webhook服务器已在运行 (PID: $OLD_PID)"
        read -p "是否重启? (y/n): " restart_choice
        if [ "$restart_choice" != "y" ] && [ "$restart_choice" != "Y" ]; then
            exit 0
        fi
        echo "停止现有服务..."
        kill $OLD_PID
        sleep 2
    fi
fi

# 启动Webhook服务器
echo ""
echo "启动Webhook服务器..."
nohup python src/wechat_webhook_server.py > logs/webhook.log 2>&1 &
WEB_PID=$!

echo $WEB_PID > webhook.pid

sleep 2

# 检查是否启动成功
if ps -p $WEB_PID > /dev/null; then
    echo "=================================="
    echo "  ✓ Webhook服务器启动成功"
    echo "=================================="
    echo ""
    echo "PID: $WEB_PID"
    echo "日志: logs/webhook.log"
    echo ""
    echo "访问地址:"
    echo "  http://43.129.17.66:5001/wechat/callback"
    echo ""
    echo "管理命令:"
    echo "  停止服务: ./stop_webhook.sh"
    echo "  查看日志: tail -f logs/webhook.log"
    echo "  查看状态: ps -p $(cat webhook.pid)"
    echo ""
    echo "=================================="
    echo ""
    echo "接下来需要配置企业微信："
    echo "1. 登录企业微信管理后台"
    echo "2. 进入应用管理 → 选择你的应用"
    echo "3. 设置接收消息回调URL:"
    echo "   https://43.129.17.66:5001/wechat/callback"
    echo "4. 填写Token和EncodingAESKey"
    echo "5. 保存配置"
    echo ""
else
    echo "=================================="
    echo "  ✗ Webhook服务器启动失败"
    echo "=================================="
    echo ""
    echo "请查看日志:"
    echo "  cat logs/webhook.log"
    echo ""
    rm webhook.pid
    exit 1
fi
