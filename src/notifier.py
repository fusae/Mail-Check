#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知模块
支持Server酱、企业微信、钉钉、Telegram等多种通知方式
"""

import hashlib
import hmac
import json
import logging
import os
from urllib.parse import urlencode

import requests
import yaml

class Notifier:
    def __init__(self, config):
        self.config = config.get('notification', {})
        self.feedback_config = config.get('feedback', {})
        self.provider = self.config.get('provider', 'console')  # 默认控制台输出
        self.logger = logging.getLogger(__name__)
        
        # 加载各平台配置
        self.telegram = self.config.get('telegram', {})
        self.serverchan = self.config.get('serverchan', {})
        self.wechat_work = self.config.get('wechat_work', {})
        self.dingtalk = self.config.get('dingtalk', {})
        self.suppress_keywords = self._load_suppress_keywords()
        self.hospital_contacts, self.contact_mentions = self._load_hospital_contacts()

    
    def _load_hospital_contacts(self):
        contacts_file = self.config.get('hospital_contacts_file', 'config/hospital_contacts.yaml')
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = contacts_file if os.path.isabs(contacts_file) else os.path.join(base_dir, contacts_file)

        if not os.path.exists(path):
            self.logger.warning(f"医院联系人配置文件不存在: {path}")
            return {}, {}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            hospitals = data.get('hospitals', {}) or {}
            mentions = data.get('mentions', {}) or {}
            return hospitals, mentions
        except Exception as e:
            self.logger.error(f"读取医院联系人配置失败: {e}")
            return {}, {}

    def _get_config_path(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, 'config', 'config.yaml')

    def _load_suppress_keywords(self):
        keywords = []
        raw_list = []

        config_path = self._get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = yaml.safe_load(f) or {}
                notification = cfg.get('notification', {}) or {}
                wechat_cfg = notification.get('wechat_work', {}) or {}
                raw_list = wechat_cfg.get('suppress_keywords') or notification.get('suppress_keywords') or []
            except Exception as e:
                self.logger.warning(f"读取屏蔽关键词失败，将使用内存配置: {e}")

        if not raw_list:
            raw_list = self.wechat_work.get('suppress_keywords') or self.config.get('suppress_keywords') or []
        if isinstance(raw_list, str):
            raw_list = [raw_list]
        for item in raw_list:
            if not item:
                continue
            text = str(item).strip()
            if text:
                keywords.append(text)
        return keywords

    def _should_suppress_wechat(self, content, sentiment_info):
        # 运行时刷新关键词，确保网页端更新后即时生效
        self.suppress_keywords = self._load_suppress_keywords()
        if not self.suppress_keywords:
            return False, ""
        content = content or ""
        title = (sentiment_info or {}).get('title', '') or ''
        reason = (sentiment_info or {}).get('reason', '') or ''
        source = (sentiment_info or {}).get('source', '') or ''
        haystack = f"{title}\n{reason}\n{source}\n{content}"
        for keyword in self.suppress_keywords:
            if keyword in haystack:
                return True, keyword
        return False, ""

    def send(self, title, content, hospital_name=None, sentiment_info=None):
        """
        发送通知
        
        Args:
            title: 标题
            content: 内容
            hospital_name: 医院名称
            sentiment_info: 舆情详细信息
        """
        self.logger.info(f"准备发送通知: {title}")
        sentiment_info = sentiment_info or {}
        
        if self.provider == 'telegram':
            result = self._send_via_telegram(title, content, hospital_name, sentiment_info)
        elif self.provider == 'serverchan':
            result = self._send_via_serverchan(title, content, hospital_name, sentiment_info)
        elif self.provider == 'wechat_work':
            suppressed, hit = self._should_suppress_wechat(content, sentiment_info)
            if suppressed:
                self.logger.info(f"命中屏蔽关键词，已跳过企业微信推送: {hit}")
                return {'success': False, 'suppressed': True, 'keyword': hit}
            result = self._send_via_wechat_work(title, content, hospital_name, sentiment_info)
        elif self.provider == 'dingtalk':
            result = self._send_via_dingtalk(title, content, hospital_name, sentiment_info)
        else:
            self.logger.warning(f"不支持的通知方式: {self.provider}")
            result = self._print_to_console(title, content, hospital_name, sentiment_info)

        if isinstance(result, dict):
            return result
        return {'success': bool(result)}
    
    def _print_to_console(self, title, content, hospital_name=None, sentiment_info=None):
        """输出到控制台（备用方式）"""
        print("\n" + "!" * 50)
        print(f"⚠️ {title}")
        print("!" * 50)
        print(f"医院: {hospital_name}")
        if sentiment_info:
            print(f"来源: {sentiment_info.get('source', '未知')}")
            print(f"标题: {sentiment_info.get('title', '无标题')}")
            content_preview = content[:200] if len(content) > 200 else content
            print(f"内容摘要: {content_preview}...")
            print(f"AI判断: {sentiment_info.get('reason', '未判断')}")
            print(f"严重程度: {sentiment_info.get('severity', 'medium')}")
        print("!" * 50 + "\n")
        
        return True
    
    def _send_via_telegram(self, title, content, hospital_name, sentiment_info):
        """通过Telegram发送"""
        try:
            # 获取配置
            bot_token = self.telegram.get('bot_token', '')
            chat_id = self.telegram.get('chat_id', '')
            message_prefix = self.telegram.get('message_prefix', '【舆情监控】')
            enable_html = self.telegram.get('enable_html', True)
            enable_preview = self.telegram.get('enable_preview', True)
            enable_markdown = self.telegram.get('enable_markdown', False)
            
            if not bot_token:
                self.logger.warning("Telegram Bot Token未配置")
                return self._print_to_console(title, content, hospital_name, sentiment_info)
            if not chat_id:
                self.logger.warning("Telegram Chat ID未配置")
                return self._print_to_console(title, content, hospital_name, sentiment_info)
            
            # 构建消息内容
            if enable_markdown and not enable_html:
                # Markdown格式
                source = sentiment_info.get('source', '未知')
                url = sentiment_info.get('url', '')
                sentiment_id = sentiment_info.get('id') or sentiment_info.get('sentiment_id')

                if url and source in ('抖音', '小红书') and sentiment_id:
                    detail_url = f"https://console.microvivid.com/h5ListDetail?id={sentiment_id}"
                    url_line = f"**舆情链接：** [查看详情]({detail_url})"
                elif url:
                    url_line = f"**原文链接：** [{url}]({url})"
                else:
                    url_line = ""

                message = f"""
{message_prefix} **{title}**

**医院：** {hospital_name}

**来源：** {source}
**AI判断：** {sentiment_info.get('reason', '未判断')}
**严重程度：** {sentiment_info.get('severity', 'medium')}
{url_line}

**详细内容：**
{content}

请及时查看详情。
"""
            elif enable_html:
                # HTML格式
                source = sentiment_info.get('source', '未知')
                url = sentiment_info.get('url', '')
                sentiment_id = sentiment_info.get('id') or sentiment_info.get('sentiment_id')

                if url and source in ('抖音', '小红书') and sentiment_id:
                    detail_url = f"https://console.microvivid.com/h5ListDetail?id={sentiment_id}"
                    url_html = f'<a href="{detail_url}">查看详情</a>'
                    link_label = "舆情链接"
                elif url:
                    url_html = f'<a href="{url}">{url}</a>'
                    link_label = "原文链接"
                else:
                    url_html = '无'
                    link_label = "原文链接"

                message = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px; line-height: 1.6;">
    <h2 style="color: #e74c3c;">{message_prefix} {title}</h2>
    <table style="border-collapse: collapse; width: 100%; max-width: 800px;">
        <tr style="background-color: #f8f9fa;">
            <th style="padding: 12px; text-align: left; border: 1px solid #dee2e6; text-align: left; font-weight: bold;">
                项目
            </th>
            <th style="padding: 12px; text-align: left; border: 1px solid #dee2e6; text-align: left;">
                内容
            </th>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">
                医院
            </td>
            <td style="padding: 12px; border: 1px solid #dee2e6;">
                {hospital_name}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">
                来源
            </td>
            <td style="padding:  0px; border: 1px solid #dee2e6;">
                {source}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">
                标题
            </td>
            <td style="padding: 0px; border: 1px solid #dee2e6;">
                {sentiment_info.get('title', '无标题')}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">
                AI判断
            </td>
            <td style="padding: 0px; border: 1px solid #dee2e6; color: #e74c3c;">
                {sentiment_info.get('reason', '未判断')}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">
                严重程度
            </td>
            <td style="padding: 0px; border: 1px solid #dee2e6;">
                <span style="background-color:
                    {'#e74c3c' if sentiment_info.get('severity') == 'high' else
                     '#f0ad0e' if sentiment_info.get('severity') == 'medium' else
                     '#6c757d' if sentiment_info.get('severity') == 'low' else '#95a5a6'}>
                {sentiment_info.get('severity', 'medium')}
                </span>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">
                {link_label}
            </td>
            <td style="padding: 0px; border: 1px solid #dee2e6;">
                {url_html}
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold; vertical-align: top;">
                内容摘要
            </td>
            <td style="padding: 0px; border: 1px solid #dee2e6;">
                <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                    {content[:500]}
                    {'...' if len(content) > 500 else ''}
                </div>
                </td>
        </tr>
    </table>

    <script>
        window.top.close();
    </script>
</body>
</html>
"""
            else:
                # 纯文本格式（默认）
                message = f"""
{message_prefix} {title}

医院: {hospital_name}
来源: {sentiment_info.get('source', '未知')}
标题: {sentiment_info.get('title', '无标题')}
AI判断: {sentiment_info.get('reason', '未判断')}
严重程度: {sentiment_info.get('severity', 'medium')}

详细内容:
{content}

请及时查看详情。
"""
            
            # Telegram API调用
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            params = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown' if enable_markdown else None
            }
            
            self.logger.info(f"发送Telegram消息到: {chat_id}")
            proxies = {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}
            response = requests.post(url, params=params, proxies=proxies, timeout=10)
            
            result = response.json()
            
            if result.get('ok'):
                self.logger.info("✓ Telegram通知发送成功")
                return True
            else:
                self.logger.error(f"✗ Telegram通知失败: {result.get('description', '未知错误')}")
                return self._print_to_console(title, content, hospital_name, sentiment_info)
        
        except requests.exceptions.Timeout:
            self.logger.error("Telegram请求超时")
            return self._print_to_console(title, content, hospital_name, sentiment_info)
        except Exception as e:
            self.logger.error(f"Telegram通知异常: {e}")
            return self._print_to_console(title, content, hospital_name, sentiment_info)
    
    def _send_via_serverchan(self, title, content, hospital_name, sentiment_info):
        """通过Server酱发送"""
        try:
            sendkey = self.serverchan.get('sendkey', '')
            
            if not sendkey:
                self.logger.warning("Server酱SendKey未配置")
                return self._print_to_console(title, content, hospital_name, sentiment_info)
            
            source = sentiment_info.get('source', '未知')
            sent_title = sentiment_info.get('title', '无标题')
            reason = sentiment_info.get('reason', '未判断')
            severity = sentiment_info.get('severity', 'medium')
            
            # 构建完整内容
            full_content = f"""
医院: {hospital_name}
来源: {source}
标题: {sent_title}
AI判断: {reason}
严重程度: {severity}

详细内容:
{content}
"""
            
            # Server酱API
            url = "https://sctapi.ftqq.com/SendKey/send"
            params = {
                'SendKey': sendkey,
                'title': f"【舆情监控】{title}",
                'desp': full_content
            }
            
            self.logger.info(f"发送Server酱通知...")
            response = requests.post(url, params=params, timeout=10)
            
            result = response.json()
            
            if result.get('code') == 0:
                self.logger.info("✓ Server酱通知发送成功")
                return True
            else:
                self.logger.error(f"✗ Server酱通知失败: {result.get('message', '未知错误')}")
                return self._print_to_console(title, content, hospital_name, sentiment_info)
        
        except requests.exceptions.Timeout:
            self.logger.error("Server酱请求超时")
            return self._print_to_console(title, content, hospital_name, sentiment_info)
        except Exception as e:
            self.logger.error(f"Server酱通知异常: {e}")
            return self._print_to_console(title, content, hospital_name, sentiment_info)
    
    def _send_via_wechat_work(self, title, content, hospital_name, sentiment_info):
        """通过企业微信Webhook发送"""
        return self._send_via_wechat_work_webhook(title, content, hospital_name, sentiment_info)

    def _build_feedback_url(self, sentiment_id):
        base_url = self.feedback_config.get('link_base_url')
        secret = self.feedback_config.get('link_secret')
        if not base_url or not secret or not sentiment_id:
            return None

        message = f"{sentiment_id}".encode('utf-8')
        sig = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).hexdigest()

        query = urlencode({
            'sentiment_id': sentiment_id,
            'sig': sig
        })

        joiner = '&' if '?' in base_url else '?'
        return f"{base_url}{joiner}{query}"

    def _format_wechat_markdown(self, title, content, hospital_name, sentiment_info):
        sentiment_id = sentiment_info.get('id') or sentiment_info.get('sentiment_id')
        source = sentiment_info.get('source', '未知')
        sent_title = sentiment_info.get('title', '无标题')
        reason = sentiment_info.get('reason', '未判断')
        severity = sentiment_info.get('severity', 'medium')
        is_duplicate = bool(sentiment_info.get('duplicate'))
        event_total = sentiment_info.get('event_total')
        feedback_url = self._build_feedback_url(sentiment_id)
        feedback_line = f"\n**反馈链接：** [点击反馈]({feedback_url})\n" if feedback_url else ""
        event_line = f"> **事件累计：** {event_total} 条\n" if event_total else ""

        if is_duplicate:
            return f"""### ♻️ 重复舆情提醒

**{title}**

> **医院：** {hospital_name}
> **来源：** {source}
> **标题：** {sent_title}
> **AI判断：** {reason}
> **严重程度：** {severity}
{event_line}
请注意该事件已多次出现。

{feedback_line}
"""

        return f"""### ⚠️ 舆情监控通知

**{title}**

> **医院：** {hospital_name}
> **来源：** {source}
> **标题：** {sent_title}
> **AI判断：** {reason}
> **严重程度：** {severity}
**详细内容：**
{content}

请及时查看详情。

{feedback_line}
"""

    def _send_via_wechat_work_webhook(self, title, content, hospital_name, sentiment_info):
        """通过企业微信Webhook发送（不支持回调）"""
        try:
            webhook_url = self.wechat_work.get('webhook_url', '')

            if not webhook_url:
                self.logger.warning("企业微信Webhook URL未配置")
                return self._print_to_console(title, content, hospital_name, sentiment_info)

            # 企业微信 Markdown 内容限制 4096（按字节更稳妥）
            MAX_BYTES = 4096
            BUFFER_BYTES = 200  # 预留缓冲（字节）

            def _utf8_len(s):
                return len(s.encode('utf-8'))

            def _truncate_utf8(s, max_bytes):
                if max_bytes <= 0:
                    return ""
                return s.encode('utf-8')[:max_bytes].decode('utf-8', errors='ignore')

            # 先构建消息（包含完整反馈链接）
            sentiment_id = sentiment_info.get('id') or sentiment_info.get('sentiment_id')
            feedback_url = self._build_feedback_url(sentiment_id)
            feedback_line = f"\n**反馈链接：** [点击反馈]({feedback_url})\n" if feedback_url else ""

            # 构建固定部分（不包括内容）
            source = sentiment_info.get('source', '未知')
            sent_title = sentiment_info.get('title', '无标题')
            reason = sentiment_info.get('reason', '未判断')
            severity = sentiment_info.get('severity', 'medium')
            is_duplicate = bool(sentiment_info.get('duplicate'))
            event_total = sentiment_info.get('event_total')
            url = sentiment_info.get('url', '')
            sentiment_id = sentiment_info.get('id') or sentiment_info.get('sentiment_id')

            # 固定文本模板（内容部分用占位符）
            # 原文链接和反馈链接单独构建，避免在 f-string 表达式里使用转义字符（会导致 SyntaxError）
            # 抖音链接使用详情页跳转，其他来源使用原始链接
            if url:
                if source in ('抖音', '小红书') and sentiment_id:
                    detail_url = f"https://console.microvivid.com/h5ListDetail?id={sentiment_id}"
                    orig_link_line = f"**舆情链接：** [查看详情]({detail_url})\n"
                    self.logger.info(f"{source}舆情，使用详情页链接: {detail_url}")
                else:
                    orig_link_line = f"**原文链接：** [{url}]({url})\n"
                    self.logger.info(f"非抖音/小红书舆情，使用原始链接: {url}")
            else:
                orig_link_line = ""
                self.logger.warning("未获取到URL")

            event_line = f"> **事件累计：** {event_total} 条\n" if event_total else ""
            if is_duplicate:
                header = (
                    f"### ♻️ 重复舆情提醒\n\n**{title}**\n\n"
                    f"> **医院：** {hospital_name}\n"
                    f"> **来源：** {source}\n"
                    f"> **标题：** {sent_title}\n"
                    f"> **AI判断：** {reason}\n"
                    f"> **严重程度：** {severity}\n"
                    f"{event_line}"
                    f"{orig_link_line}\n"
                )
                footer = f"\n请注意该事件已多次出现。\n{feedback_line}"
            else:
                header = (
                    f"### ⚠️ 舆情监控通知\n\n**{title}**\n\n"
                    f"> **医院：** {hospital_name}\n"
                    f"> **来源：** {source}\n"
                    f"> **标题：** {sent_title}\n"
                    f"> **AI判断：** {reason}\n"
                    f"> **严重程度：** {severity}\n"
                    f"{orig_link_line}\n"
                    f"**详细内容：**\n\n"
                )
                footer = f"\n\n请及时查看详情。\n{feedback_line}"

            # 计算可用空间（字节）
            fixed_bytes = _utf8_len(header) + _utf8_len(footer)
            available_bytes = MAX_BYTES - fixed_bytes - BUFFER_BYTES
            if available_bytes < 0:
                self.logger.warning(
                    f"固定内容过长（{fixed_bytes}字节），将仅保留关键字段并裁剪内容"
                )
                available_bytes = 0

            # 截断内容（重复舆情无需正文）
            suffix = "\n...（内容过长已截断，点击反馈链接查看完整信息）"
            suffix_bytes = _utf8_len(suffix)
            content_bytes = _utf8_len(content)
            if is_duplicate:
                truncated_content = ""
            elif content_bytes > available_bytes:
                # 精确计算截断后的内容长度，确保加上提示后不超过限制
                max_content_bytes = max(0, available_bytes - suffix_bytes)
                truncated_content = _truncate_utf8(content, max_content_bytes)
                if max_content_bytes > 0 and _utf8_len(truncated_content) + suffix_bytes <= max(0, available_bytes):
                    truncated_content += suffix
                self.logger.warning(
                    f"内容超限（{content_bytes}字节），截断为 {_utf8_len(truncated_content)} 字节，保留反馈链接"
                )
            else:
                truncated_content = content

            # 构建最终消息
            markdown_content = header + truncated_content + footer

            # 最终验证并兜底
            final_bytes = _utf8_len(markdown_content)
            if final_bytes > MAX_BYTES:
                # 先丢弃内容部分，再次尝试保留 footer（含反馈链接）
                markdown_content = header + footer
                final_bytes = _utf8_len(markdown_content)
                if final_bytes > MAX_BYTES:
                    footer_bytes = _utf8_len(footer)
                    allow_header = max(0, MAX_BYTES - footer_bytes - 3)
                    header_trim = _truncate_utf8(header, allow_header)
                    markdown_content = (header_trim + "..." + footer) if allow_header else ("..." + footer)
                self.logger.warning(f"最终长度 {final_bytes} 仍超限，已缩减头部与内容到 {_utf8_len(markdown_content)} 字节")

            markdown_msg = {
                "msgtype": "markdown",
                "markdown": {
                    "content": markdown_content
                }
            }

            self.logger.info(f"发送企业微信通知（Webhook），内容长度: {_utf8_len(markdown_content)} 字节")
            response = requests.post(webhook_url, json=markdown_msg, timeout=10)
            result = response.json()

            if result.get('errcode') == 0:
                self.logger.info("✓ 企业微信通知发送成功")
                # Duplicate events should not repeatedly ping responsible staff.
                if not bool((sentiment_info or {}).get("duplicate")):
                    self._send_wechat_mention(webhook_url, hospital_name, sentiment_info)
                return {'success': True}
            else:
                self.logger.error(f"✗ 企业微信通知失败: {result.get('errmsg', '未知错误')}")
                return self._print_to_console(title, content, hospital_name, sentiment_info)

        except requests.exceptions.Timeout:
            self.logger.error("企业微信请求超时")
            return self._print_to_console(title, content, hospital_name, sentiment_info)
        except Exception as e:
            self.logger.error(f"企业微信通知异常: {e}")
            return self._print_to_console(title, content, hospital_name, sentiment_info)

    def _send_wechat_mention(self, webhook_url, hospital_name, sentiment_info):
        """发送@提醒（仅 text 支持）"""
        mention = self._resolve_mention(hospital_name)
        if not mention:
            return False

        title = sentiment_info.get('title', '无标题')
        name = mention.get('name', '')
        content = f"@{name} 该医院有舆情需要关注：{hospital_name} | {title}"

        payload = {
            "msgtype": "text",
            "text": {
                "content": content,
                "mentioned_list": mention.get('mentioned_list', []),
                "mentioned_mobile_list": mention.get('mentioned_mobile_list', [])
            }
        }

        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            result = resp.json()
            if result.get('errcode') == 0:
                self.logger.info("✓ 企业微信@提醒发送成功")
                return True
            self.logger.warning(f"@提醒发送失败: {result.get('errmsg', '未知错误')}")
        except Exception as e:
            self.logger.warning(f"@提醒发送异常: {e}")
        return False

    def _resolve_mention(self, hospital_name):
        monitor_name = self.hospital_contacts.get(hospital_name)
        if not monitor_name:
            return None

        mention_info = self.contact_mentions.get(monitor_name, {}) or {}
        userid = mention_info.get('wechat_userid') or mention_info.get('userid')
        mobile = mention_info.get('wechat_mobile') or mention_info.get('mobile')

        if userid:
            return {
                'name': monitor_name,
                'mentioned_list': [userid],
                'mentioned_mobile_list': []
            }
        if mobile:
            return {
                'name': monitor_name,
                'mentioned_list': [],
                'mentioned_mobile_list': [mobile]
            }

        self.logger.warning(f"未配置监控人员的企业微信ID/手机号: {monitor_name}")
        return None
    
    def _send_via_dingtalk(self, title, content, hospital_name, sentiment_info):
        """通过钉钉发送（备用）"""
        try:
            webhook_url = self.dingtalk.get('webhook_url', '')
            
            if not webhook_url:
                self.logger.warning("钉钉Webhook URL未配置")
                return self._print_to_console(title, content, hospital_name, sentiment_info)
            
            # 钉钉Markdown格式
            source = sentiment_info.get('source', '未知')
            sent_title = sentiment_info.get('title', '无标题')
            reason = sentiment_info.get('reason', '未判断')
            severity = sentiment_info.get('severity', 'medium')
            
            markdown_msg = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"【舆情监控】{title}",
                    "text": f"""### ⚠️ 舆情监控通知

**医院：** {hospital_name}
**来源：** {source}
**AI判断：** {reason}
**严重程度：** {severity}

**详细内容：**
{content}

请及时查看详情。
"""
                }
            }
            
            self.logger.info("发送钉钉通知...")
            response = requests.post(webhook_url, json=markdown_msg, timeout=10)
            result = response.json()
            
            if result.get('errcode') == 0:
                self.logger.info("✓ 钉钉通知发送成功")
                return True
            else:
                self.logger.error(f"✗ 钉钉通知失败: {result.get('errmsg', '未知错误')}")
                return self._print_to_console(title, content, hospital_name, sentiment_info)
        
        except requests.exceptions.Timeout:
            self.logger.error("钉钉请求超时")
            return self._print_to_console(title, content, hospital_name, sentiment_info)
        except Exception as e:
            self.logger.error(f"钉钉通知异常: {e}")
            return self._print_to_console(title, content, hospital_name, sentiment_info)

if __name__ == '__main__':
    # 测试Telegram
    import sys
    os.chdir('src')
    sys.path.insert(0, '.')
    
    # 加载配置
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    notifier = Notifier(config)
    
    # 测试发送
    test_sentiment_info = {
        'source': '抖音',
        'title': '网红疑患性病病历流传',
        'url': 'https://www.douyin.com/share/video/7594672291024449253'
    }
    
    success = notifier.send(
        title="发现医院负面舆情",
        content="这是一条测试的负面舆情内容，包含医院信息...",
        hospital_name="东莞市第九人民医院",
        sentiment_info=test_sentiment_info
    )
    
    print(f"\n\nTelegram通知测试: {'成功' if success else '失败'}")
