#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情监控系统主程序
"""

import sys
import os
import time
import yaml
import logging
from datetime import datetime
import sqlite3

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_monitor import EmailMonitor
from link_extractor import LinkExtractor
from content_fetcher import ContentFetcher
from sentiment_analyzer import SentimentAnalyzer
from notifier import Notifier

class SentimentMonitor:
    def __init__(self, config_path='config/config.yaml'):
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 设置日志
        self.setup_logging()
        
        # 初始化模块
        self.email_monitor = EmailMonitor(self.config)
        self.link_extractor = LinkExtractor(self.config)
        self.content_fetcher = ContentFetcher(self.config)
        self.sentiment_analyzer = SentimentAnalyzer(self.config)
        self.notifier = Notifier(self.config)
        
        # 初始化数据库
        self.db_path = self.config['runtime']['database_path']
        self.init_database()
        
        self.check_interval = self.config['runtime']['check_interval']
        self.logger.info("=" * 50)
        self.logger.info("舆情监控系统启动")
        self.logger.info("=" * 50)
    
    def setup_logging(self):
        """配置日志"""
        log_config = self.config['runtime']
        log_level = getattr(logging, log_config['log_level'])
        log_file = log_config['log_file']
        
        # 确保日志目录存在
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # 配置日志格式
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def init_database(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE,
                hospital_name TEXT,
                email_date TEXT,
                processed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
        
        # 添加 url 字段（如果表已存在）
        cursor.execute("PRAGMA table_info(negative_sentiments)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'url' not in columns:
            cursor.execute('ALTER TABLE negative_sentiments ADD COLUMN url TEXT')
            self.logger.info("数据库表结构已升级：添加 url 字段")

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

        self._ensure_column(cursor, 'negative_sentiments', 'content', 'TEXT')
        self._ensure_column(cursor, 'negative_sentiments', 'status', 'TEXT')
        self._ensure_column(cursor, 'negative_sentiments', 'dismissed_at', 'TEXT')
        
        conn.commit()
        conn.close()
        
        self.logger.info("数据库初始化完成")

    def _ensure_column(self, cursor, table_name, column_name, column_def):
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1] for row in cursor.fetchall()}
        if column_name not in columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
    
    def is_email_processed(self, token):
        """检查邮件是否已处理"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM processed_emails WHERE token = ?', (token,))
        result = cursor.fetchone()
        
        conn.close()
        
        return result is not None
    
    def mark_email_processed(self, token, hospital_name, email_date):
        """标记邮件已处理"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO processed_emails (token, hospital_name, email_date)
                VALUES (?, ?, ?)
            ''', (token, hospital_name, email_date))
            conn.commit()
            self.logger.info(f"邮件已标记处理: {token[:20]}...")
        except sqlite3.IntegrityError:
            self.logger.warning(f"邮件已存在: {token[:20]}...")
        
        conn.close()
    
    def save_negative_sentiment(self, sentiment, hospital_name, analysis):
        """保存负面舆情"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO negative_sentiments 
            (sentiment_id, hospital_name, title, source, content, reason, severity, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            sentiment.get('id', ''),
            hospital_name,
            sentiment.get('title', ''),
            sentiment.get('webName', ''),
            sentiment.get('ocrData') or sentiment.get('allContent', ''),
            analysis['reason'],
            analysis['severity'],
            sentiment.get('url', '')
        ))
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"负面舆情已保存到数据库")

    def queue_feedback(self, sentiment_id, recipients):
        """记录可反馈的舆情队列"""
        if not sentiment_id:
            return

        if not recipients:
            recipients = ['@all']
        elif isinstance(recipients, str):
            recipients = [recipients]

        sent_time = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for user_id in recipients:
            cursor.execute('''
                INSERT INTO feedback_queue (sentiment_id, user_id, sent_time)
                VALUES (?, ?, ?)
            ''', (sentiment_id, user_id, sent_time))

        conn.commit()
        conn.close()

        self.logger.info("反馈队列已记录")
    
    def process_email(self, email_info):
        """处理单封邮件"""
        self.logger.info("\n" + "=" * 50)
        self.logger.info(f"开始处理邮件: {email_info['subject']}")
        self.logger.info(f"医院: {email_info['hospital_name']}")
        self.logger.info(f"Token: {email_info['token']}")
        
        token = email_info['token']
        hospital_name = email_info['hospital_name']
        
        # 检查是否已处理
        if self.is_email_processed(token):
            self.logger.info(f"邮件已处理过，跳过")
            return
        
        try:
            # 1. 提取舆情ID
            self.logger.info("步骤1: 提取舆情ID...")
            ids = asyncio.run(self.link_extractor.extract_ids(token))
            
            if not ids:
                self.logger.warning("未提取到舆情ID，跳过")
                return
            
            self.logger.info(f"提取到 {len(ids)} 个舆情ID")
            
            # 2. 获取舆情详情
            self.logger.info("\n步骤2: 获取舆情详情...")
            sentiments = self.content_fetcher.fetch_sentiment_details(ids)
            
            if not sentiments:
                self.logger.warning("未获取到舆情详情")
                return
            
            self.logger.info(f"获取到 {len(sentiments)} 条舆情")
            
            # 3. 分析每条舆情
            self.logger.info("\n步骤3: AI分析舆情...")
            negative_count = 0
            
            for i, sentiment in enumerate(sentiments, 1):
                self.logger.info(f"\n  舆情 {i}/{len(sentiments)}: {sentiment.get('title', '无标题')}")
                
                # AI分析
                analysis = self.sentiment_analyzer.analyze(sentiment, hospital_name)
                
                if analysis['is_negative']:
                    negative_count += 1
                    self.logger.warning(f"  ⚠️  发现负面舆情！")
                    self.logger.warning(f"     来源: {sentiment.get('webName', '未知')}")
                    self.logger.warning(f"     理由: {analysis['reason']}")
                    self.logger.warning(f"     严重程度: {analysis['severity']}")
                    
                    # 输出到控制台
                    print("\n" + "!" * 50)
                    print(f"⚠️ 发现负面舆情！")
                    print(f"!" * 50)
                    print(f"医院: {hospital_name}")
                    print(f"来源: {sentiment.get('webName', '未知')}")
                    print(f"标题: {sentiment.get('title', '无标题')}")
                    print(f"内容摘要: {sentiment.get('allContent', '')[:200]}...")
                    print(f"AI判断: {analysis['reason']}")
                    print(f"严重程度: {analysis['severity']}")
                    print("!" * 50 + "\n")
                    
                    # 保存到数据库
                    self.save_negative_sentiment(sentiment, hospital_name, analysis)

                    # 发送通知并记录反馈队列
                    sentiment_info = {
                        'id': sentiment.get('id', ''),
                        'source': sentiment.get('webName', '未知'),
                        'title': sentiment.get('title', '无标题'),
                        'reason': analysis.get('reason', ''),
                        'severity': analysis.get('severity', 'medium'),
                        'url': sentiment.get('url', '')
                    }
                    content = sentiment.get('allContent', '') or sentiment.get('content', '')
                    notify_result = self.notifier.send(
                        title="发现负面舆情",
                        content=content,
                        hospital_name=hospital_name,
                        sentiment_info=sentiment_info
                    )

                    if isinstance(notify_result, dict) and notify_result.get('success'):
                        recipients = notify_result.get('recipients')
                        if recipients:
                            self.queue_feedback(sentiment_info.get('id'), recipients)
                else:
                    self.logger.info(f"  ✓ 非负面舆情: {analysis['reason']}")
            
            # 标记邮件已处理
            self.logger.info(f"\n步骤4: 标记邮件已处理...")
            self.mark_email_processed(token, hospital_name, email_info['date'])
            
            self.logger.info(f"\n处理完成！发现 {negative_count} 条负面舆情")
        
        except Exception as e:
            self.logger.error(f"处理邮件失败: {e}")
    
    def run(self):
        """主循环"""
        self.logger.info(f"开始监控，检查间隔: {self.check_interval}秒")
        
        try:
            while True:
                try:
                    # 连接Gmail
                    if self.email_monitor.connect():
                        # 获取新邮件
                        emails = self.email_monitor.get_new_emails()
                        
                        if emails:
                            self.logger.info(f"\n找到 {len(emails)} 封新邮件")
                            
                            for email in emails:
                                self.process_email(email)
                        else:
                            self.logger.info("没有新邮件")
                        
                        # 断开连接
                        self.email_monitor.disconnect()
                    else:
                        self.logger.error("连接Gmail失败")
                    
                    # 等待下一次检查
                    self.logger.info(f"\n等待 {self.check_interval} 秒后继续...")
                    time.sleep(self.check_interval)
                
                except KeyboardInterrupt:
                    self.logger.info("\n收到中断信号，退出...")
                    break
                except Exception as e:
                    self.logger.error(f"主循环错误: {e}")
                    time.sleep(60)  # 出错后等待1分钟
        
        finally:
            self.logger.info("舆情监控系统停止")

def main():
    """主函数"""
    monitor = SentimentMonitor()
    monitor.run()

if __name__ == '__main__':
    import asyncio
    main()
