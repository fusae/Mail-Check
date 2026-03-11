#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试图表生成功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
from report_generator_enhanced import EnhancedReportGenerator

# 创建测试数据
test_data = {
    '标题': [
        '这个东莞的医院居然说医生不会看病，拒绝接诊的。',
        '万般皆是命。排名全国前5%的东莞市中医院',
        '广州中医药大学东莞医院 视障者就医全流程无支持',
        '广州中医药大学东莞医院 视障者就医全流程无支持',
        '这个东莞市中医院，厕所里面都是垃圾',
        '今天出院了，住个院比住高级宾馆价格高'
    ],
    '内容': [
        '医生态度很差，说不会看病就拒绝接诊',
        '收费有问题，重复扣费',
        '视障者就医没有无障碍设施',
        '视障者就医没有无障碍设施，拒不整改',
        '厕所卫生很差，垃圾很多',
        '住院费用太高了，住不起'
    ],
    '来源': ['抖音', '抖音', '今日头条', '抖音', '抖音', '抖音'],
    '创建时间': [
        '2026-02-03 21:01:00',
        '2026-02-20 18:35:00',
        '2026-02-05 04:01:00',
        '2026-02-04 21:33:00',
        '2026-02-02 06:03:00',
        '2026-02-27 16:33:00'
    ],
    '风险分': [100, 60, 60, 60, 60, 30],
    '严重程度': ['high', 'medium', 'medium', 'medium', 'medium', 'low'],
    '状态': ['active', 'active', 'active', 'active', 'active', 'active'],
    '警示理由': [
        '标题直接指控医院医生不会看病并拒绝接诊',
        '内容明确指控医院存在收费错误、重复扣费问题',
        '指控医院对视障者就医全流程无支持且拒不整改',
        '指控医院未履行无障碍服务法定义务',
        '内容直接指控本院厕所卫生差、管理混乱',
        '患者抱怨住院费用过高'
    ]
}

df = pd.DataFrame(test_data)

print("=" * 60)
print("测试图表生成功能")
print("=" * 60)

# 创建报告生成器
generator = EnhancedReportGenerator()

# 生成报告数据
print("\n1. 生成报告数据...")
report_data = generator.generate_report_data(
    df=df,
    hospital_name='东莞市中医院',
    report_type='special'
)

# 检查图表路径
chart_paths = report_data.get('chart_paths', {})
print(f"\n2. 生成的图表:")
for chart_name, chart_path in chart_paths.items():
    if chart_path and os.path.exists(chart_path):
        print(f"   ✓ {chart_name}: {chart_path}")
    else:
        print(f"   ✗ {chart_name}: 生成失败")

# 生成Markdown报告
print("\n3. 生成Markdown报告...")
markdown_report = generator.generate_markdown_report(report_data)

# 保存报告
output_path = os.path.join(generator.project_root, 'data', 'test_report_with_charts.md')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(markdown_report)

print(f"   ✓ 报告已保存: {output_path}")

# 生成Word报告
print("\n4. 生成Word报告...")
word_output_path = os.path.join(generator.project_root, 'data', 'test_report_with_charts.docx')
try:
    generator.generate_word_report(report_data, word_output_path)
    print(f"   ✓ Word报告已保存: {word_output_path}")
except Exception as e:
    print(f"   ✗ Word报告生成失败: {e}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
