#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件监控模块
负责连接邮箱（支持Gmail/163/等），读取新邮件，提取token链接和医院名称
"""

import imaplib
import email
from email.header import decode_header
import re
import yaml
from datetime import datetime
import logging

class EmailMonitor:
    def __init__(self, config):
        self.config = config['email']
        self.imap_server = self.config['imap_server']
        self.imap_port = self.config.get('imap_port', 993)
        self.email_address = self.config['email_address']
        self.app_password = self.config['app_password']
        self.sender = self.config['rules']['sender']
        self.subject_pattern = self.config['rules']['subject_pattern']

        # 根据邮箱服务器类型确定邮箱类型名称
        if "163.com" in self.imap_server:
            self.email_type_name = "163邮箱"
        elif "qq.com" in self.imap_server:
            self.email_type_name = "QQ邮箱"
        elif "gmail.com" in self.imap_server:
            self.email_type_name = "Gmail"
        else:
            self.email_type_name = "邮箱"

        self.logger = logging.getLogger(__name__)
    
    def connect(self):
        """连接到邮箱IMAP（支持Gmail/163等）"""
        try:
            # 使用指定端口连接
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.mail.login(self.email_address, self.app_password)
            status, data = self.mail.select('INBOX')
            if status != 'OK':
                status, data = self.mail.select('INBOX', readonly=True)
            if status != 'OK':
                self.logger.warning("无法选择INBOX，尝试列出邮箱文件夹")
                status, mailboxes = self.mail.list()
                if status == 'OK' and mailboxes:
                    inbox = None
                    for line in mailboxes:
                        name = line.decode(errors='ignore')
                        if 'INBOX' in name.upper():
                            inbox = name.split(' "/" ')[-1].strip('"')
                            break
                    if inbox:
                        status, data = self.mail.select(inbox)
                if status != 'OK':
                    self.logger.error(f"选择邮箱失败，响应: {data}")
                    raise RuntimeError("无法选择邮件文件夹，服务器未进入SELECTED状态")
            
            # 根据邮箱类型显示不同的日志
            self.logger.info(f"成功连接到{self.email_type_name}: {self.email_address}")
            return True
        except Exception as e:
            self.logger.error(f"连接{self.email_type_name}失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        try:
            self.mail.close()
            self.mail.logout()
            self.logger.info("已断开邮箱连接")
        except:
            pass
    
    def get_new_emails(self):
        """获取未读邮件"""
        try:
            # 搜索来自指定发件人的未读邮件
            search_criteria = f'(FROM "{self.sender}")'
            status, messages = self.mail.search(None, 'UNSEEN', search_criteria)
            
            if status != 'OK':
                self.logger.warning("未找到新邮件")
                return []
            
            email_ids = messages[0].split()
            self.logger.info(f"找到 {len(email_ids)} 封新邮件")
            
            emails = []
            for email_id in email_ids:
                email_data = self.mail.fetch(email_id, '(RFC822)')[1]
                raw_email = email_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                email_info = self.parse_email(msg)
                if email_info:
                    emails.append(email_info)
                self.mark_email_seen(email_id)
            
            return emails
        except Exception as e:
            self.logger.error(f"获取邮件失败: {e}")
            return []
    
    def parse_email(self, msg):
        """解析邮件，提取关键信息"""
        try:
            # 获取主题
            subject = self.decode_header_value(msg['Subject'])
            
            # 获取发件人
            sender = self.decode_header_value(msg['From'])
            
            # 检查主题是否匹配
            if not re.search(self.subject_pattern, subject):
                self.logger.info(f"跳过邮件（主题不匹配）: {subject}")
                return None
            
            # 获取邮件正文
            body = self.get_email_body(msg)
            
            # 提取token链接
            token = self.extract_token(body)
            
            # 提取医院名称
            hospital_name = self.extract_hospital_name(body)
            
            if not token:
                self.logger.warning(f"未找到token链接: {subject}")
                return None
            
            return {
                'subject': subject,
                'sender': sender,
                'token': token,
                'hospital_name': hospital_name,
                'body': body,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            self.logger.error(f"解析邮件失败: {e}")
            return None
    
    def decode_header_value(self, header_value):
        """解码邮件头"""
        if not header_value:
            return ""
        
        decoded = []
        for part, encoding in decode_header(header_value):
            if isinstance(part, bytes):
                decoded.append(part.decode(encoding or 'utf-8', errors='ignore'))
            else:
                decoded.append(str(part))
        return ''.join(decoded)
    
    def get_email_body(self, msg):
        """获取邮件正文"""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    body = part.get_payload(decode=True)
                    try:
                        body = body.decode('utf-8', errors='ignore')
                    except:
                        pass
                    break
                elif content_type == 'text/html':
                    body = part.get_payload(decode=True)
                    try:
                        body = body.decode('utf-8', errors='ignore')
                    except:
                        pass
                    break
        else:
            body = msg.get_payload(decode=True)
            try:
                body = body.decode('utf-8', errors='ignore')
            except:
                pass
        
        return body
    
    def extract_token(self, body):
        """从邮件中提取token"""
        # 匹配格式: https://lt.microvivid.com/h5List?token=xxxxx
        pattern = r'https://lt\.microvivid\.com/h5List\?token=([a-zA-Z0-9_-]+)'
        match = re.search(pattern, body)
        
        if match:
            return match.group(1)
        return None
    
    def extract_hospital_name(self, body):
        """从邮件中提取医院名称"""
        # 匹配格式: 以下是某某方案的网路舆情信息
        pattern = r'以下是(.*?)方案的网路舆情信息'
        match = re.search(pattern, body)

        if match:
            hospital_name = match.group(1).strip()
            self.logger.info(f"提取到医院名称: {hospital_name}")
            return hospital_name

        self.logger.warning("未提取到医院名称")
        return None

    def mark_email_seen(self, email_id):
        """标记邮件为已读，避免重复处理"""
        try:
            self.mail.store(email_id, '+FLAGS', '\\Seen')
        except Exception as e:
            self.logger.warning(f"标记邮件已读失败: {e}")

if __name__ == '__main__':
    # 测试代码
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    monitor = EmailMonitor(config)
    
    if monitor.connect():
        emails = monitor.get_new_emails()
        
        for i, email_info in enumerate(emails, 1):
            print(f"\n邮件 {i}:")
            print(f"  主题: {email_info['subject']}")
            print(f"  医院: {email_info['hospital_name']}")
            print(f"  Token: {email_info['token']}")
        
        monitor.disconnect()
