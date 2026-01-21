#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情监控系统主程序（集成通知模块）
"""

import sys
import os
import time
import yaml
import logging
from datetime import datetime
import sqlite3
import asyncio

# 添加src目录到路径（如果从其他目录运行）
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from email_monitor import EmailMonitor
from link_extractor import LinkExtractor
from content_fetcher import ContentFetcher
from sentiment_analyzer import SentimentAnalyzer
from notifier import Notifier

class SentimentMonitor:
    def __init__(self, config_path=None):
        # 确定配置文件路径
        if config_path is None:
            # 从项目根目录查找
            project_root = os.path.dirname(current_dir)
            config_path = os.path.join(project_root, 'config', 'config.yaml')
        
        self.config_path = config_path
        
        # 检查配置文件是否存在
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
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
        self.notifier = Notifier(self.config)  # 初始化通知模块
        
        # 初始化数据库
        self.db_path = self.config['runtime']['database_path']
        self.init_database()
        
        self.check_interval = self.config['runtime']['check_interval']
        self.logger.info("=" * 50)
        self.logger.info("舆情监控系统启动")
        self.logger.info(f"配置文件: {self.config_path}")
        self.logger.info(f"通知方式: {self.config.get('notification', {}).get('provider', 'serverchan')}")
        self.logger.info("=" * 50)
    
    def setup_logging(self):
        """配置日志"""
        log_config = self.config['runtime']
        log_level = getattr(logging, log_config['log_level'])
        log_file = log_config['log_file']
        
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
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
        self.logger.setLevel(log_level)
    
    def init_database(self):
        """初始化数据库"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        with self._connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute('PRAGMA journal_mode=WAL')
        
            # 创建 processed_emails 表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE,
                    hospital_name TEXT,
                    email_date TEXT,
                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建 negative_sentiments 表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS negative_sentiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sentiment_id TEXT,
                    hospital_name TEXT,
                    title TEXT,
                    source TEXT,
                    reason TEXT,
                    severity TEXT,
                    original_url TEXT,
                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_negative_sentiments_sentiment_id
                ON negative_sentiments (sentiment_id)
            ''')
        
        self.logger.info(f"数据库初始化完成: {self.db_path}")

    def _connect_db(self):
        """创建数据库连接，设置忙等待避免写锁报错"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute('PRAGMA busy_timeout=30000')
        return conn
    
    def is_email_processed(self, token):
        """检查邮件是否已处理"""
        with self._connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM processed_emails WHERE token = ?', (token,))
            result = cursor.fetchone()
            return result is not None
    
    def mark_email_processed(self, token, hospital_name, email_date):
        """标记邮件已处理"""
        try:
            with self._connect_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO processed_emails (token, hospital_name, email_date)
                    VALUES (?, ?, ?)
                ''', (token, hospital_name, email_date))
                self.logger.info(f"邮件已标记处理: {token[:20]}...")
        except sqlite3.IntegrityError:
            self.logger.warning(f"邮件已存在: {token[:20]}...")
        except sqlite3.OperationalError as e:
            self.logger.error(f"写入处理记录失败: {e}")
    
    def save_negative_sentiment(self, sentiment, hospital_name, analysis, original_url=None):
        """保存负面舆情"""
        try:
            with self._connect_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO negative_sentiments
                    (sentiment_id, hospital_name, title, source, reason, severity, original_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sentiment.get('id', ''),
                    hospital_name,
                    sentiment.get('title', ''),
                    sentiment.get('webName', ''),
                    analysis['reason'],
                    analysis['severity'],
                    original_url
                ))
                self.logger.info(f"负面舆情已保存到数据库")
        except sqlite3.IntegrityError:
            self.logger.info("负面舆情已存在，跳过写入")
        except sqlite3.OperationalError as e:
            self.logger.error(f"写入负面舆情失败: {e}")
    
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
                    self.logger.warning(f"  ⚠️ 发现负面舆情！")
                    self.logger.warning(f"     医院: {hospital_name}")
                    self.logger.warning(f"     来源: {sentiment.get('webName', '未知')}")
                    self.logger.warning(f"     理由: {analysis['reason']}")
                    self.logger.warning(f"     严重程度: {analysis['severity']}")
                    
                    # 获取原文链接
                    self.logger.info("获取原文链接...")
                    original_url = None
                    try:
                        sentiment_id = sentiment.get('id', '')
                        original_url = self.content_fetcher.get_original_url(sentiment_id)
                        if original_url:
                            self.logger.info(f"成功获取原文链接: {original_url}")
                        else:
                            self.logger.warning("未能获取原文链接")
                    except Exception as e:
                        self.logger.error(f"获取原文链接失败: {e}")
                    
                    # 输出到控制台
                    print("\n" + "!" * 50)
                    print(f"⚠️ 发现负面舆情！")
                    print("!" * 50)
                    print(f"医院: {hospital_name}")
                    print(f"来源: {sentiment.get('webName', '未知')}")
                    print(f"标题: {sentiment.get('title', '无标题')}")
                    content = sentiment.get('allContent', '')
                    print(f"内容摘要: {content[:200]}...")
                    print(f"AI判断: {analysis['reason']}")
                    print(f"严重程度: {analysis['severity']}")
                    if original_url:
                        print(f"原文链接: {original_url}")
                    print("!" * 50 + "\n")

                    # 保存到数据库
                    self.save_negative_sentiment(sentiment, hospital_name, analysis, original_url)
                    
                    # 发送通知 - 使用当前舆情的内容
                    self.logger.info("步骤4: 发送通知...")
                    sentiment_info = {
                        'source': sentiment.get('webName', '未知'),
                        'title': sentiment.get('title', '无标题'),
                        'url': sentiment.get('url', ''),
                        'original_url': original_url,
                        'reason': analysis['reason'],
                        'severity': analysis['severity']
                    }

                    # 准备通知内容 - 只使用当前舆情的内容
                    content = sentiment.get('allContent', '')
                    title = f"发现医院负面舆情: {sentiment.get('title', '无标题')}"

                    # 发送通知
                    self.notifier.send(
                        title=title,
                        content=content,
                        hospital_name=hospital_name,
                        sentiment_info=sentiment_info,
                        sentiment_id=sentiment.get('id', '')
                    )
                    
                    self.logger.info("通知发送完成")
                else:
                    self.logger.info(f"  ✓ 非负面舆情: {analysis['reason']}")
            
            # 标记邮件已处理
            self.logger.info(f"\n步骤5: 标记邮件已处理...")
            self.mark_email_processed(token, hospital_name, email_info['date'])
            
            self.logger.info(f"\n处理完成！发现 {negative_count} 条负面舆情")
        
        except Exception as e:
            self.logger.error(f"处理邮件失败: {e}")
    
    def run(self):
        """主循环"""
        self.logger.info(f"开始监控，检查间隔: {self.check_interval}秒")

        while True:
            try:
                try:
                    # 连接QQ邮箱
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
                        self.logger.error(f"连接{self.email_monitor.email_type_name}失败")

                     # 等待下一次检查
                    self.logger.info(f"\n等待 {self.check_interval} 秒后继续...")
                    self.logger.debug(f"开始等待时间: {datetime.now()}")
                    time.sleep(self.check_interval)
                    self.logger.debug(f"等待完成时间: {datetime.now()}")
                
                except KeyboardInterrupt:
                    self.logger.info("\n收到中断信号，退出...")
                    break
            except Exception as e:
                import traceback
                self.logger.error(f"主循环异常: {e}")
                self.logger.error(f"错误详情: {traceback.format_exc()}")
                self.logger.info(f"等待 60 秒后自动重启...")
                time.sleep(60)
                continue

        self.logger.info("舆情监控系统正常退出")

def main():
    """主函数"""
    # 从项目根目录运行
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, 'config', 'config.yaml')
    
    monitor = SentimentMonitor(config_path)
    monitor.run()

if __name__ == '__main__':
    main()
