#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信API封装
支持发送消息和接收回调
"""

import requests
import json
import hashlib
import xml.etree.ElementTree as ET
from Crypto.Cipher import AES
from base64 import b64decode
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class WeChatWorkAPI:
    """企业微信API"""

    def __init__(self, config):
        """
        初始化企业微信API

        Args:
            config: 企业微信配置
                {
                    'corp_id': '企业ID',
                    'agent_id': '应用ID',
                    'secret': '应用密钥',
                    'token': '验证Token',
                    'encoding_aes_key': '加密密钥'
                }
        """
        self.corp_id = config.get('corp_id')
        self.agent_id = config.get('agent_id')
        self.secret = config.get('secret')
        self.token = config.get('token')
        self.encoding_aes_key = config.get('encoding_aes_key')

        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"
        self.access_token = None
        self.expires_at = None

    def get_access_token(self):
        """获取access_token"""
        # 检查是否有效
        if self.access_token and self.expires_at:
            import time
            if time.time() < self.expires_at:
                return self.access_token

        # 重新获取
        url = f"{self.base_url}/gettoken?corpid={self.corp_id}&corpsecret={self.secret}"
        response = requests.get(url, timeout=10)
        result = response.json()

        if result.get('errcode') == 0:
            self.access_token = result['access_token']
            self.expires_at = result['expires_in'] - 300  # 提前5分钟过期
            logger.info("获取access_token成功")
            return self.access_token
        else:
            logger.error(f"获取access_token失败: {result}")
            raise Exception(f"获取access_token失败: {result}")

    def send_message(self, to_user: str, msg_type: str, content: Dict):
        """
        发送消息

        Args:
            to_user: 接收人，@all表示所有人
            msg_type: 消息类型：text/markdown/textcard等
            content: 消息内容字典

        Returns:
            发送结果
        """
        token = self.get_access_token()
        url = f"{self.base_url}/message/send?access_token={token}"

        data = {
            "touser": to_user,
            "msgtype": msg_type,
            "agentid": self.agent_id,
            msg_type: content
        }

        response = requests.post(url, json=data, timeout=10)
        result = response.json()

        if result.get('errcode') == 0:
            logger.info(f"消息发送成功: msgid={result.get('msgid')}")
            return {
                'success': True,
                'msgid': result.get('msgid'),
                'invaliduser': result.get('invaliduser', [])
            }
        else:
            logger.error(f"消息发送失败: {result}")
            return {
                'success': False,
                'error': result
            }

    def send_text(self, to_user: str, content: str):
        """发送文本消息"""
        return self.send_message(to_user, 'text', {'content': content})

    def send_markdown(self, to_user: str, content: str):
        """发送Markdown消息"""
        return self.send_message(to_user, 'markdown', {'content': content})

    def send_text_card(self, to_user: str, title: str, description: str, url: str, btn_txt: str = "详情"):
        """发送文本卡片消息"""
        return self.send_message(to_user, 'textcard', {
            'title': title,
            'description': description,
            'url': url,
            'btntxt': btn_txt
        })

    def verify_signature(self, msg_signature: str, timestamp: str, nonce: str, echostr: str):
        """
        验证URL有效性（GET请求）

        Returns:
            验证通过返回echostr的解密结果
        """
        # 拼接字符串
        data = f"{self.token}{timestamp}{nonce}{echostr}"

        # SHA1加密
        sha1 = hashlib.sha1()
        sha1.update(data.encode('utf-8'))
        signature = sha1.hexdigest()

        if signature != msg_signature:
            logger.error("签名验证失败")
            return None

        # 解密echostr
        decrypted = self._decrypt(echostr)
        return decrypted

    def decrypt_message(self, encrypted_msg: str):
        """
        解密消息（POST请求）

        Args:
            encrypted_msg: 加密的消息

        Returns:
            解密后的消息字典
        """
        # 解密
        decrypted = self._decrypt(encrypted_msg)

        # 解析XML
        root = ET.fromstring(decrypted)
        message = {}

        for child in root:
            message[child.tag] = child.text

        return message

    def encrypt_message(self, message: str):
        """
        加密消息（用于回复）

        Args:
            message: 要发送的消息

        Returns:
            加密后的消息
        """
        # 加密
        encrypted = self._encrypt(message)
        return encrypted

    def _decrypt(self, encrypted: str):
        """
        AES解密

        Args:
            encrypted: Base64编码的加密字符串

        Returns:
            解密后的字符串
        """
        # 生成key
        aes_key = b64decode(self.encoding_aes_key + "=")

        # 解密
        cipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16])
        decrypted = b64decode(encrypted)

        # 解密
        plaintext = cipher.decrypt(decrypted)

        # 去除padding
        pad = plaintext[-1]
        plaintext = plaintext[:-pad]

        # 去除前16字节随机字符串 + 后4字节msg_len
        content = plaintext[16:-4]

        return content.decode('utf-8')

    def _encrypt(self, plaintext: str):
        """
        AES加密

        Args:
            plaintext: 明文

        Returns:
            Base64编码的密文
        """
        # 生成key
        aes_key = b64decode(self.encoding_aes_key + "=")

        # 生成16字节随机字符串
        import random
        rand_str = ''.join([chr(random.randint(0, 255)) for _ in range(16)])

        # 消息长度（4字节）
        msg_len = len(plaintext).to_bytes(4, byteorder='big')

        # 拼接
        content = rand_str.encode('latin-1') + msg_len + plaintext.encode('utf-8')

        # PKCS7 padding
        pad = 16 - (len(content) % 16)
        content += bytes([pad] * pad)

        # 加密
        cipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16])
        encrypted = cipher.encrypt(content)

        # Base64编码
        return b64encode(encrypted).decode('utf-8')

if __name__ == '__main__':
    # 测试代码
    config = {
        'corp_id': 'your_corp_id',
        'agent_id': '123456',
        'secret': 'your_secret',
        'token': 'your_token',
        'encoding_aes_key': 'your_aes_key'
    }

    api = WeChatWorkAPI(config)

    # 发送测试消息
    result = api.send_text('@all', '测试消息')
    print(result)
