#!/bin/bash

echo "=================================="
echo "   舆情监控系统测试"
echo "=================================="
echo ""

cd /Users/jamesyu/Documents/Opencode/Mail_Check
source venv/bin/activate

echo "1. 检查配置文件..."
if [ -f "config/config.yaml" ]; then
    echo "   ✓ 配置文件存在"
    echo "   Gmail: $(grep email_address config/config.yaml | awk '{print $2}')"
else
    echo "   ✗ 配置文件不存在"
    exit 1
fi

echo ""
echo "2. 检查Python模块..."
python3 << 'PYTEST'
import sys
try:
    import yaml
    import requests
    import logging
    from playwright.sync_api import sync_playwright
    print("   ✓ 所有依赖模块可用")
except ImportError as e:
    print(f"   ✗ 模块导入失败: {e}")
    sys.exit(1)
PYTEST

echo ""
echo "3. 检查Playwright浏览器..."
python3 << 'PYTEST'
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        print("   ✓ Chromium浏览器可用")
        browser.close()
except Exception as e:
    print(f"   ✗ 浏览器启动失败: {e}")
    exit(1)
PYTEST

echo ""
echo "4. 测试智谱AI连接..."
python3 << 'PYTEST'
import requests
import yaml

with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

api_key = config['ai']['api_key']
url = config['ai']['api_url']

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

data = {
    "model": config['ai']['model'],
    "messages": [{"role": "user", "content": "测试连接"}],
    "max_tokens": 50
}

try:
    response = requests.post(url, headers=headers, json=data, timeout=10)
    if response.status_code == 200:
        print("   ✓ 智谱AI连接成功")
    else:
        print(f"   ✗ AI连接失败: {response.status_code}")
except Exception as e:
    print(f"   ✗ AI连接异常: {e}")
PYTEST

echo ""
echo "5. 检查Gmail连接..."
python3 << 'PYTEST'
import yaml
import imaplib

with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

email = config['email']['email_address']
password = config['email']['app_password']
server = config['email']['imap_server']

try:
    mail = imaplib.IMAP4_SSL(server)
    mail.login(email, password)
    mail.select('INBOX')
    print("   ✓ Gmail连接成功")
    
    # 搜索邮件
    status, messages = mail.search(None, 'UNSEEN', f'(FROM "{config["email"]["rules"]["sender"]}")')
    count = len(messages[0].split()) if status == 'OK' else 0
    print(f"   找到 {count} 封新邮件")
    
    mail.close()
    mail.logout()
except Exception as e:
    print(f"   ✗ Gmail连接失败: {e}")
PYTEST

echo ""
echo "=================================="
echo "   测试完成"
echo "=================================="
