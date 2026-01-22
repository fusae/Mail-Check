#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知模块
支持Server酱、企业微信、钉钉、Telegram等多种通知方式
"""

import json
import logging
import os

import requests
import yaml

from wechat_api import WeChatWorkAPI

class Notifier:
    def __init__(self, config):
        self.config = config.get('notification', {})
        self.provider = self.config.get('provider', 'console')  # 默认控制台输出
        self.logger = logging.getLogger(__name__)
        
        # 加载各平台配置
        self.telegram = self.config.get('telegram', {})
        self.serverchan = self.config.get('serverchan', {})
        self.wechat_work = self.config.get('wechat_work', {})
        self.dingtalk = self.config.get('dingtalk', {})

        self.wechat_api = None
        if self.wechat_work.get('corp_id') and self.wechat_work.get('agent_id') and self.wechat_work.get('secret'):
            self.wechat_api = WeChatWorkAPI(self.wechat_work)
    
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
        """通过企业微信发送（优先应用消息，回退Webhook）"""
        if self.wechat_api:
            result = self._send_via_wechat_work_app(title, content, hospital_name, sentiment_info)
            if result.get('success'):
                return result
            if self.wechat_work.get('webhook_url'):
                self.logger.warning("企业微信应用发送失败，尝试Webhook回退")
                return self._send_via_wechat_work_webhook(title, content, hospital_name, sentiment_info)
            return result

        return self._send_via_wechat_work_webhook(title, content, hospital_name, sentiment_info)

    def _get_wechat_recipients(self):
        to_user = self.wechat_work.get('to_user') or self.wechat_work.get('touser')
        to_party = self.wechat_work.get('to_party')
        to_tag = self.wechat_work.get('to_tag')

        if not to_user and not to_party and not to_tag:
            to_user = '@all'

        recipients = []
        if to_user and to_user != '@all':
            recipients = [u.strip() for u in to_user.split('|') if u.strip()]
        else:
            recipients = ['@all']

        return to_user, to_party, to_tag, recipients

    def _build_wechat_card(self, title, content, hospital_name, sentiment_info):
        sentiment_id = sentiment_info.get('id') or sentiment_info.get('sentiment_id')
        source = sentiment_info.get('source', '未知')
        sent_title = sentiment_info.get('title', '无标题')
        reason = sentiment_info.get('reason', '未判断')
        severity = sentiment_info.get('severity', 'medium')

        snippet = (content or '').replace('\n', ' ').strip()
        if len(snippet) > 120:
            snippet = snippet[:120] + '...'

        button_list = [{
            "text": "误判舆情",
            "style": 2,
            "key": f"false_positive_{sentiment_id}"
        }]

        if self.wechat_work.get('enable_confirm_button'):
            button_list.append({
                "text": "确认负面",
                "style": 1,
                "key": f"true_positive_{sentiment_id}"
            })

        card = {
            "card_type": "button_interaction",
            "source": {
                "desc": "舆情监控",
                "desc_color": 0
            },
            "main_title": {
                "title": title,
                "desc": f"医院：{hospital_name}"
            },
            "sub_title_text": (
                f"来源：{source}\n"
                f"标题：{sent_title}\n"
                f"AI判断：{reason}\n"
                f"严重程度：{severity}\n"
                f"摘要：{snippet}"
            ),
            "button_list": button_list
        }

        url = sentiment_info.get('url')
        if url:
            card["card_action"] = {
                "type": 1,
                "url": url
            }

        return card

    def _format_wechat_markdown(self, title, content, hospital_name, sentiment_info):
        source = sentiment_info.get('source', '未知')
        sent_title = sentiment_info.get('title', '无标题')
        reason = sentiment_info.get('reason', '未判断')
        severity = sentiment_info.get('severity', 'medium')

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
"""

    def _send_via_wechat_work_app(self, title, content, hospital_name, sentiment_info):
        """通过企业微信应用发送（支持按钮回调）"""
        if not self.wechat_api:
            return {'success': False, 'error': 'wechat_app_not_configured'}

        to_user, to_party, to_tag, recipients = self._get_wechat_recipients()
        sentiment_id = sentiment_info.get('id') or sentiment_info.get('sentiment_id')

        try:
            if sentiment_id:
                card = self._build_wechat_card(title, content, hospital_name, sentiment_info)
                result = self.wechat_api.send_template_card(to_user, card, to_party, to_tag)
            else:
                markdown = self._format_wechat_markdown(title, content, hospital_name, sentiment_info)
                result = self.wechat_api.send_markdown(to_user, markdown, to_party, to_tag)

            if result.get('success'):
                self.logger.info("✓ 企业微信应用通知发送成功")
                return {'success': True, 'msgid': result.get('msgid'), 'recipients': recipients}

            self.logger.error(f"✗ 企业微信应用通知失败: {result.get('error')}")
            return {'success': False, 'error': result.get('error')}

        except requests.exceptions.Timeout:
            self.logger.error("企业微信应用请求超时")
            return {'success': False, 'error': 'timeout'}
        except Exception as e:
            self.logger.error(f"企业微信应用通知异常: {e}")
            return {'success': False, 'error': str(e)}

    def _send_via_wechat_work_webhook(self, title, content, hospital_name, sentiment_info):
        """通过企业微信Webhook发送（不支持回调）"""
        try:
            webhook_url = self.wechat_work.get('webhook_url', '')

            if not webhook_url:
                self.logger.warning("企业微信Webhook URL未配置")
                return self._print_to_console(title, content, hospital_name, sentiment_info)

            markdown_msg = {
                "msgtype": "markdown",
                "markdown": {
                    "content": self._format_wechat_markdown(title, content, hospital_name, sentiment_info)
                }
            }

            self.logger.info("发送企业微信通知（Webhook）...")
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
