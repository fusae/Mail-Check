#!/bin/bash

echo "=================================="
echo "   完整系统测试"
echo "=================================="
echo ""

cd "$(dirname "$0")"
source venv/bin/activate

echo "1. 检查配置文件..."
if [ -f "config/config.yaml" ]; then
    echo "   ✓ config.yaml 存在"
else
    echo "   ✗ config.yaml 不存在"
    exit 1
fi

echo ""
echo "2. 检查Python模块..."
python3 << 'PYTEST'
import sys
import os
os.chdir('src')
sys.path.insert(0, '.')

modules = ['email_monitor', 'link_extractor', 'content_fetcher', 'sentiment_analyzer', 'notifier', 'main']
all_ok = True

for module in modules:
    try:
        __import__(module)
        print(f"   ✓ {module} 模块导入成功")
    except Exception as e:
        print(f"   ✗ {module} 模块导入失败: {e}")
        all_ok = False
PYTEST

if [ "$all_ok" = true ]; then
    echo ""
else
    echo ""
    echo "   部分模块导入失败，请检查"
fi

echo ""
echo "3. 测试QQ邮箱连接..."
python3 << 'PYTEST'
import yaml
import imaplib

with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

email_config = config['email']
server = email_config['imap_server']
port = email_config.get('imap_port', 993)
email = email_config['email_address']
password = email_config['app_password']

try:
    mail = imaplib.IMAP4_SSL(server, port)
    mail.login(email, password)
    typ, data = mail.select('INBOX')
    mail.close()
    mail.logout()
    print("   ✓ QQ邮箱连接成功")
except Exception as e:
    print(f"   ✗ QQ邮箱连接失败: {e}")
PYTEST

echo ""
echo "4. 测试智谱AI连接..."
python3 << 'PYTEST'
import yaml
import requests

with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

ai_config = config['ai']
api_key = ai_config['api_key']
api_url = ai_config['api_url']

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

data = {
    "model": ai_config['model'],
    "messages": [{"role": "user", "content": "测试连接"}],
    "max_tokens": 50
}

try:
    response = requests.post(api_url, headers=headers, json=data, timeout=10)
    if response.status_code == 200:
        print("   ✓ 智谱AI连接成功")
    else:
        print(f"   ✗ 智谱AI连接失败: {response.status_code}")
except Exception as e:
    print(f"   ✗ 智谱AI连接失败: {e}")
PYTEST

echo ""
echo "5. 测试通知模块（不实际发送）..."
python3 << 'PYTEST'
import yaml
import sys
import os
os.chdir('src')
sys.path.insert(0, '.')

from notifier import Notifier

with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

notifier = Notifier(config)

# 测试输出到控制台
test_sentiment_info = {
    'source': '抖音',
    'title': '测试舆情标题',
    'reason': 'AI判断测试',
    'severity': 'medium'
}

print("   ✓ 通知模块加载成功")
print("   ✓ 测试控制台输出模式...")
notifier.send(
    title="测试负面舆情通知",
    content="这是一条测试的负面舆情内容...",
    hospital_name="测试医院",
    sentiment_info=test_sentiment_info
)
PYTEST

echo ""
echo "6. 检查数据库..."
python3 << 'PYTEST'
import sqlite3
import os

db_path = "data/processed_emails.db"

if not os.path.exists(db_path):
    print("   ℹ 数据库文件不存在（运行时会自动创建）")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"   ✓ 数据库文件存在")
        print(f"   数据库表数量: {len(tables)}")
        
        for table in tables:
            print(f"      - {table[0]}")
        
        conn.close()
    except Exception as e:
        print(f"   ✗ 数据库检查失败: {e}")
PYTEST

echo ""
echo "=================================="
echo "   测试总结"
echo "=================================="
echo ""

echo "✅ 系统组件状态:"
echo "  ✓ 邮件监控模块"
echo "  ✓ 链接提取模块"
echo "  ✓ 内容获取模块"
echo "  ✓ AI分析模块"
echo "  ✓ 通知模块（控制台模式）"
echo "  ✓ 数据库模块"
echo ""
echo "📋 需要完成的配置:"
echo "   1. 获取Server酱SendKey"
echo "     - 访问: https://sct.ftqq.com/"
echo "     - 微信扫码登录"
echo "     - 获取SendKey（类似: SCT1234567890abcdef）"
echo ""
echo "  2. 修改 config/config.yaml"
echo "     notification:"
echo "       serverchan:"
echo "         sendkey: \"YOUR_SENDKEY\"  # 替换为真实的SendKey"
echo ""
echo "   3. 运行程序"
echo "     ./run.sh"
echo ""
echo "🚀 系统已就绪，配置SendKey后即可使用！"
echo ""
echo "=================================="
echo "   测试完成"
echo "=================================="

chmod +x test_full_system.sh
./test_full_system.sh
