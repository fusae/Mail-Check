#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情监控 API 服务（Flask）
同域名提供前端数据与 AI 总结/洞察接口
"""

import hashlib
import hmac
import logging
import os
import random
import re
import time
import db
from collections import defaultdict
from datetime import datetime, timedelta

import requests
import yaml
from flask import Flask, jsonify, request, send_file


logging.basicConfig(level=logging.DEBUG)


app = Flask(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)


def load_config():
    config_path = os.path.join(project_root, 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _get_config_path():
    return os.path.join(project_root, 'config', 'config.yaml')


def _read_config_file():
    config_path = _get_config_path()
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _write_config_file(cfg):
    config_path = _get_config_path()
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


config = load_config()
ai_config = config.get('ai', {})
feedback_config = config.get('feedback', {})
_default_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:10088",
    "http://127.0.0.1:10088",
]
_cfg_origins = (config.get("runtime", {}) or {}).get("cors_origins") or []
# Merge defaults + config to avoid config overriding dev origins accidentally.
CORS_ORIGINS = sorted(set(_default_cors_origins + list(_cfg_origins)))
REPORTS_DIR = os.path.join(project_root, 'data', 'reports')


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin and origin in CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return response


def init_database():
    db.ensure_schema(project_root)


def query_db(sql, params=(), fetchone=False):
    if fetchone:
        return db.execute(project_root, sql, params, fetchone=True)
    return db.execute(project_root, sql, params, fetchall=True)


def _now_local_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def row_to_opinion(row, include_content=True, preview_len=240):
    content = row["content"] or ""
    if include_content:
        content_out = content
        truncated = False
    else:
        content_out = content[:preview_len]
        truncated = len(content) > preview_len
    return {
        "id": row["sentiment_id"],
        "hospital": row["hospital_name"],
        "title": row["title"],
        "source": row["source"],
        "content": content_out,
        "reason": row["reason"],
        "severity": row["severity"],
        "score": 1.0 if row["severity"] == "high" else 0.6 if row["severity"] == "medium" else 0.3,
        "url": row["url"],
        "status": row["status"] or "active",
        "dismissed_at": row["dismissed_at"],
        "content_truncated": truncated,
        "createdAt": _format_local_time(row["processed_at"]),
    }


def get_sentiment_info(sentiment_id):
    result = query_db(
        '''
        SELECT hospital_name, title, source, content, reason, severity, url, status, dismissed_at
        FROM negative_sentiments
        WHERE sentiment_id = ?
        ''',
        (sentiment_id,),
        fetchone=True
    )
    if not result:
        return None
    if isinstance(result, dict):
        return {
            'hospital_name': result.get('hospital_name'),
            'title': result.get('title'),
            'source': result.get('source'),
            'content': result.get('content'),
            'reason': result.get('reason'),
            'severity': result.get('severity'),
            'url': result.get('url', ''),
            'status': result.get('status', 'active'),
            'dismissed_at': result.get('dismissed_at')
        }
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
    conn = db.connect(project_root)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sentiment_feedback (
            sentiment_id, feedback_judgment, feedback_type,
            feedback_text, user_id, feedback_time, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['sentiment_id'],
        data['feedback_judgment'],
        data['feedback_type'],
        data['feedback_text'],
        data['user_id'],
        _now_local_str(),
        _now_local_str(),
    ))
    feedback_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return feedback_id


def delete_negative_sentiment(sentiment_id):
    conn = db.connect(project_root)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE negative_sentiments
        SET status = 'dismissed', dismissed_at = ?
        WHERE sentiment_id = ?
    ''', (_now_local_str(), sentiment_id))
    conn.commit()
    conn.close()


def restore_negative_sentiment(sentiment_id):
    conn = db.connect(project_root)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE negative_sentiments
        SET status = 'active', dismissed_at = NULL
        WHERE sentiment_id = ?
    ''', (sentiment_id,))
    conn.commit()
    conn.close()


def get_feedback_list(sentiment_id):
    conn = db.connect(project_root)
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
            'feedback_time': row.get('feedback_time') if isinstance(row, dict) else row[0],
            'feedback_type': row.get('feedback_type') if isinstance(row, dict) else row[1],
            'feedback_text': row.get('feedback_text') if isinstance(row, dict) else row[2],
            'user_id': row.get('user_id') if isinstance(row, dict) else row[3]
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

    conn = db.connect(project_root)
    cursor = conn.cursor()
    for rule in rules:
        cursor.execute('''
            INSERT INTO feedback_rules (
                pattern, rule_type, action, confidence, enabled, source_feedback_id, created_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
        ''', (
            rule.get('pattern'),
            rule.get('rule_type', 'keyword'),
            action,
            rule.get('confidence', 0.5),
            feedback_id,
            _now_local_str(),
        ))
    conn.commit()
    conn.close()


@app.get("/api/opinions")
def list_opinions():
    status = request.args.get("status", "active")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    compact = request.args.get("compact", "0").lower() in ("1", "true", "yes")
    preview_len = int(request.args.get("preview", 240))

    logging.debug(
        f"list_opinions called: status={status}, limit={limit}, offset={offset}, compact={compact}"
    )

    rows = query_db(
        """
        SELECT sentiment_id, hospital_name, title, source, content, reason,
               severity, url, status, dismissed_at, processed_at
        FROM negative_sentiments
        WHERE (? = 'all' OR COALESCE(NULLIF(status, ''), 'active') = ?)
        ORDER BY processed_at DESC
        LIMIT ? OFFSET ?
        """,
        (status, status, limit, offset),
    )
    logging.debug(f"Query returned {len(rows)} rows")
    return jsonify([row_to_opinion(r, include_content=not compact, preview_len=preview_len) for r in rows])


@app.get("/api/stats")
def get_stats():
    range_key = request.args.get("range", "7d")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    now = datetime.now()
    if start_date or end_date:
        start_dt = _parse_db_datetime(start_date) if start_date else None
        end_dt = _parse_db_datetime(end_date) if end_date else None
    else:
        if range_key == "24h":
            start_dt = now - timedelta(hours=24)
        elif range_key == "30d":
            start_dt = now - timedelta(days=30)
        else:
            start_dt = now - timedelta(days=7)
        end_dt = now

    time_filters = []
    params = []
    if start_dt:
        time_filters.append("processed_at >= ?")
        params.append(start_dt.strftime("%Y-%m-%d %H:%M:%S"))
    if end_dt:
        time_filters.append("processed_at <= ?")
        params.append(end_dt.strftime("%Y-%m-%d %H:%M:%S"))
    time_clause = " AND ".join(time_filters)
    active_clause = " AND ".join([f for f in [time_clause, "COALESCE(NULLIF(status,''),'active') != 'dismissed'"] if f])
    time_where = f"WHERE {time_clause}" if time_clause else ""
    active_where = f"WHERE {active_clause}" if active_clause else ""

    status_expr = "COALESCE(NULLIF(status,''),'active')"

    proc_params = []
    if start_dt:
        proc_params.append(start_dt.strftime("%Y-%m-%d %H:%M:%S"))
    if end_dt:
        proc_params.append(end_dt.strftime("%Y-%m-%d %H:%M:%S"))

    rows = query_db(
        f"""
        SELECT
            SUM(CASE WHEN {status_expr} != 'dismissed' THEN 1 ELSE 0 END) AS active_total,
            SUM(CASE WHEN severity = 'high' AND {status_expr} != 'dismissed' THEN 1 ELSE 0 END) AS high_total,
            SUM(CASE WHEN severity = 'medium' AND {status_expr} != 'dismissed' THEN 1 ELSE 0 END) AS medium_total,
            SUM(CASE WHEN severity = 'low' AND {status_expr} != 'dismissed' THEN 1 ELSE 0 END) AS low_total,
            SUM(CASE WHEN {status_expr} != 'dismissed'
                THEN CASE
                    WHEN severity = 'high' THEN 0.92
                    WHEN severity = 'medium' THEN 0.6
                    ELSE 0.35
                END
                ELSE 0 END) AS total_score,
            SUM(CASE WHEN {status_expr} != 'dismissed' THEN 1 ELSE 0 END) AS score_count
        FROM negative_sentiments
        {time_where}
        """,
        tuple(proc_params),
        fetchone=True,
    )

    dis_filters = []
    dis_params = []
    if start_dt:
        dis_filters.append("dismissed_at >= ?")
        dis_params.append(start_dt.strftime("%Y-%m-%d %H:%M:%S"))
    if end_dt:
        dis_filters.append("dismissed_at <= ?")
        dis_params.append(end_dt.strftime("%Y-%m-%d %H:%M:%S"))
    dis_clause = " AND ".join(dis_filters)
    dis_where = f"AND {dis_clause}" if dis_clause else ""

    dismissed_row = query_db(
        f"""
        SELECT COUNT(*) AS dismissed_total
        FROM negative_sentiments
        WHERE {status_expr} = 'dismissed'
        {dis_where}
        """,
        tuple(dis_params),
        fetchone=True,
    )
    dismissed_total = (dismissed_row or {}).get("dismissed_total", 0)
    sources_rows = query_db(
        f"""
        SELECT
            COALESCE(NULLIF(source,''),'未知') AS source,
            COUNT(*) AS count
        FROM negative_sentiments
        {active_where}
        GROUP BY COALESCE(NULLIF(source,''),'未知')
        ORDER BY count DESC
        LIMIT 10
        """,
        tuple(params),
    )
    hospital_list_rows = query_db(
        f"""
        SELECT DISTINCT COALESCE(NULLIF(hospital_name,''),'未知') AS hospital
        FROM negative_sentiments
        {active_where}
        ORDER BY hospital
        """,
        tuple(params),
    )
    hospital_rows = query_db(
        f"""
        SELECT
            COALESCE(NULLIF(hospital_name,''),'未知') AS hospital,
            SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) AS high,
            SUM(CASE WHEN severity = 'medium' THEN 1 ELSE 0 END) AS medium,
            SUM(CASE WHEN severity = 'low' THEN 1 ELSE 0 END) AS low,
            COUNT(*) AS total
        FROM negative_sentiments
        {active_where}
        GROUP BY COALESCE(NULLIF(hospital_name,''),'未知')
        ORDER BY total DESC
        LIMIT 10
        """,
        tuple(params),
    )
    score_count = rows["score_count"] or 0
    avg_score = round((rows["total_score"] or 0) / score_count * 100, 1) if score_count else 0
    return jsonify({
        "active_total": rows["active_total"] or 0,
        "dismissed_total": dismissed_total or 0,
        "high_total": rows["high_total"] or 0,
        "avg_score": avg_score,
        "severity": {
            "high": rows["high_total"] or 0,
            "medium": rows["medium_total"] or 0,
            "low": rows["low_total"] or 0,
        },
        "sources": [
            {"source": r["source"], "count": r["count"] or 0}
            for r in sources_rows
        ],
        "hospital_list": [r["hospital"] for r in hospital_list_rows],
        "hospitals": [
            {
                "hospital": r["hospital"],
                "high": r["high"] or 0,
                "medium": r["medium"] or 0,
                "low": r["low"] or 0,
                "total": r["total"] or 0,
            }
            for r in hospital_rows
        ],
    })


@app.get("/api/stats/trend")
def get_trend():
    range_key = request.args.get("range", "7d")
    now = datetime.now()
    if range_key == "24h":
        start_dt = now - timedelta(hours=24)
        bucket_fmt = "%H:00"
    elif range_key == "30d":
        start_dt = now - timedelta(days=30)
        bucket_fmt = "%m-%d"
    else:
        start_dt = now - timedelta(days=7)
        bucket_fmt = "%m-%d"

    rows = query_db(
        """
        SELECT processed_at, severity
        FROM negative_sentiments
        WHERE COALESCE(NULLIF(status,''),'active') != 'dismissed'
          AND processed_at >= ?
          AND processed_at <= ?
        ORDER BY processed_at ASC
        """,
        (start_dt.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")),
    )

    buckets = defaultdict(lambda: {"count": 0, "score": 0.0})
    cursor = start_dt
    step = timedelta(hours=1) if range_key == "24h" else timedelta(days=1)
    while cursor <= now:
        buckets[cursor.strftime(bucket_fmt)]
        cursor += step

    for row in rows:
        ts = _parse_db_datetime(row["processed_at"])
        if not ts:
            continue
        label = ts.strftime(bucket_fmt)
        buckets[label]["count"] += 1
        buckets[label]["score"] += _severity_score(row["severity"] or "low")

    data = []
    for label, item in sorted(buckets.items(), key=lambda x: x[0]):
        avg_score = round((item["score"] / item["count"]) * 100) if item["count"] else 0
        data.append({
            "label": label,
            "count": item["count"],
            "avgScore": avg_score,
        })

    return jsonify({"range": range_key, "data": data})


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
    compact = request.args.get("compact", "0").lower() in ("1", "true", "yes")
    preview_len = int(request.args.get("preview", 240))

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
    return jsonify([row_to_opinion(r, include_content=not compact, preview_len=preview_len) for r in rows])


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

    api_url = ai_config.get("api_url")
    timeout = ai_config.get("timeout", 60)
    # Retry policy: keep backward compat with max_retries, but add exponential backoff
    # and only retry on transient failures.
    max_retries = int(ai_config.get("max_retries", 2))
    max_attempts = max(1, max_retries + 1)
    backoff_base = float(ai_config.get("retry_backoff_seconds", 1.0))
    backoff_cap = float(ai_config.get("retry_backoff_max_seconds", 8.0))
    retry_statuses = set(ai_config.get("retry_statuses", [429, 500, 502, 503, 504]))

    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(api_url, headers=headers, json=data, timeout=timeout)

            if resp.status_code in retry_statuses and attempt < max_attempts:
                retry_after = resp.headers.get("Retry-After")
                sleep_s = min(backoff_cap, backoff_base * (2 ** (attempt - 1)))
                if retry_after:
                    try:
                        sleep_s = min(backoff_cap, float(retry_after))
                    except Exception:
                        pass
                # small jitter to avoid thundering herd
                sleep_s = min(backoff_cap, sleep_s + random.random() * 0.25)
                logging.warning(
                    f"AI调用返回{resp.status_code}（第{attempt}次），等待{sleep_s:.1f}s后重试"
                )
                time.sleep(sleep_s)
                continue

            resp.raise_for_status()
            result = resp.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            sleep_s = min(backoff_cap, backoff_base * (2 ** (attempt - 1)))
            sleep_s = min(backoff_cap, sleep_s + random.random() * 0.25)
            logging.warning(f"AI调用失败（第{attempt}次）: {exc}，等待{sleep_s:.1f}s后重试")
            time.sleep(sleep_s)

    raise last_exc


def _parse_db_datetime(value):
    if not value:
        return None
    # MySQL (pymysql) may return datetime objects already
    if isinstance(value, datetime):
        return value
    # Some drivers may return date objects
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        try:
            return datetime(
                value.year,
                value.month,
                value.day,
                getattr(value, "hour", 0),
                getattr(value, "minute", 0),
                getattr(value, "second", 0),
            )
        except Exception:
            return None
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except Exception:
            return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_local_time(value):
    dt = _parse_db_datetime(value)
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else value


def _severity_score(severity):
    if severity == "high":
        return 0.92
    if severity == "medium":
        return 0.6
    return 0.35



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
    return jsonify({"text": text, "generated_at": _now_local_str()})


@app.post("/api/ai/insight")
def ai_insight():
    payload = request.get_json(force=True) or {}
    opinion = payload.get("opinion") or {}

    if not opinion:
        return jsonify({"text": "未提供舆情内容。"}), 400

    sentiment_id = opinion.get("id")
    if sentiment_id:
        cached = query_db(
            "SELECT insight_text, insight_at FROM negative_sentiments WHERE sentiment_id = ?",
            (sentiment_id,),
            fetchone=True,
        )
        if cached and cached["insight_text"]:
            return jsonify({
                "text": cached["insight_text"],
                "generated_at": cached["insight_at"] or _now_local_str(),
                "cached": True,
            })

    prompt = (
        "请对以下单条舆情进行传播风险点分析，并给出简要建议（100字以内）。\n"
        f"医院:{opinion.get('hospital')}\n"
        f"来源:{opinion.get('source')}\n"
        f"标题:{opinion.get('title')}\n"
        f"内容:{opinion.get('content')}\n"
    )
    text = call_ai(prompt)
    generated_at = _now_local_str()
    if sentiment_id:
        conn = db.connect(project_root)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE negative_sentiments SET insight_text = ?, insight_at = ? WHERE sentiment_id = ?",
            (text, generated_at, sentiment_id),
        )
        conn.commit()
        conn.close()
    return jsonify({"text": text, "generated_at": generated_at, "cached": False})


@app.get("/api/notification/suppress_keywords")
def get_suppress_keywords():
    cfg = _read_config_file()
    notification = cfg.get("notification", {}) or {}
    wechat_cfg = notification.get("wechat_work", {}) or {}
    keywords = wechat_cfg.get("suppress_keywords") or notification.get("suppress_keywords") or []
    if isinstance(keywords, str):
        keywords = [keywords]
    keywords = [str(k).strip() for k in keywords if str(k).strip()]
    return jsonify({"keywords": keywords})


@app.post("/api/notification/suppress_keywords")
def update_suppress_keywords():
    payload = request.get_json(force=True) or {}
    keywords = payload.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [keywords]
    cleaned = []
    for k in keywords:
        text = str(k).strip()
        if text and text not in cleaned:
            cleaned.append(text)

    cfg = _read_config_file()
    notification = cfg.setdefault("notification", {})
    wechat_cfg = notification.setdefault("wechat_work", {})
    wechat_cfg["suppress_keywords"] = cleaned

    _write_config_file(cfg)
    return jsonify({"success": True, "keywords": cleaned})


@app.post("/api/report/generate")
def api_generate_report():
    """生成舆情报告（新报告生成器）"""
    try:
        data = request.get_json() or {}

        from report_generator_mailcheck import MailCheckReportGenerator

        generator = MailCheckReportGenerator()
        result = generator.generate_report(
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            hospital=data.get('hospital'),
            report_period=data.get('period'),
            output_format=data.get('format', 'markdown')
        )

        if result.get('success'):
            files = {}
            for fmt, path in result.get('files', {}).items():
                files[fmt] = f"/api/report/download/{os.path.basename(path)}"

            return jsonify({
                'success': True,
                'message': '报告生成成功',
                'files': files,
                'summary': {
                    'hospital': result.get('hospital_name'),
                    'period': result.get('period'),
                    'total_events': result.get('total_events'),
                    'high_risk_events': result.get('high_risk_events'),
                }
            })

        return jsonify({'success': False, 'message': result.get('message', '生成失败')}), 500

    except Exception as e:
        logging.exception("Failed to generate report")
        return jsonify({'success': False, 'message': f'生成报告失败: {str(e)}'}), 500


@app.get("/api/report/download/<filename>")
def api_download_report(filename):
    """下载生成的报告（新报告生成器）"""
    try:
        if not filename or '..' in filename or '/' in filename:
            return jsonify({'success': False, 'message': '无效的文件名'}), 400

        file_path = os.path.join(REPORTS_DIR, filename)

        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '文件不存在'}), 404

        return send_file(file_path, as_attachment=True, download_name=filename)

    except Exception as e:
        logging.exception("Failed to download report")
        return jsonify({'success': False, 'message': f'下载失败: {str(e)}'}), 500


@app.get("/api/report/list")
def api_list_reports():
    """列出已生成的报告（新报告生成器）"""
    try:
        if not os.path.exists(REPORTS_DIR):
            return jsonify({'success': True, 'reports': []})

        reports = []
        for filename in os.listdir(REPORTS_DIR):
            file_path = os.path.join(REPORTS_DIR, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                file_ext = os.path.splitext(filename)[1].lower()
                fmt = 'word' if file_ext == '.docx' else 'markdown'
                reports.append({
                    'filename': filename,
                    'created_at': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': stat.st_size,
                    'format': fmt,
                })

        reports.sort(key=lambda x: x['created_at'], reverse=True)
        return jsonify({'success': True, 'reports': reports[:50]})

    except Exception as e:
        logging.exception("Failed to list reports")
        return jsonify({'success': False, 'message': f'获取列表失败: {str(e)}'}), 500


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
