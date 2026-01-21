#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化Telegram通知模板
"""

# 新的简洁模板
NEW_TEMPLATE = '''
⚠️ {title}

🏥 医院: {hospital_name}
📱 来源: {sentiment_info.get('source', '未知')}
📝 标题: {sentiment_info.get('title', '无标题')}
🤖 AI判断: {sentiment_info.get('reason', '未判断')}
⚡ 严重程度: {sentiment_info.get('severity', 'medium').upper()}

📄 内容摘要:
{content[:200]}{'...' if len(content) > 200 else ''}

━━━━━━━━━━━━━━━━━━━━━
请及时查看详情并处理。
'''

print("新的Telegram消息模板:")
print("=" * 60)
print(NEW_TEMPLATE)
print("=" * 60)

# 测试数据
test_data = {
    'title': '【舆情监控】发现负面舆情',
    'hospital_name': '测试医院',
    'sentiment_info': {
        'source': '微博',
        'title': '某医院发生医疗纠纷事件',
        'reason': '医疗纠纷负面舆情，影响医院声誉',
        'severity': 'high'
    },
    'content': '某医院发生医疗纠纷事件，患者家属在医院大厅聚集抗议，质疑医院的治疗方案和医疗费用。该事件已在社交媒体上广泛传播，引发公众关注和讨论。医院方面表示正在积极处理此事，但舆情影响仍在扩大。这起事件可能对医院声誉造成负面影响，建议及时回应和处理。'
}

# 生成示例消息
test_message = NEW_TEMPLATE.format(**test_data)
print("\n示例消息效果:")
print("=" * 60)
print(test_message)
