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
                message = f"""
{message_prefix} **{title}**

**医院：** {hospital_name}

**来源：** {sentiment_info.get('source', '未知')}
**AI判断：** {sentiment_info.get('reason', '未判断')}
**严重程度：** {sentiment_info.get('severity', 'medium')}
{f"**原文链接：** [{sentiment_info.get('url', '')}]({sentiment_info.get('url', '')})" if sentiment_info.get('url') else ""}

**详细内容：**
{content}

请及时查看详情。
"""
            elif enable_html:
                # HTML格式
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
                {sentiment_info.get('source', '未知')}
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
                     '#6c757d' if sentiment_info.get('severity') == 'low' else '#95a5a6'}">
                {sentiment_info.get('severity', 'medium')}
                </span>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">
                原文链接
            </td>
            <td style="padding: 0px; border: 1px solid #dee2e6;">
                {f'<a href="{sentiment_info.get("url", "")}">{sentiment_info.get("url", "无")}</a>' if sentiment_info.get('url') else '无'}
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
        feedback_url = self._build_feedback_url(sentiment_id)
        feedback_line = f"\n**反馈链接：** [点击反馈]({feedback_url})\n" if feedback_url else ""

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

            # 企业微信 Markdown 内容限制 4096 字符
            MAX_LENGTH = 4096
            BUFFER = 100  # 预留缓冲

            # 先构建消息（包含完整反馈链接）
            sentiment_id = sentiment_info.get('id') or sentiment_info.get('sentiment_id')
            feedback_url = self._build_feedback_url(sentiment_id)
            feedback_line = f"\n**反馈链接：** [点击反馈]({feedback_url})\n" if feedback_url else ""

            # 构建固定部分（不包括内容）
            source = sentiment_info.get('source', '未知')
            sent_title = sentiment_info.get('title', '无标题')
            reason = sentiment_info.get('reason', '未判断')
            severity = sentiment_info.get('severity', 'medium')
            url = sentiment_info.get('url', '')

            # 固定文本模板（内容部分用占位符）
            # 原文链接和反馈链接单独构建，避免在 f-string 表达式里使用转义字符（会导致 SyntaxError）
            orig_link_line = f"**原文链接：** [{url}]({url})\n" if url else ""

            header = f"### ⚠️ 舆情监控通知\n\n**{title}**\n\n> **医院：** {hospital_name}\n> **来源：** {source}\n> **标题：** {sent_title}\n> **AI判断：** {reason}\n> **严重程度：** {severity}\n{orig_link_line}\n**详细内容：**\n\n"
            footer = f"\n\n请及时查看详情。\n{feedback_line}"

            # 计算可用空间
            fixed_length = len(header) + len(footer)
            available_space = MAX_LENGTH - fixed_length - BUFFER

            # 截断内容
            if len(content) > available_space:
                # 精确计算截断后的内容长度，确保加上提示后不超过限制
                content_max_len = max(0, available_space - 20)  # 为提示与换行预留
                truncated_content = content[:content_max_len] + "\n...（内容过长已截断，点击反馈链接查看完整信息）"
                self.logger.warning(f"内容超限（{len(content)}字符），截断为 {len(truncated_content)} 字符，保留反馈链接")
            else:
                truncated_content = content

            # 构建最终消息
            markdown_content = header + truncated_content + footer

            # 最终验证并兜底
            final_length = len(markdown_content)
            if final_length > MAX_LENGTH:
                # 强制截断，确保不超过 MAX_LENGTH - 3（为了加 "..."）
                markdown_content = markdown_content[:MAX_LENGTH - 3] + "..."
                self.logger.warning(f"最终长度 {final_length} 仍超限，强制截断到 {len(markdown_content)} 字符")

            markdown_msg = {
                "msgtype": "markdown",
                "markdown": {
                    "content": markdown_content
                }
            }

            self.logger.info(f"发送企业微信通知（Webhook），内容长度: {len(markdown_content)} 字符")
            response = requests.post(webhook_url, json=markdown_msg, timeout=10)
            result = response.json()

            if result.get('errcode') == 0:
                self.logger.info("✓ 企业微信通知发送成功")
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
