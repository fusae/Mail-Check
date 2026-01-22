#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信回调服务器
接收企业微信消息并处理用户反馈
"""

import hashlib
import logging
import os
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime

from flask import Flask, request
import yaml

from wechat_api import WeChatWorkAPI


app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)


def load_config():
    config_path = os.path.join(project_root, 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


config = load_config()
wechat_config = config.get('notification', {}).get('wechat_work', {})
wechat_api = WeChatWorkAPI(wechat_config)

DB_PATH = config.get('runtime', {}).get(
    'database_path',
    os.path.join(project_root, 'data', 'processed_emails.db')
)


def init_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sentiment_id TEXT,
            feedback_judgment BOOLEAN,
            feedback_type TEXT,
            feedback_text TEXT,
            user_id TEXT,
            feedback_time TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sentiment_id TEXT,
            user_id TEXT,
            sent_time TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_feedback_queue_user_status
        ON feedback_queue (user_id, status, sent_time)
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT,
            rule_type TEXT,
            action TEXT,
            confidence REAL,
            enabled INTEGER DEFAULT 1,
            source_feedback_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("反馈数据库初始化完成")


def parse_feedback(text):
    false_keywords = ['误报', '不是负面', '不算负面', '误判', '误判舆情', '非负面', '正常', '中性', '正面', '没问题']
    true_keywords = ['确认', '是负面', '正确', '严重']

    text_lower = text.lower()
    if any(kw in text_lower for kw in false_keywords):
        return False, 'false_positive'
    if any(kw in text_lower for kw in true_keywords):
        return True, 'true_positive'
    return None, 'unknown'


def extract_sentiment_id(text):
    match = re.search(r'\b(\d{8,})\b', text)
    return match.group(1) if match else None


def extract_rule_candidates(text):
    rules = []
    if not text:
        return rules

    explicit_patterns = []
    keyword_match = re.search(r'(关键词|关键字|排除|规则)[:：]\s*(.+)', text)
    if keyword_match:
        explicit_patterns.append(keyword_match.group(2))

    quoted = re.findall(r'[“"《](.+?)[”"》]', text)
    explicit_patterns.extend(quoted)

    candidates = []
    for raw in explicit_patterns:
        parts = re.split(r'[，,、;；\s]+', raw)
        for part in parts:
            term = part.strip()
            if 2 <= len(term) <= 20:
                candidates.append(term)

    for term in candidates:
        rules.append({
            'pattern': term,
            'rule_type': 'keyword',
            'confidence': 0.9
        })

    return rules


def get_pending_sentiment(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT sentiment_id FROM feedback_queue
        WHERE user_id = ? AND status = 'pending'
        ORDER BY sent_time DESC
        LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute('''
            SELECT sentiment_id FROM feedback_queue
            WHERE user_id = '@all' AND status = 'pending'
            ORDER BY sent_time DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()

    if not row:
        cursor.execute('''
            SELECT sentiment_id FROM feedback_queue
            WHERE status = 'pending'
            ORDER BY sent_time DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()

    conn.close()
    return row['sentiment_id'] if row else None


def mark_feedback_queue(sentiment_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE feedback_queue
        SET status = 'processed'
        WHERE sentiment_id = ? AND user_id = ? AND status = 'pending'
    ''', (sentiment_id, user_id))
    if cursor.rowcount == 0:
        cursor.execute('''
            UPDATE feedback_queue
            SET status = 'processed'
            WHERE sentiment_id = ? AND user_id = '@all' AND status = 'pending'
        ''', (sentiment_id,))
    conn.commit()
    conn.close()


def save_feedback(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sentiment_feedback (
            sentiment_id, feedback_judgment, feedback_type,
            feedback_text, user_id, feedback_time
        ) VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        data['sentiment_id'],
        data['feedback_judgment'],
        data['feedback_type'],
        data['feedback_text'],
        data['user_id'],
        datetime.now().isoformat()
    ))
    feedback_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return feedback_id


def save_feedback_rules(feedback_id, rules, action):
    if not rules:
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for rule in rules:
        cursor.execute('''
            INSERT INTO feedback_rules (
                pattern, rule_type, action, confidence, enabled, source_feedback_id
            ) VALUES (?, ?, ?, ?, 1, ?)
        ''', (
            rule.get('pattern'),
            rule.get('rule_type', 'keyword'),
            action,
            rule.get('confidence', 0.5),
            feedback_id
        ))
    conn.commit()
    conn.close()


def delete_negative_sentiment(sentiment_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM negative_sentiments WHERE sentiment_id = ?', (sentiment_id,))
    conn.commit()
    conn.close()


@app.route('/wechat/callback', methods=['GET'])
def verify_url():
    msg_signature = request.args.get('msg_signature', '')
    timestamp = request.args.get('timestamp', '')
    nonce = request.args.get('nonce', '')
    echostr = request.args.get('echostr', '')

    decrypted = wechat_api.verify_signature(msg_signature, timestamp, nonce, echostr)
    if decrypted:
        return decrypted
    return 'Verification failed', 403


@app.route('/wechat/callback', methods=['POST'])
def receive_message():
    try:
        msg_signature = request.args.get('msg_signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')

        xml_body = request.data.decode('utf-8')
        root = ET.fromstring(xml_body)
        encrypted = root.findtext('Encrypt') or ''

        if not wechat_api.check_signature(msg_signature, timestamp, nonce, encrypted):
            logger.error("签名验证失败")
            return "Invalid signature", 403

        msg = wechat_api.decrypt_message(encrypted)
        msg_type = msg.get('MsgType')
        from_user = msg.get('FromUserName')

        logger.info(f"收到消息: type={msg_type}, from={from_user}")

        if msg_type == 'text':
            handle_text_message(msg)
        elif msg_type == 'event':
            handle_event_message(msg)

        return make_response('ok')
    except Exception as e:
        logger.error(f"处理消息失败: {e}", exc_info=True)
        return make_response('ok')


def handle_text_message(msg):
    user_id = msg.get('FromUserName')
    content = (msg.get('Content') or '').strip()

    judgment, feedback_type = parse_feedback(content)
    if judgment is None:
        send_reply(user_id, "无法理解反馈，请回复“误报/确认”即可。")
        return

    sentiment_id = extract_sentiment_id(content)
    if not sentiment_id:
        sentiment_id = get_pending_sentiment(user_id)

    if not sentiment_id:
        send_reply(user_id, "未找到可反馈的舆情，请稍后再试。")
        return

    feedback_id = save_feedback({
        'sentiment_id': sentiment_id,
        'feedback_judgment': judgment,
        'feedback_type': feedback_type,
        'feedback_text': content,
        'user_id': user_id
    })
    mark_feedback_queue(sentiment_id, user_id)

    if judgment is False:
        delete_negative_sentiment(sentiment_id)
        rules = extract_rule_candidates(content)
        save_feedback_rules(feedback_id, rules, 'exclude')

    send_reply(user_id, "✅ 已收到反馈并记录，谢谢！")


def handle_event_message(msg):
    event = msg.get('Event')
    if event not in ('click', 'template_card_event'):
        return

    event_key = msg.get('EventKey') or msg.get('ButtonKey') or ''
    user_id = msg.get('FromUserName')

    if event_key.startswith('false_positive_'):
        sentiment_id = event_key.split('_', 2)[2]
        feedback_type = 'false_positive'
        judgment = False
    elif event_key.startswith('true_positive_'):
        sentiment_id = event_key.split('_', 2)[2]
        feedback_type = 'true_positive'
        judgment = True
    else:
        return

    save_feedback({
        'sentiment_id': sentiment_id,
        'feedback_judgment': judgment,
        'feedback_type': feedback_type,
        'feedback_text': f"按钮反馈: {event_key}",
        'user_id': user_id
    })
    mark_feedback_queue(sentiment_id, user_id)

    if judgment is False:
        delete_negative_sentiment(sentiment_id)

    send_reply(user_id, "✅ 已收到反馈并记录，谢谢！")


def send_reply(user_id, text):
    try:
        wechat_api.send_text(user_id, text)
    except Exception as e:
        logger.error(f"发送回复失败: {e}", exc_info=True)


def make_response(content):
    timestamp = str(int(time.time()))
    nonce = str(int(time.time() * 1000) % 1000000)
    encrypted = wechat_api.encrypt_message(content)
    signature = hashlib.sha1(''.join(sorted([wechat_api.token, timestamp, nonce, encrypted])).encode('utf-8')).hexdigest()

    response_xml = f"""<xml>
<Encrypt><![CDATA[{encrypted}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""
    return response_xml


if __name__ == '__main__':
    init_database()
    if not wechat_config:
        logger.error("未配置企业微信信息，请检查 config.yaml")
        raise SystemExit(1)

    logger.info("企业微信回调服务启动")
    app.run(host='0.0.0.0', port=5001, debug=False)
