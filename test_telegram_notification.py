#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Telegram通知功能
模拟发送一条负面舆情通知
"""

import sys
import os
import logging
import yaml

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from notifier import Notifier

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_telegram_notification():
    """测试Telegram通知功能"""
    
    print("=" * 60)
    print("开始测试Telegram通知功能")
    print("=" * 60)
    
    # 读取配置
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 创建通知器
    notifier = Notifier(config)
    
    # 模拟一条负面舆情
    test_data = {
        'title': '【舆情测试】发现负面舆情',
        'content': '''某医院发生医疗纠纷事件，患者家属在医院大厅聚集抗议，质疑医院的治疗方案和医疗费用。该事件已在社交媒体上广泛传播，引发公众关注和讨论。医院方面表示正在积极处理此事，但舆情影响仍在扩大。这起事件可能对医院声誉造成负面影响，建议及时回应和处理。''',
        'hospital_name': '测试医院（东莞市第九人民医院）',
        'sentiment_info': {
            'source': '微博',
            'title': '某医院发生医疗纠纷事件',
            'reason': '医疗纠纷负面舆情，涉及医院声誉和服务质量，已在社交媒体传播，对医院形象造成负面影响',
            'severity': 'high'
        }
    }
    
    print("\n" + "!" * 60)
    print("⚠️ 测试数据：")
    print("!" * 60)
    print(f"医院: {test_data['hospital_name']}")
    print(f"来源: {test_data['sentiment_info']['source']}")
    print(f"标题: {test_data['sentiment_info']['title']}")
    print(f"AI判断: {test_data['sentiment_info']['reason']}")
    print(f"严重程度: {test_data['sentiment_info']['severity']}")
    print(f"内容长度: {len(test_data['content'])} 字符")
    print("!" * 60 + "\n")
    
    # 发送通知
    print("正在发送Telegram通知...\n")
    result = notifier.send(
        title=test_data['title'],
        content=test_data['content'],
        hospital_name=test_data['hospital_name'],
        sentiment_info=test_data['sentiment_info']
    )
    
    if result:
        print("\n" + "=" * 60)
        print("✅ Telegram通知发送成功！")
        print("=" * 60)
        print(f"\n请检查您的Telegram群组（Chat ID: -5241269597）")
        print("应该已经收到测试通知消息")
    else:
        print("\n" + "=" * 60)
        print("❌ Telegram通知发送失败！")
        print("=" * 60)
        print("\n可能的原因：")
        print("1. Bot Token配置错误")
        print("2. Chat ID配置错误")
        print("3. 网络连接问题")
        print("4. Telegram API服务异常")
        print("\n请查看上方日志中的详细错误信息")
    
    return result

if __name__ == "__main__":
    try:
        success = test_telegram_notification()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
