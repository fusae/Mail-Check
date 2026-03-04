#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库连接与初始化（MySQL）
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Tuple

import yaml

try:
    import pymysql
    from pymysql.cursors import DictCursor
    MYSQL_AVAILABLE = True
except Exception:
    MYSQL_AVAILABLE = False


def load_config(project_root: str) -> Dict[str, Any]:
    config_path = os.path.join(project_root, "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_db_engine(config: Dict[str, Any]) -> str:
    return "mysql"


def get_mysql_config(config: Dict[str, Any]) -> Dict[str, Any]:
    mysql = config.get("runtime", {}).get("mysql", {}) or {}
    return {
        "host": mysql.get("host", "127.0.0.1"),
        "port": int(mysql.get("port", 3306)),
        "user": mysql.get("user", "root"),
        "password": mysql.get("password", ""),
        "database": mysql.get("database", "mail_check"),
        "charset": mysql.get("charset", "utf8mb4"),
    }


def _adapt_sql(sql: str, engine: str) -> str:
    return sql.replace("?", "%s")


class _MysqlCompatCursor:
    def __init__(self, cursor, engine: str):
        self._cursor = cursor
        self._engine = engine

    def execute(self, sql: str, params: Iterable[Any] = ()):
        return self._cursor.execute(_adapt_sql(sql, self._engine), params or ())

    def executemany(self, sql: str, params: Iterable[Tuple[Any, ...]]):
        return self._cursor.executemany(_adapt_sql(sql, self._engine), params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)


class _MysqlCompatConnection:
    def __init__(self, conn, engine: str):
        self._conn = conn
        self._engine = engine

    def cursor(self):
        return _MysqlCompatCursor(self._conn.cursor(), self._engine)

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()


def connect(project_root: str):
    config = load_config(project_root)
    engine = get_db_engine(config)
    if not MYSQL_AVAILABLE:
        raise RuntimeError("未安装pymysql，请先安装后再使用MySQL。")
    mysql_cfg = get_mysql_config(config)
    conn = pymysql.connect(
        host=mysql_cfg["host"],
        port=mysql_cfg["port"],
        user=mysql_cfg["user"],
        password=mysql_cfg["password"],
        database=mysql_cfg["database"],
        charset=mysql_cfg["charset"],
        cursorclass=DictCursor,
        autocommit=True,
    )
    return _MysqlCompatConnection(conn, engine)


def execute(project_root: str, sql: str, params: Iterable[Any] = (), fetchone: bool = False, fetchall: bool = False):
    config = load_config(project_root)
    engine = get_db_engine(config)
    conn = connect(project_root)
    try:
        cursor = conn.cursor()
        cursor.execute(_adapt_sql(sql, engine), params)
        if fetchone:
            return cursor.fetchone()
        if fetchall:
            return cursor.fetchall()
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def execute_with_lastrowid(project_root: str, sql: str, params: Iterable[Any] = ()) -> int | None:
    config = load_config(project_root)
    engine = get_db_engine(config)
    conn = connect(project_root)
    try:
        cursor = conn.cursor()
        cursor.execute(_adapt_sql(sql, engine), params)
        return cursor.lastrowid
    finally:
        try:
            conn.close()
        except Exception:
            pass


def ensure_mysql_database(config: Dict[str, Any]):
    if not MYSQL_AVAILABLE:
        raise RuntimeError("未安装pymysql，请先安装后再使用MySQL。")
    mysql_cfg = get_mysql_config(config)
    conn = pymysql.connect(
        host=mysql_cfg["host"],
        port=mysql_cfg["port"],
        user=mysql_cfg["user"],
        password=mysql_cfg["password"],
        charset=mysql_cfg["charset"],
        autocommit=True,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{mysql_cfg['database']}` DEFAULT CHARACTER SET utf8mb4"
            )
    finally:
        conn.close()


def ensure_schema(project_root: str):
    config = load_config(project_root)
    ensure_mysql_database(config)
    _ensure_mysql_tables(project_root, config)


def _ensure_mysql_tables(project_root: str, config: Dict[str, Any]):
    conn = connect(project_root)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_emails (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            token VARCHAR(255) UNIQUE,
            hospital_name VARCHAR(255),
            email_date VARCHAR(255),
            processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS negative_sentiments (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            sentiment_id VARCHAR(255),
            event_id BIGINT,
            hospital_name VARCHAR(255),
            title TEXT,
            source VARCHAR(255),
            content LONGTEXT,
            reason TEXT,
            severity VARCHAR(20),
            url TEXT,
            status VARCHAR(20) DEFAULT 'active',
            is_duplicate TINYINT(1) DEFAULT 0,
            dismissed_at DATETIME,
            insight_text LONGTEXT,
            insight_at DATETIME,
            processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_groups (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            hospital_name VARCHAR(255),
            fingerprint BIGINT UNSIGNED,
            event_url VARCHAR(1024),
            total_count BIGINT DEFAULT 1,
            last_title TEXT,
            last_reason TEXT,
            last_source VARCHAR(255),
            last_sentiment_id VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment_feedback (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            sentiment_id VARCHAR(255),
            feedback_judgment TINYINT(1),
            feedback_type VARCHAR(50),
            feedback_text TEXT,
            user_id VARCHAR(255),
            feedback_time DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback_queue (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            sentiment_id VARCHAR(255),
            user_id VARCHAR(255),
            sent_time DATETIME,
            status VARCHAR(20) DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback_rules (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            pattern TEXT,
            rule_type VARCHAR(20),
            action VARCHAR(20),
            confidence DOUBLE,
            enabled TINYINT(1) DEFAULT 1,
            source_feedback_id BIGINT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ''')

    def _mysql_index_exists(table: str, index_name: str) -> bool:
        cursor.execute(
            "SHOW INDEX FROM `{}` WHERE Key_name=%s".format(table),
            (index_name,),
        )
        return cursor.fetchone() is not None

    def _mysql_column_exists(table: str, column_name: str) -> bool:
        cursor.execute(
            """
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND COLUMN_NAME = %s
            """,
            (table, column_name),
        )
        return cursor.fetchone() is not None

    if not _mysql_column_exists("negative_sentiments", "event_id"):
        cursor.execute("ALTER TABLE negative_sentiments ADD COLUMN event_id BIGINT")
    if not _mysql_column_exists("negative_sentiments", "is_duplicate"):
        cursor.execute("ALTER TABLE negative_sentiments ADD COLUMN is_duplicate TINYINT(1) DEFAULT 0")

    if not _mysql_index_exists("negative_sentiments", "idx_negative_sentiments_processed_at"):
        cursor.execute('CREATE INDEX idx_negative_sentiments_processed_at ON negative_sentiments(processed_at)')
    if not _mysql_index_exists("negative_sentiments", "idx_negative_sentiments_status"):
        cursor.execute('CREATE INDEX idx_negative_sentiments_status ON negative_sentiments(status)')
    if not _mysql_index_exists("negative_sentiments", "idx_negative_sentiments_hospital"):
        cursor.execute('CREATE INDEX idx_negative_sentiments_hospital ON negative_sentiments(hospital_name)')
    if not _mysql_index_exists("negative_sentiments", "idx_negative_sentiments_sentiment_id"):
        cursor.execute('CREATE INDEX idx_negative_sentiments_sentiment_id ON negative_sentiments(sentiment_id)')
    if not _mysql_index_exists("negative_sentiments", "idx_negative_sentiments_event_id"):
        cursor.execute('CREATE INDEX idx_negative_sentiments_event_id ON negative_sentiments(event_id)')
    if not _mysql_index_exists("feedback_queue", "idx_feedback_queue_user_status"):
        cursor.execute('CREATE INDEX idx_feedback_queue_user_status ON feedback_queue(user_id, status, sent_time)')
    if not _mysql_index_exists("event_groups", "idx_event_groups_hospital_time"):
        cursor.execute('CREATE INDEX idx_event_groups_hospital_time ON event_groups(hospital_name, last_seen_at)')
    if not _mysql_index_exists("event_groups", "idx_event_groups_fingerprint"):
        cursor.execute('CREATE INDEX idx_event_groups_fingerprint ON event_groups(fingerprint)')
    if not _mysql_index_exists("event_groups", "idx_event_groups_url"):
        # utf8mb4 下 1024 字符可能超过 InnoDB 索引长度上限（3072 bytes）。
        # 用前缀索引既能支持等值查询的快速过滤，又避免建索引失败。
        cursor.execute('CREATE INDEX idx_event_groups_url ON event_groups(event_url(191))')

    conn.commit()
    conn.close()
