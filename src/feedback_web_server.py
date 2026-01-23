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
feedback_config = config.get('runtime', {}).get('feedback', {})
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


def get_sentiment_info(sentiment_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT hospital_name, title, source, content, reason, severity
        FROM negative_sentiments
        WHERE sentiment_id = ?
    ''', (sentiment_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'hospital_name': result[0],
            'title': result[1],
            'source': result[2],
            'content': result[3],
            'reason': result[4],
            'severity': result[5]
        }
    return None


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

    sentiment_info = get_sentiment_info(sentiment_id)
    
    if sentiment_info:
        hospital_name = sentiment_info['hospital_name'] or ''
        title = sentiment_info['title'] or ''
        source = sentiment_info['source'] or ''
        content = sentiment_info['content'] or ''
        reason = sentiment_info['reason'] or ''
        severity = sentiment_info['severity'] or 'medium'
        
        severity_colors = {
            'high': '#ff4d4f',
            'medium': '#faad14',
            'low': '#52c41a'
        }
        severity_label = {
            'high': '高',
            'medium': '中',
            'low': '低'
        }
        severity_color = severity_colors.get(severity, '#faad14')
        severity_text = severity_label.get(severity, '中')
        
        info_section = f"""
        <div class="info-section">
          <h4>舆情详情</h4>
          <div class="info-row">
            <span class="label">舆情ID：</span>
            <span class="value">{sentiment_id}</span>
          </div>
          <div class="info-row">
            <span class="label">医院：</span>
            <span class="value">{hospital_name}</span>
          </div>
          <div class="info-row">
            <span class="label">来源：</span>
            <span class="value">{source}</span>
          </div>
          <div class="info-row">
            <span class="label">严重程度：</span>
            <span class="value" style="color: {severity_color}; font-weight: bold;">{severity_text}</span>
          </div>
          <div class="info-row">
            <span class="label">标题：</span>
            <span class="value">{title}</span>
          </div>
          <div class="info-row">
            <span class="label">内容：</span>
            <span class="value">{content}</span>
          </div>
          <div class="info-row">
            <span class="label">AI判断：</span>
            <span class="value">{reason}</span>
          </div>
        </div>
        """
    else:
        info_section = f"""
        <div class="info-section" style="background: #fffbe6; border-color: #ffe58f;">
          <h4>舆情详情</h4>
          <p style="color: #faad14;">⚠️ 测试数据（未存入数据库）</p>
          <div class="info-row">
            <span class="label">舆情ID：</span>
            <span class="value">{sentiment_id}</span>
          </div>
          <div class="info-row">
            <span class="label">说明：</span>
            <span class="value">此舆情数据为测试生成，未存入数据库。如需测试完整功能，请通过实际监控产生舆情数据。</span>
          </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>舆情反馈</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; background: #f5f5f5; margin: 0; }}
    .container {{ max-width: 640px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 32px; }}
    h3 {{ margin-top: 0; color: #333; border-bottom: 2px solid #1890ff; padding-bottom: 12px; }}
    h4 {{ margin: 0 0 16px 0; color: #1890ff; font-size: 16px; }}
    .info-section {{ background: #f0f7ff; border: 1px solid #d6e4ff; border-radius: 6px; padding: 16px; margin-bottom: 24px; }}
    .info-row {{ margin-bottom: 12px; display: flex; align-items: flex-start; }}
    .info-row:last-child {{ margin-bottom: 0; }}
    .label {{ font-weight: 600; color: #595959; min-width: 80px; flex-shrink: 0; }}
    .value {{ color: #262626; flex: 1; word-break: break-word; }}
    textarea {{ width: 100%; height: 100px; padding: 12px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 14px; font-family: inherit; resize: vertical; box-sizing: border-box; }}
    textarea:focus {{ outline: none; border-color: #1890ff; box-shadow: 0 0 0 2px rgba(24,144,255,0.2); }}
    .btn-group {{ margin-top: 20px; display: flex; gap: 12px; }}
    .btn {{ padding: 10px 24px; font-size: 14px; font-weight: 500; border: none; border-radius: 4px; cursor: pointer; transition: all 0.3s; }}
    .btn-false {{ background: #52c41a; color: white; }}
    .btn-false:hover {{ background: #73d13d; }}
    .btn-true {{ background: #ff4d4f; color: white; }}
    .btn-true:hover {{ background: #ff7875; }}
    label {{ font-weight: 600; color: #333; display: block; margin-bottom: 8px; }}
  </style>
</head>
<body>
  <div class="container">
    <h3>舆情反馈</h3>
    {info_section}
    <label>补充说明（可选）：</label>
    <textarea name="feedback_text" placeholder="例如：误报，内容与医院无关"></textarea>
    <form method="post" action="/feedback" style="margin-top: 20px;">
      <input type="hidden" name="sentiment_id" value="{sentiment_id}">
      <input type="hidden" name="ts" value="{ts}">
      <input type="hidden" name="sig" value="{sig}">
      <input type="hidden" name="feedback_text" id="feedback_text_hidden">
      <div class="btn-group">
        <button class="btn btn-false" type="submit" name="judgment" value="false">✓ 误判舆情</button>
        <button class="btn btn-true" type="submit" name="judgment" value="true">✗ 确认负面</button>
      </div>
    </form>
  </div>
  <script>
    document.querySelector('textarea').addEventListener('input', function() {{
      document.getElementById('feedback_text_hidden').value = this.value;
    }});
  </script>
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
