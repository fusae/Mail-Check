#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通知模块
支持Server酱、企业微信、钉钉、Telegram等多种通知方式
"""

import requests
import logging
import yaml
import json

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
        
        if self.provider == 'telegram':
            return self._send_via_telegram(title, content, hospital_name, sentiment_info)
        elif self.provider == 'serverchan':
            return self._send_via_serverchan(title, content, hospital_name, sentiment_info)
        elif self.provider == 'wechat_work':
            return self._send_via_wechat_work(title, content, hospital_name, sentiment_info)
        elif self.provider == 'dingtalk':
            return self._send_via_dingtalk(title, content, hospital_name, sentiment_info)
        else:
            self.logger.warning(f"不支持的通知方式: {self.provider}")
            return self._print_to_console(title, content, hospital_name, sentiment_info)
    
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
        """通过企业微信发送（备用）"""
        try:
            webhook_url = self.wechat_work.get('webhook_url', '')
            
            if not webhook_url:
                self.logger.warning("企业微信Webhook URL未配置")
                return self._print_to_console(title, content, hospital_name, sentiment_info)
            
            # 企业微信Markdown格式
            source = sentiment_info.get('source', '未知')
            sent_title = sentiment_info.get('title', '无标题')
            reason = sentiment_info.get('reason', '未判断')
            severity = sentiment_info.get('severity', 'medium')
            
            markdown_msg = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"""### ⚠️ 舆情监控通知

**{title}**

> **医院：** {hospital_name}
> **来源：** {source}
> **AI判断：** {reason}
> **严重程度：** {severity}

**详细内容：**
{content}

请及时查看详情。
"""
                }
            }
            
            self.logger.info("发送企业微信通知...")
            response = requests.post(webhook_url, json=markdown_msg, timeout=10)
            result = response.json()
            
            if result.get('errcode') == 0:
                self.logger.info("✓ 企业微信通知发送成功")
                return True
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
            logger.error("钉钉请求超时")
            return self._print_to_console(title, content, hospital_name, sentiment_info)
        except Exception as e:
            logger.error(f"钉钉通知异常: {e}")
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
