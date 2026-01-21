#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信Webhook服务器
接收企业微信的回调消息并处理用户反馈
"""

from flask import Flask, request, jsonify
import sqlite3
import os
import sys
import logging
from datetime import datetime
from wechat_api import WeChatWorkAPI

# 添加上级目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import yaml

app = Flask(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载配置
def load_config():
    """加载配置"""
    config_path = os.path.join(parent_dir, 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()

# 初始化企业微信API
wechat_api = WeChatWorkAPI(config.get('wechat_work', {}))

# 数据库路径
DB_PATH = os.path.join(parent_dir, 'data', 'processed_emails.db')

# 消息缓存（用于关联回复和原始舆情）
# 格式：{user_id: {msg_id: sentiment_id, ...}}
message_cache = {}

def init_database():
    """初始化数据库"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 创建反馈表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sentiment_id TEXT UNIQUE,
            original_judgment BOOLEAN,
            feedback_judgment BOOLEAN,
            feedback_type TEXT,
            feedback_text TEXT,
            user_id TEXT,
            feedback_time TEXT,
            ai_reason TEXT,
            processed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("数据库初始化完成")

def get_sentiment(sentiment_id):
    """获取舆情信息"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM negative_sentiments
        WHERE sentiment_id = ?
    ''', (sentiment_id,))

    result = cursor.fetchone()
    conn.close()

    return dict(result) if result else None

def get_recent_sentiment(user_id, minutes=10):
    """获取用户最近未反馈的舆情"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    time_threshold = datetime.now().replace(microsecond=0).isoformat()

    cursor.execute('''
        SELECT ns.* FROM negative_sentiments ns
        LEFT JOIN sentiment_feedback sf ON ns.sentiment_id = sf.sentiment_id
        WHERE ns.processed_at >= datetime('now', '-10 minutes')
        AND sf.sentiment_id IS NULL
        ORDER BY ns.processed_at DESC
        LIMIT 1
    ''')

    result = cursor.fetchone()
    conn.close()

    return dict(result) if result else None

def save_feedback(data):
    """保存反馈"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO sentiment_feedback (
                sentiment_id, original_judgment, feedback_judgment,
                feedback_type, feedback_text, user_id, feedback_time, ai_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['sentiment_id'],
            data['original_judgment'],
            data['feedback_judgment'],
            data['feedback_type'],
            data['feedback_text'],
            data['user_id'],
            datetime.now().isoformat(),
            data['ai_reason']
        ))

        conn.commit()
        logger.info(f"反馈已保存: {data['sentiment_id']}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"反馈已存在: {data['sentiment_id']}")
        return False

def parse_feedback(text):
    """解析反馈文本"""
    false_keywords = ['误报', '不是负面', '误判', '非负面', '正常', '中性', '正面']
    true_keywords = ['确认', '是负面', '正确', '严重']

    text_lower = text.lower()

    if any(kw in text_lower for kw in false_keywords):
        return False, 'false_positive'
    elif any(kw in text_lower for kw in true_keywords):
        return True, 'true_positive'
    else:
        return None, 'unknown'

@app.route('/wechat/callback', methods=['GET'])
def verify_url():
    """验证URL有效性（企业微信首次配置时调用）"""
    msg_signature = request.args.get('msg_signature')
    timestamp = request.args.get('timestamp')
    nonce = request.args.get('nonce')
    echostr = request.args.get('echostr')

    logger.info("收到URL验证请求")

    decrypted = wechat_api.verify_signature(msg_signature, timestamp, nonce, echostr)

    if decrypted:
        logger.info("URL验证成功")
        return decrypted
    else:
        logger.error("URL验证失败")
        return 'Verification failed', 403

@app.route('/wechat/callback', methods=['POST'])
def receive_message():
    """接收企业微信消息"""
    try:
        # 获取加密数据
        data = request.get_json()

        encrypted_msg = data.get('Encrypt', '')

        # 解密消息
        msg = wechat_api.decrypt_message(encrypted_msg)

        msg_type = msg.get('MsgType')
        from_user = msg.get('FromUserName')

        logger.info(f"收到消息: type={msg_type}, from={from_user}")

        # 处理文本消息（用户回复）
        if msg_type == 'text':
            return handle_text_message(msg)

        # 处理事件消息（按钮点击等）
        elif msg_type == 'event':
            return handle_event_message(msg)

        else:
            logger.info(f"忽略消息类型: {msg_type}")
            return make_response('ok')

    except Exception as e:
        logger.error(f"处理消息失败: {e}", exc_info=True)
        return make_response('ok')

def handle_text_message(msg):
    """处理文本消息"""
    try:
        user_id = msg.get('FromUserName')
        content = msg.get('Content', '').strip()

        logger.info(f"用户回复: {content}")

        # 解析反馈
        judgment, feedback_type = parse_feedback(content)

        if judgment is None:
            # 无法判断，发送提示
            reply = "无法理解您的反馈，请使用以下格式：\n- 误报，这是正常的XX\n- 确认，确实是负面"
            send_reply(user_id, reply)
            return make_response('ok')

        # 查找对应的舆情
        sentiment = find_sentiment_for_feedback(user_id)

        if not sentiment:
            reply = "未找到相关舆情，请稍后再试"
            send_reply(user_id, reply)
            return make_response('ok')

        # 保存反馈
        feedback_data = {
            'sentiment_id': sentiment['sentiment_id'],
            'original_judgment': True,
            'feedback_judgment': judgment,
            'feedback_type': feedback_type,
            'feedback_text': content,
            'user_id': user_id,
            'ai_reason': sentiment.get('reason', '')
        }

        saved = save_feedback(feedback_data)

        if saved:
            reply = "✅ 收到您的反馈，已记录并用于AI优化\n\n" \
                    "您的反馈将帮助系统更准确地识别舆情。"
        else:
            reply = "该舆情已收到反馈，感谢您的关注"

        send_reply(user_id, reply)

        return make_response('ok')

    except Exception as e:
        logger.error(f"处理文本消息失败: {e}", exc_info=True)
        return make_response('ok')

def handle_event_message(msg):
    """处理事件消息"""
    event = msg.get('Event')

    logger.info(f"收到事件: {event}")

    # 处理按钮点击等事件
    if event == 'click':
        # 按钮点击事件
        event_key = msg.get('EventKey', '')
        from_user = msg.get('FromUserName')

        # 解析事件键
        if event_key.startswith('confirm_'):
            # 确认负面
            sentiment_id = event_key.split('_', 1)[1]
            handle_button_feedback(from_user, sentiment_id, True)
        elif event_key.startswith('false_positive_'):
            # 误报
            sentiment_id = event_key.split('_', 1)[1]
            handle_button_feedback(from_user, sentiment_id, False)

    return make_response('ok')

def handle_button_feedback(user_id, sentiment_id, is_negative):
    """处理按钮反馈"""
    try:
        sentiment = get_sentiment(sentiment_id)

        if not sentiment:
            logger.error(f"舆情不存在: {sentiment_id}")
            return

        feedback_type = 'true_positive' if is_negative else 'false_positive'

        feedback_data = {
            'sentiment_id': sentiment_id,
            'original_judgment': True,
            'feedback_judgment': is_negative,
            'feedback_type': feedback_type,
            'feedback_text': f"通过按钮选择：{'确认负面' if is_negative else '误报'}",
            'user_id': user_id,
            'ai_reason': sentiment.get('reason', '')
        }

        save_feedback(feedback_data)

        reply = "✅ 收到您的反馈，已记录并用于AI优化"
        send_reply(user_id, reply)

    except Exception as e:
        logger.error(f"处理按钮反馈失败: {e}", exc_info=True)

def find_sentiment_for_feedback(user_id):
    """查找用户应该反馈的舆情"""
    # 方法1：从缓存中查找
    if user_id in message_cache:
        # 获取最新的未反馈舆情
        cached = message_cache[user_id]
        for msg_id, sentiment_id in reversed(cached.items()):
            sentiment = get_sentiment(sentiment_id)
            if sentiment:
                return sentiment

    # 方法2：查找最近的舆情
    return get_recent_sentiment(user_id)

def send_reply(user_id, text):
    """发送回复"""
    try:
        result = wechat_api.send_text(user_id, text)
        if result.get('success'):
            logger.info(f"回复发送成功: {user_id}")
        else:
            logger.error(f"回复发送失败: {result}")
    except Exception as e:
        logger.error(f"发送回复失败: {e}", exc_info=True)

def make_response(content):
    """构建响应"""
    # 生成时间戳和随机数
    import time
    import random

    timestamp = str(int(time.time()))
    nonce = str(random.randint(0, 1000000))

    # 构建回复消息
    reply_msg = content

    # 加密消息
    encrypted = wechat_api.encrypt_message(reply_msg)

    # 生成签名
    data = f"{wechat_api.token}{timestamp}{nonce}{encrypted}"
    import hashlib
    signature = hashlib.sha1(data.encode('utf-8')).hexdigest()

    # 构建响应XML
    response_xml = f"""<xml>
<Encrypt><![CDATA[{encrypted}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""

    return response_xml

if __name__ == '__main__':
    # 初始化数据库
    init_database()

    # 检查配置
    if not config.get('wechat_work'):
        logger.error("未配置企业微信信息")
        logger.error("请在 config.yaml 中添加 wechat_work 配置")
        sys.exit(1)

    logger.info("企业微信Webhook服务器启动中...")
    logger.info(f"访问地址: https://43.129.17.66/wechat/callback")

    # 启动服务器
    app.run(host='0.0.0.0', port=5001, debug=False)
