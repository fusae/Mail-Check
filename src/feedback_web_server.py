#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反馈链接服务
用于群机器人场景的外部反馈入口
"""

import hashlib
import hmac
import os
import re
import sqlite3
import time
from datetime import datetime

from flask import Flask, request
import yaml


app = Flask(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)


def load_config():
    config_path = os.path.join(project_root, 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


config = load_config()
feedback_config = config.get('feedback', {})
DB_PATH = config.get('runtime', {}).get(
    'database_path',
    os.path.join(project_root, 'data', 'processed_emails.db')
)


def init_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS negative_sentiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sentiment_id TEXT,
            hospital_name TEXT,
            title TEXT,
            source TEXT,
            content TEXT,
            reason TEXT,
            severity TEXT,
            processed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

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

    _ensure_column(cursor, 'negative_sentiments', 'content', 'TEXT')
    conn.commit()
    conn.close()


def _ensure_column(cursor, table_name, column_name, column_def):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


def verify_signature(sentiment_id, ts, sig):
    secret = feedback_config.get('link_secret', '')
    if not secret:
        return False

    message = f"{sentiment_id}:{ts}".encode('utf-8')
    expected = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig or ''):
        return False

    expiry = int(feedback_config.get('link_expiry_seconds', 7 * 24 * 3600))
    if expiry <= 0:
        return True

    try:
        ts_int = int(ts)
    except (TypeError, ValueError):
        return False

    return (time.time() - ts_int) <= expiry


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


def delete_negative_sentiment(sentiment_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM negative_sentiments WHERE sentiment_id = ?', (sentiment_id,))
    conn.commit()
    conn.close()


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


@app.route('/feedback', methods=['GET'])
def feedback_form():
    sentiment_id = request.args.get('sentiment_id', '')
    ts = request.args.get('ts', '')
    sig = request.args.get('sig', '')

    if not verify_signature(sentiment_id, ts, sig):
        return "Invalid or expired link.", 403

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <title>舆情反馈</title>
  <style>
    body {{ font-family: Arial, sans-serif; padding: 24px; }}
    .container {{ max-width: 520px; margin: 0 auto; }}
    textarea {{ width: 100%; height: 120px; }}
    .btn {{ padding: 10px 16px; margin-right: 8px; }}
  </style>
</head>
<body>
  <div class="container">
    <h3>舆情反馈</h3>
    <p>舆情ID: {sentiment_id}</p>
    <form method="post" action="/feedback">
      <input type="hidden" name="sentiment_id" value="{sentiment_id}">
      <input type="hidden" name="ts" value="{ts}">
      <input type="hidden" name="sig" value="{sig}">
      <label>补充说明（可选）：</label><br>
      <textarea name="feedback_text" placeholder="例如：误报，价格单与医院无关"></textarea><br><br>
      <button class="btn" type="submit" name="judgment" value="false">误判舆情</button>
      <button class="btn" type="submit" name="judgment" value="true">确认负面</button>
    </form>
  </div>
</body>
</html>
"""


@app.route('/feedback', methods=['POST'])
def submit_feedback():
    sentiment_id = request.form.get('sentiment_id', '')
    ts = request.form.get('ts', '')
    sig = request.form.get('sig', '')
    judgment = request.form.get('judgment', '')
    feedback_text = (request.form.get('feedback_text') or '').strip()

    if not verify_signature(sentiment_id, ts, sig):
        return "Invalid or expired link.", 403

    if judgment not in ('true', 'false'):
        return "Invalid feedback.", 400

    feedback_judgment = (judgment == 'true')
    feedback_type = 'true_positive' if feedback_judgment else 'false_positive'
    user_id = request.remote_addr or 'web'

    feedback_id = save_feedback({
        'sentiment_id': sentiment_id,
        'feedback_judgment': feedback_judgment,
        'feedback_type': feedback_type,
        'feedback_text': feedback_text or f"web_feedback:{feedback_type}",
        'user_id': user_id
    })

    if not feedback_judgment:
        delete_negative_sentiment(sentiment_id)
        rules = extract_rule_candidates(feedback_text)
        save_feedback_rules(feedback_id, rules, 'exclude')

    return "已收到反馈，感谢！"


if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5002, debug=False)
