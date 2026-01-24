#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情监控 API 服务（Flask）
同域名提供前端数据与 AI 总结/洞察接口
"""

import hashlib
import hmac
import os
import re
import sqlite3
from datetime import datetime

import requests
import yaml
from flask import Flask, jsonify, request


app = Flask(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)


def load_config():
    config_path = os.path.join(project_root, 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


config = load_config()
DB_PATH = config.get('runtime', {}).get(
    'database_path',
    os.path.join(project_root, 'data', 'processed_emails.db')
)

ai_config = config.get('ai', {})
feedback_config = config.get('feedback', {})


def _ensure_column(cursor, table_name, column_name, column_def):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


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
            url TEXT,
            status TEXT DEFAULT 'active',
            dismissed_at TEXT,
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
    _ensure_column(cursor, 'negative_sentiments', 'url', 'TEXT')
    _ensure_column(cursor, 'negative_sentiments', 'status', 'TEXT')
    _ensure_column(cursor, 'negative_sentiments', 'dismissed_at', 'TEXT')

    conn.commit()
    conn.close()


def query_db(sql, params=(), fetchone=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchone() if fetchone else cursor.fetchall()
    conn.close()
    return rows


def row_to_opinion(row):
    return {
        "id": row["sentiment_id"],
        "hospital": row["hospital_name"],
        "title": row["title"],
        "source": row["source"],
        "content": row["content"],
        "reason": row["reason"],
        "severity": row["severity"],
        "score": 1.0 if row["severity"] == "high" else 0.6 if row["severity"] == "medium" else 0.3,
        "url": row["url"],
        "status": row["status"] or "active",
        "dismissed_at": row["dismissed_at"],
        "createdAt": row["processed_at"],
    }


def get_sentiment_info(sentiment_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT hospital_name, title, source, content, reason, severity, url, status, dismissed_at
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
            'severity': result[5],
            'url': result[6] if len(result) > 6 else '',
            'status': result[7] if len(result) > 7 else 'active',
            'dismissed_at': result[8] if len(result) > 8 else None
        }
    return None


def verify_signature(sentiment_id, sig):
    secret = feedback_config.get('link_secret', '')
    if not secret:
        return False

    message = f"{sentiment_id}".encode('utf-8')
    expected = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig or ''):
        return False
    return True


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
    cursor.execute('''
        UPDATE negative_sentiments
        SET status = 'dismissed', dismissed_at = ?
        WHERE sentiment_id = ?
    ''', (datetime.now().isoformat(), sentiment_id))
    conn.commit()
    conn.close()


def restore_negative_sentiment(sentiment_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE negative_sentiments
        SET status = 'active', dismissed_at = NULL
        WHERE sentiment_id = ?
    ''', (sentiment_id,))
    conn.commit()
    conn.close()


def get_feedback_list(sentiment_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT feedback_time, feedback_type, feedback_text, user_id
        FROM sentiment_feedback
        WHERE sentiment_id = ?
        ORDER BY created_at DESC
        LIMIT 20
    ''', (sentiment_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            'feedback_time': row[0],
            'feedback_type': row[1],
            'feedback_text': row[2],
            'user_id': row[3]
        }
        for row in rows
    ]


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


@app.get("/api/opinions")
def list_opinions():
    status = request.args.get("status", "active")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    rows = query_db(
        """
        SELECT sentiment_id, hospital_name, title, source, content, reason,
               severity, url, status, dismissed_at, processed_at
        FROM negative_sentiments
        WHERE (? = 'all' OR status = ?)
        ORDER BY processed_at DESC
        LIMIT ? OFFSET ?
        """,
        (status, status, limit, offset),
    )
    return jsonify([row_to_opinion(r) for r in rows])


@app.get("/api/opinions/<sentiment_id>")
def get_opinion(sentiment_id):
    row = query_db(
        """
        SELECT sentiment_id, hospital_name, title, source, content, reason,
               severity, url, status, dismissed_at, processed_at
        FROM negative_sentiments
        WHERE sentiment_id = ?
        """,
        (sentiment_id,),
        fetchone=True,
    )
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify(row_to_opinion(row))


@app.get("/api/search")
def search_opinions():
    query = request.args.get("query", "").strip()
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    if not query:
        return jsonify([])

    like = f"%{query}%"
    rows = query_db(
        """
        SELECT sentiment_id, hospital_name, title, source, content, reason,
               severity, url, status, dismissed_at, processed_at
        FROM negative_sentiments
        WHERE hospital_name LIKE ? OR title LIKE ? OR content LIKE ? OR source LIKE ?
        ORDER BY processed_at DESC
        LIMIT ? OFFSET ?
        """,
        (like, like, like, like, limit, offset),
    )
    return jsonify([row_to_opinion(r) for r in rows])


def call_ai(prompt):
    if not ai_config:
        return "AI 未配置"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ai_config.get('api_key', '')}"
    }
    data = {
        "model": ai_config.get("model"),
        "messages": [
            {"role": "system", "content": "你是专业的舆情分析助手。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": ai_config.get("temperature", 0.3),
        "max_tokens": ai_config.get("max_tokens", 800)
    }

    resp = requests.post(ai_config.get("api_url"), headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    return result["choices"][0]["message"]["content"]


@app.post("/api/ai/summary")
def ai_summary():
    payload = request.get_json(force=True) or {}
    opinions = payload.get("opinions") or []

    if not opinions:
        return jsonify({"text": "暂无负面舆情可总结。"})

    lines = []
    for idx, op in enumerate(opinions, 1):
        lines.append(f"{idx}. 医院:{op.get('hospital')} 标题:{op.get('title')} 内容:{(op.get('content') or '')[:200]}")

    prompt = (
        "请基于以下舆情列表生成一段“现状综述”和“公关建议”。\n"
        "输出格式：\n"
        "现状综述：...\n"
        "公关建议：...\n\n"
        "舆情列表：\n" + "\n".join(lines)
    )

    text = call_ai(prompt)
    return jsonify({"text": text, "generated_at": datetime.now().isoformat()})


@app.post("/api/ai/insight")
def ai_insight():
    payload = request.get_json(force=True) or {}
    opinion = payload.get("opinion") or {}

    if not opinion:
        return jsonify({"text": "未提供舆情内容。"}), 400

    prompt = (
        "请对以下单条舆情进行传播风险点分析，并给出简要建议（100字以内）。\n"
        f"医院:{opinion.get('hospital')}\n"
        f"来源:{opinion.get('source')}\n"
        f"标题:{opinion.get('title')}\n"
        f"内容:{opinion.get('content')}\n"
    )
    text = call_ai(prompt)
    return jsonify({"text": text, "generated_at": datetime.now().isoformat()})


@app.get('/feedback')
def feedback_form():
    sentiment_id = request.args.get('sentiment_id', '')
    sig = request.args.get('sig', '')

    if not verify_signature(sentiment_id, sig):
        return "Invalid or expired link.", 403

    sentiment_info = get_sentiment_info(sentiment_id)

    if sentiment_info:
        hospital_name = sentiment_info['hospital_name'] or ''
        title = sentiment_info['title'] or ''
        source = sentiment_info['source'] or ''
        content = sentiment_info['content'] or ''
        reason = sentiment_info['reason'] or ''
        severity = sentiment_info['severity'] or 'medium'
        url = sentiment_info.get('url', '')
        status = sentiment_info.get('status', 'active')
        dismissed_at = sentiment_info.get('dismissed_at')
        feedback_list = get_feedback_list(sentiment_id)

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

        feedback_items = ""
        if feedback_list:
            for item in feedback_list:
                feedback_items += f"""
                <div class="feedback-item">
                  <div class="feedback-meta">{item['feedback_time']} | {item['feedback_type']} | {item['user_id']}</div>
                  <div class="feedback-text">{item['feedback_text']}</div>
                </div>
                """
        else:
            feedback_items = "<div class=\"feedback-empty\">暂无反馈</div>"

        status_line = ""
        restore_button = ""
        if status == 'dismissed':
            dismissed_label = dismissed_at or '未知时间'
            status_line = f"""
          <div class="info-row">
            <span class="label">状态：</span>
            <span class="value" style="color: #52c41a; font-weight: bold;">已标记为误报（{dismissed_label}）</span>
          </div>
            """
            restore_button = """
      <button class="btn btn-restore" type="submit" name="action" value="restore">↺ 恢复为负面</button>
            """

        info_section = f"""
        <div class="info-section">
          <h4>舆情详情</h4>
          <div class="info-row">
            <span class="label">舆情ID：</span>
            <span class="value">{sentiment_id}</span>
          </div>
          {status_line}
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
            <span class="label">原文链接：</span>
            <span class="value"><a href="{url}" target="_blank" style="color: #1890ff;">{url or '无'}</a></span>
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
        <div class="feedback-section">
          <h4>用户反馈</h4>
          {feedback_items}
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
    .feedback-section {{ background: #fafafa; border: 1px solid #f0f0f0; border-radius: 6px; padding: 16px; margin-bottom: 24px; }}
    .feedback-item {{ border-bottom: 1px solid #f0f0f0; padding: 10px 0; }}
    .feedback-item:last-child {{ border-bottom: none; }}
    .feedback-meta {{ color: #8c8c8c; font-size: 12px; margin-bottom: 6px; }}
    .feedback-text {{ color: #262626; font-size: 14px; }}
    .feedback-empty {{ color: #8c8c8c; font-size: 13px; }}
    .info-row {{ margin-bottom: 12px; display: flex; align-items: flex-start; }}
    .info-row:last-child {{ margin-bottom: 0; }}
    .label {{ font-weight: 600; color: #595959; min-width: 80px; flex-shrink: 0; }}
    .value {{ color: #262626; flex: 1; word-break: break-word; }}
    textarea {{ width: 100%; height: 100px; padding: 12px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 14px; font-family: inherit; resize: vertical; box-sizing: border-box; }}
    textarea:focus {{ outline: none; border-color: #1890ff; box-shadow: 0 0 0 2px rgba(24,144,255,0.2); }}
    .btn-group {{ margin-top: 20px; display: flex; gap: 12px; flex-wrap: wrap; }}
    .btn {{ padding: 10px 24px; font-size: 14px; font-weight: 500; border: none; border-radius: 4px; cursor: pointer; transition: all 0.3s; }}
    .btn-false {{ background: #52c41a; color: white; }}
    .btn-false:hover {{ background: #73d13d; }}
    .btn-true {{ background: #ff4d4f; color: white; }}
    .btn-true:hover {{ background: #ff7875; }}
    .btn-restore {{ background: #1890ff; color: white; }}
    .btn-restore:hover {{ background: #40a9ff; }}
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
      <input type="hidden" name="sig" value="{sig}">
      <input type="hidden" name="feedback_text" id="feedback_text_hidden">
      <div class="btn-group">
        <button class="btn btn-false" type="submit" name="judgment" value="false">✓ 误判舆情</button>
        <button class="btn btn-true" type="submit" name="judgment" value="true">✗ 确认负面</button>
        {restore_button}
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


@app.post('/feedback')
def submit_feedback():
    sentiment_id = request.form.get('sentiment_id', '')
    sig = request.form.get('sig', '')
    judgment = request.form.get('judgment', '')
    action = request.form.get('action', '')
    feedback_text = (request.form.get('feedback_text') or '').strip()

    if not verify_signature(sentiment_id, sig):
        return "Invalid or expired link.", 403

    if action == 'restore':
        restore_negative_sentiment(sentiment_id)
        save_feedback({
            'sentiment_id': sentiment_id,
            'feedback_judgment': True,
            'feedback_type': 'restore_negative',
            'feedback_text': feedback_text or '恢复为负面',
            'user_id': request.remote_addr or 'web'
        })
        return "已恢复为负面，谢谢！"

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


if __name__ == "__main__":
    init_database()
    api_cfg = config.get("api", {})
    host = api_cfg.get("host", "0.0.0.0")
    port = int(api_cfg.get("port", 5003))
    app.run(host=host, port=port, debug=False)
