#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信API封装
支持发送消息和接收回调
"""

import hashlib
import logging
import os
import time
import xml.etree.ElementTree as ET
from base64 import b64decode, b64encode

import requests
from Crypto.Cipher import AES

logger = logging.getLogger(__name__)


class WeChatWorkAPI:
    """企业微信API"""

    def __init__(self, config):
        """
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
        if self.access_token and self.expires_at and time.time() < self.expires_at:
            return self.access_token

        url = f"{self.base_url}/gettoken?corpid={self.corp_id}&corpsecret={self.secret}"
        response = requests.get(url, timeout=10)
        result = response.json()

        if result.get('errcode') == 0:
            self.access_token = result['access_token']
            self.expires_at = time.time() + result['expires_in'] - 300
            logger.info("获取access_token成功")
            return self.access_token

        logger.error(f"获取access_token失败: {result}")
        raise RuntimeError(f"获取access_token失败: {result}")

    def send_message(self, to_user: str, msg_type: str, content: dict, to_party: str = None, to_tag: str = None):
        """发送消息"""
        token = self.get_access_token()
        url = f"{self.base_url}/message/send?access_token={token}"

        data = {
            "msgtype": msg_type,
            "agentid": self.agent_id,
            msg_type: content
        }
        if to_user:
            data["touser"] = to_user
        if to_party:
            data["toparty"] = to_party
        if to_tag:
            data["totag"] = to_tag

        response = requests.post(url, json=data, timeout=10)
        result = response.json()

        if result.get('errcode') == 0:
            logger.info(f"消息发送成功: msgid={result.get('msgid')}")
            return {
                'success': True,
                'msgid': result.get('msgid'),
                'invaliduser': result.get('invaliduser', [])
            }

        logger.error(f"消息发送失败: {result}")
        return {
            'success': False,
            'error': result
        }

    def send_text(self, to_user: str, content: str, to_party: str = None, to_tag: str = None):
        """发送文本消息"""
        return self.send_message(to_user, 'text', {'content': content}, to_party, to_tag)

    def send_markdown(self, to_user: str, content: str, to_party: str = None, to_tag: str = None):
        """发送Markdown消息"""
        return self.send_message(to_user, 'markdown', {'content': content}, to_party, to_tag)

    def send_template_card(self, to_user: str, card: dict, to_party: str = None, to_tag: str = None):
        """发送模板卡片消息（用于反馈按钮）"""
        return self.send_message(to_user, 'template_card', card, to_party, to_tag)

    def verify_signature(self, msg_signature: str, timestamp: str, nonce: str, echostr: str):
        """验证URL有效性（GET请求）"""
        if not self.check_signature(msg_signature, timestamp, nonce, echostr):
            logger.error("签名验证失败")
            return None
        return self._decrypt(echostr)

    def check_signature(self, msg_signature: str, timestamp: str, nonce: str, encrypted: str):
        """验证POST请求签名"""
        params = [self.token, timestamp, nonce, encrypted]
        params.sort()
        signature = hashlib.sha1(''.join(params).encode('utf-8')).hexdigest()
        return signature == msg_signature

    def decrypt_message(self, encrypted_msg: str):
        """解密消息（POST请求）"""
        decrypted = self._decrypt(encrypted_msg)
        root = ET.fromstring(decrypted)
        message = {}
        for child in root:
            message[child.tag] = child.text
        return message

    def encrypt_message(self, message: str):
        """加密消息（用于回复）"""
        return self._encrypt(message)

    def _decrypt(self, encrypted: str):
        """AES解密"""
        aes_key = b64decode(self.encoding_aes_key + "=")
        cipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16])
        decrypted = b64decode(encrypted)
        plaintext = cipher.decrypt(decrypted)

        pad = plaintext[-1]
        plaintext = plaintext[:-pad]

        msg_len = int.from_bytes(plaintext[16:20], byteorder='big')
        msg_content = plaintext[20:20 + msg_len]
        corp_id = plaintext[20 + msg_len:].decode('utf-8')

        if self.corp_id and corp_id != self.corp_id:
            logger.warning(f"CorpId不匹配: {corp_id}")

        return msg_content.decode('utf-8')

    def _encrypt(self, plaintext: str):
        """AES加密"""
        aes_key = b64decode(self.encoding_aes_key + "=")
        rand_bytes = os.urandom(16)
        msg_len = len(plaintext.encode('utf-8')).to_bytes(4, byteorder='big')
        corp_id = (self.corp_id or '').encode('utf-8')
        content = rand_bytes + msg_len + plaintext.encode('utf-8') + corp_id

        pad = 16 - (len(content) % 16)
        content += bytes([pad] * pad)

        cipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16])
        encrypted = cipher.encrypt(content)
        return b64encode(encrypted).decode('utf-8')
