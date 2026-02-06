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
import re
import hashlib
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import db

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_monitor import EmailMonitor
from link_extractor import LinkExtractor
from content_fetcher import ContentFetcher
from sentiment_analyzer import SentimentAnalyzer
from notifier import Notifier

class SentimentMonitor:
    def __init__(self, config_path='config/config.yaml'):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.project_root = project_root
        if not os.path.isabs(config_path):
            config_path = os.path.join(project_root, config_path)
        # 确保相对路径以项目根目录为基准
        os.chdir(project_root)

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
        
        # 初始化数据库（MySQL）
        db.ensure_schema(self.project_root)
        
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
    
    def _now_local_str(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _event_dedupe_config(self):
        cfg = (self.config.get("runtime", {}) or {}).get("event_dedupe", {}) or {}
        return {
            "enabled": bool(cfg.get("enabled", True)),
            "window_days": int(cfg.get("window_days", 7)),
            "max_distance": int(cfg.get("max_distance", 4)),
        }

    def _tokenize_for_simhash(self, text: str):
        text = (text or "").lower()
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        alnum_words = re.findall(r"[a-z0-9]+", text)
        return chinese_chars + alnum_words

    def _compute_simhash(self, text: str) -> int:
        tokens = self._tokenize_for_simhash(text)
        if not tokens:
            return 0
        counts = Counter(tokens)
        v = [0] * 64
        for token, freq in counts.items():
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            weight = min(5, 1 + freq)
            for i in range(64):
                if (h >> i) & 1:
                    v[i] += weight
                else:
                    v[i] -= weight
        fingerprint = 0
        for i in range(64):
            if v[i] > 0:
                fingerprint |= (1 << i)
        return fingerprint

    def _hamming_distance(self, a: int, b: int) -> int:
        return bin(a ^ b).count("1")

    def _normalize_event_url(self, url: str, source: str = "") -> str:
        """
        Normalize platform URLs for dedupe.
        Goal: the same underlying content should map to the same key even if tracking params differ.
        """
        url = (url or "").strip()
        if not url:
            return ""

        src = (source or "").strip()
        u = url

        try:
            parsed = urlparse(url)
        except Exception:
            parsed = None

        host = (parsed.netloc.lower() if parsed else "")
        path = (parsed.path if parsed else "")
        qs = (parse_qs(parsed.query) if parsed else {})

        # Douyin: prefer stable video id
        if src == "抖音" or "douyin.com" in host or "douyin.com" in u:
            m = re.search(r"/video/(\d+)", u)
            if not m:
                m = re.search(r"/share/video/(\d+)", u)
            if not m:
                # Some share links use modal_id
                modal = qs.get("modal_id", [])
                if modal and isinstance(modal[0], str) and modal[0].isdigit():
                    return f"douyin:{modal[0]}"
            if m:
                return f"douyin:{m.group(1)}"

        # Xiaohongshu: prefer note id if available
        if src == "小红书" or "xiaohongshu.com" in host or "xhslink.com" in host:
            m = re.search(r"/explore/([0-9a-fA-F]+)", u)
            if m:
                return f"xhs:{m.group(1).lower()}"
            note_id = (qs.get("noteId") or qs.get("note_id") or qs.get("id") or [""])[0]
            if isinstance(note_id, str) and note_id:
                return f"xhs:{note_id.lower()}"

        # Generic: remove fragment; keep scheme+host+path; keep a small stable subset of query params.
        scheme = (parsed.scheme.lower() if parsed and parsed.scheme else "http")
        stable_keys = ["id", "mid", "tid", "sid", "video_id", "noteId", "note_id"]
        stable_parts = []
        for k in stable_keys:
            if k in qs and qs[k]:
                stable_parts.append(f"{k}={qs[k][0]}")
        stable_q = ("?" + "&".join(stable_parts)) if stable_parts else ""
        if host:
            return f"{scheme}://{host}{path}{stable_q}"
        return url

    def _match_or_create_event(self, sentiment, hospital_name, analysis):
        cfg = self._event_dedupe_config()
        if not cfg["enabled"]:
            return None, False, None

        raw_url = (sentiment.get("url") or "").strip()
        source = sentiment.get("webName", "") or ""
        norm_url = self._normalize_event_url(raw_url, source)
        # Use normalized key for matching/storing. Keep raw_url separately for UI/linking.
        url = norm_url or raw_url
        now = self._now_local_str()
        window_start = (datetime.now() - timedelta(days=cfg["window_days"]))\
            .strftime("%Y-%m-%d %H:%M:%S")

        title = sentiment.get("title", "") or ""
        reason = analysis.get("reason", "") or ""
        sentiment_id = sentiment.get("id", "") or ""

        # 硬匹配：URL 相同
        # Backward compat: old rows may have stored raw_url; match both.
        if url or raw_url:
            keys = []
            if url:
                keys.append(url)
            if raw_url and raw_url not in keys:
                keys.append(raw_url)

            if len(keys) == 1:
                where = "event_url = ?"
                params = (hospital_name, keys[0])
            else:
                where = "(event_url = ? OR event_url = ?)"
                params = (hospital_name, keys[0], keys[1])

            row = db.execute(
                self.project_root,
                f"""
                SELECT id, total_count, event_url
                FROM event_groups
                WHERE hospital_name = ? AND {where}
                ORDER BY last_seen_at DESC
                LIMIT 1
                """,
                params,
                fetchone=True
            )
            if row:
                total_count = (row.get("total_count") or 0) + 1
                db.execute(
                    self.project_root,
                    """
                    UPDATE event_groups
                    SET total_count = total_count + 1,
                        last_seen_at = ?,
                        last_title = ?,
                        last_reason = ?,
                        last_source = ?,
                        last_sentiment_id = ?
                    WHERE id = ?
                    """,
                    (now, title, reason, source, sentiment_id, row["id"])
                )
                # Prefer normalized key for future matches.
                if url and row.get("event_url") != url:
                    db.execute(
                        self.project_root,
                        "UPDATE event_groups SET event_url = ? WHERE id = ?",
                        (url, row["id"]),
                    )
                return row["id"], True, total_count

        # 软匹配：SimHash + 时间窗 + 同医院
        #
        # 按需求：软匹配仅采用“标题”做指纹（更可控、可解释）。
        # 注意：如果标题为空，再兜底用正文避免指纹为 0。
        text = re.sub(r"\\s+", " ", (title or "")).strip()
        if not text:
            content_main = (sentiment.get("allContent") or sentiment.get("content") or "").strip()
            ocr_main = (sentiment.get("ocrData") or "").strip()
            body = content_main if len(content_main) >= len(ocr_main) else ocr_main
            if len(body) > 400:
                body = body[:400]
            text = re.sub(r"\\s+", " ", body).strip()

        fingerprint = self._compute_simhash(text)
        candidates = db.execute(
            self.project_root,
            """
            SELECT id, fingerprint, total_count, event_url
            FROM event_groups
            WHERE hospital_name = ? AND last_seen_at >= ?
            """,
            (hospital_name, window_start),
            fetchall=True
        ) or []

        best_row = None
        best_dist = 999
        for row in candidates:
            fp = row.get("fingerprint")
            if fp is None:
                continue
            dist = self._hamming_distance(int(fingerprint), int(fp))
            if dist < best_dist:
                best_dist = dist
                best_row = row

        if best_row and best_dist <= cfg["max_distance"]:
            total_count = (best_row.get("total_count") or 0) + 1
            db.execute(
                self.project_root,
                """
                UPDATE event_groups
                SET total_count = total_count + 1,
                    last_seen_at = ?,
                    last_title = ?,
                    last_reason = ?,
                    last_source = ?,
                    last_sentiment_id = ?
                WHERE id = ?
                """,
                (now, title, reason, source, sentiment_id, best_row["id"])
            )
            if url and not best_row.get("event_url"):
                db.execute(
                    self.project_root,
                    "UPDATE event_groups SET event_url = ? WHERE id = ?",
                    (url, best_row["id"])
                )
            return best_row["id"], True, total_count

        # 新事件：创建事件池
        event_id = db.execute_with_lastrowid(
            self.project_root,
            """
            INSERT INTO event_groups
            (hospital_name, fingerprint, event_url, total_count, last_title, last_reason, last_source, last_sentiment_id, created_at, last_seen_at)
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
            """,
            (hospital_name, fingerprint, url or None, title, reason, source, sentiment_id, now, now)
        )
        return event_id, False, 1
    
    def is_email_processed(self, token):
        """检查邮件是否已处理"""
        row = db.execute(
            self.project_root,
            'SELECT id FROM processed_emails WHERE token = ?',
            (token,),
            fetchone=True
        )
        return row is not None
    
    def mark_email_processed(self, token, hospital_name, email_date):
        """标记邮件已处理"""
        try:
            db.execute(
                self.project_root,
                '''
                INSERT INTO processed_emails (token, hospital_name, email_date, processed_at)
                VALUES (?, ?, ?, ?)
                ''',
                (token, hospital_name, email_date, self._now_local_str()),
            )
            self.logger.info(f"邮件已标记处理: {token[:20]}...")
        except Exception:
            self.logger.warning(f"邮件已存在: {token[:20]}...")
    
    def save_negative_sentiment(self, sentiment, hospital_name, analysis, event_id=None, is_duplicate=False):
        """保存负面舆情"""
        db.execute(
            self.project_root,
            '''
            INSERT INTO negative_sentiments 
            (sentiment_id, event_id, hospital_name, title, source, content, reason, severity, url, is_duplicate, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                sentiment.get('id', ''),
                event_id,
                hospital_name,
                sentiment.get('title', ''),
                sentiment.get('webName', ''),
                sentiment.get('ocrData') or sentiment.get('allContent', ''),
                analysis['reason'],
                analysis['severity'],
                sentiment.get('url', ''),
                1 if is_duplicate else 0,
                self._now_local_str()
            )
        )
        
        self.logger.info(f"负面舆情已保存到数据库")

    def queue_feedback(self, sentiment_id, recipients):
        """记录可反馈的舆情队列"""
        if not sentiment_id:
            return

        if not recipients:
            recipients = ['@all']
        elif isinstance(recipients, str):
            recipients = [recipients]

        sent_time = self._now_local_str()
        for user_id in recipients:
            db.execute(
                self.project_root,
                '''
                INSERT INTO feedback_queue (sentiment_id, user_id, sent_time, created_at)
                VALUES (?, ?, ?, ?)
                ''',
                (sentiment_id, user_id, sent_time, sent_time)
            )

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

                    # 事件归并（重复舆情简化推送）
                    event_id, is_duplicate, event_total = self._match_or_create_event(
                        sentiment, hospital_name, analysis
                    )

                    # 保存到数据库
                    self.save_negative_sentiment(
                        sentiment, hospital_name, analysis,
                        event_id=event_id, is_duplicate=is_duplicate
                    )

                    # 发送通知并记录反馈队列
                    sentiment_info = {
                        'id': sentiment.get('id', ''),
                        'source': sentiment.get('webName', '未知'),
                        'title': sentiment.get('title', '无标题'),
                        'reason': analysis.get('reason', ''),
                        'severity': analysis.get('severity', 'medium'),
                        'url': sentiment.get('url', ''),
                        'duplicate': bool(is_duplicate),
                        'event_id': event_id,
                        'event_total': event_total
                    }
                    content = sentiment.get('allContent', '') or sentiment.get('content', '')
                    notify_result = self.notifier.send(
                        title="发现负面舆情" if not is_duplicate else "重复舆情提醒",
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
