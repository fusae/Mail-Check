#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用代理测试Telegram通知功能
"""

import sys
import os
import logging
import yaml
import os

# 设置代理（如果有的话）
# os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
# os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from notifier import Notifier

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """测试带代理的Telegram通知"""
    
    print("=" * 60)
    print("测试Telegram通知（带代理）")
    print("=" * 60)
    
    # 检查代理设置
    http_proxy = os.environ.get('HTTP_PROXY')
    https_proxy = os.environ.get('HTTPS_PROXY')
    
    if http_proxy or https_proxy:
        print(f"\n✅ 已配置代理:")
        if http_proxy:
            print(f"   HTTP_PROXY: {http_proxy}")
        if https_proxy:
            print(f"   HTTPS_PROXY: {https_proxy}")
    else:
        print("\n⚠️ 未配置代理，Telegram通知可能失败")
        print("   如果您有代理，请设置环境变量 HTTP_PROXY 和 HTTPS_PROXY")
    
    # 读取配置
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 创建通知器
    notifier = Notifier(config)
    
    # 模拟一条负面舆情
    test_data = {
        'title': '【舆情测试】发现负面舆情（代理模式）',
        'content': '测试内容：这是一条测试消息，用于验证Telegram通知功能是否正常工作。',
        'hospital_name': '测试医院',
        'sentiment_info': {
            'source': '测试',
            'title': '测试消息',
            'reason': '测试Telegram通知功能',
            'severity': 'medium'
        }
    }
    
    print("\n发送测试消息...")
    result = notifier.send(
        title=test_data['title'],
        content=test_data['content'],
        hospital_name=test_data['hospital_name'],
        sentiment_info=test_data['sentiment_info']
    )
    
    if result:
        print("\n✅ Telegram通知发送成功！")
        print("请检查您的Telegram群组")
    else:
        print("\n❌ Telegram通知发送失败！")
        print("原因：可能是网络问题或代理配置不正确")
    
    return result

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
