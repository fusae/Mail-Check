#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用示例数据测试增强版报告生成器
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# 添加src目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from report_generator_enhanced import EnhancedReportGenerator

def create_sample_data():
    """创建示例数据（参考你之前生成的报告）"""
    data = []

    # 心脏手术死亡事件（14条，抖音平台）
    base_time = datetime(2026, 1, 29, 22, 1)
    times = [
        (2026, 1, 29, 22, 1),   # 首发视频
        (2026, 1, 29, 22, 32),
        (2026, 1, 30, 2, 33),
        (2026, 1, 30, 6, 1),
        (2026, 1, 30, 8, 2),
        (2026, 1, 30, 9, 33),
        (2026, 1, 30, 10, 3),
        (2026, 1, 30, 16, 2),
        (2026, 1, 30, 19, 4),
        (2026, 1, 30, 22, 5),
        (2026, 1, 31, 8, 3),
        (2026, 1, 31, 22, 0),
        (2026, 1, 30, 3, 30),
        (2026, 1, 30, 11, 15),
    ]

    for i, (year, month, day, hour, minute) in enumerate(times):
        data.append({
            'ID': f"243{i}181457" if i == 0 else f"243{9+i:02d}{hash(str(i)) % 1000000:06d}",
            '医院': '东莞市人民医院',
            '标题': f'脚肿后做心脏手术{"~" if i == 0 else ""}  治死了{"一点责任都没有" if i > 0 else ""}',
            '来源': '抖音',
            '严重程度': 'high',
            '创建时间': datetime(year, month, day, hour, minute).strftime('%Y-%m-%d %H:%M:%S'),
            '警示理由': '患者死亡事件，手术风险极高',
            '内容': '好好的一个人，治死了。心脏射频消融微创手术，术后7天去世。嘴角流血，未及时发现。一点责任都没有。微创手术说很成功，实际患者死亡。',
            '原文链接': f'https://www.douyin.com/video/760114515454030252{i}',
            '状态': 'active',
            '科室': '心内科',
            '类型': '医疗质量-死亡事件'
        })

    # 耳鼻喉科投诉（1条，微博平台）
    data.append({
        'ID': '2437701577',
        '医院': '东莞市大朗医院',
        '标题': '耳鼻喉科刘军医生凭肉眼判定肉芽肿，导致耳膜出血',
        '来源': '新浪微博',
        '严重程度': 'high',
        '创建时间': datetime(2026, 1, 29, 12, 31).strftime('%Y-%m-%d %H:%M:%S'),
        '警示理由': '医疗质量问题，诊断流程不规范',
        '内容': '凭肉眼判定肉芽肿，未做详细检查。电子耳内镜未做就冲洗耳朵，导致出血。报告写真菌却开治疗细菌的药。说不消炎就要手术，过度医疗。要求全额退治疗费。',
        '原文链接': 'https://weibo.com/1234567890/abcdef',
        '状态': 'active',
        '科室': '耳鼻喉科',
        '类型': '医疗服务质量投诉'
    })

    df = pd.DataFrame(data)

    # 添加风险分
    df['风险分'] = df['严重程度'].apply(
        lambda x: 100 if x == 'high' else 60 if x == 'medium' else 30
    )

    return df

def test_with_sample_data():
    """使用示例数据测试报告生成"""
    print("="*60)
    print("  增强版舆情报告生成器 - 示例数据测试")
    print("="*60)
    print()

    # 创建示例数据
    print("正在创建示例数据...")
    df = create_sample_data()
    print(f"[OK] 创建了 {len(df)} 条舆情数据")
    print()

    # 创建报告生成器
    gen = EnhancedReportGenerator()

    # 生成报告数据
    print("正在分析数据...")
    report_data = gen.generate_report_data(
        df=df,
        hospital_name='东莞市人民医院',
        report_type='special',
        report_period='2026年1月29日-31日'
    )
    print("[OK] 数据分析完成")
    print()

    # 生成Markdown报告
    print("正在生成Markdown报告...")
    md_content = gen.generate_markdown_report(report_data)

    # 保存报告
    output_dir = os.path.join(current_dir, 'data', 'reports')
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    md_path = os.path.join(output_dir, f'东莞市人民医院_舆情报告_{timestamp}.md')

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"[OK] 报告已保存: {md_path}")
    print(f"[OK] 文件大小: {len(md_content)} 字符")
    print()

    # 显示摘要
    print("="*60)
    print("  报告摘要")
    print("="*60)
    summary = report_data['summary']
    print(f"医院: {report_data['hospital_name']}")
    print(f"周期: {report_data['report_date_range']}")
    print(f"事件总数: {summary['total_events']}")
    print(f"高危事件: {summary['high_risk_events']}")
    print(f"危险级别: {summary['danger_level']}")
    print(f"平均风险分: {summary['average_risk_score']}")
    print()

    # 显示关键事件数量
    key_events = report_data.get('key_events', [])
    print(f"重点事件: {len(key_events)} 个")
    for i, event in enumerate(key_events, 1):
        print(f"  {i}. {event['overview']['title'][:50]}...")

    print()
    print("="*60)
    print("测试完成！")
    print(f"请查看报告文件: {md_path}")
    print("="*60)

if __name__ == "__main__":
    test_with_sample_data()
