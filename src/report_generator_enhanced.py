#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情报告生成器 - 增强版
参考示例报告风格，生成更加详细和专业的舆情分析报告
Enhanced Sentiment Report Generator
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import Counter
import re
import json

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class EnhancedReportGenerator:
    """增强版舆情报告生成器"""

    def __init__(self):
        self.platform_names = {
            '抖音': '抖音',
            'douyin': '抖音',
            '新浪微博': '微博',
            '微博': '微博',
            'weibo': '微博',
            '微信': '微信',
            'wechat': '微信',
            '新闻网站': '新闻网站',
            'news': '新闻网站',
            '黑猫投诉': '黑猫投诉',
            '今日头条': '今日头条',
            '百度贴吧': '百度贴吧',
        }

        # 情感关键词库
        self.emotion_keywords = {
            '愤怒': ['愤怒', '生气', '火大', '无语', '凭什么', '凭什么', '忍无可忍',
                    '太差了', '垃圾', '无良', '黑心', '骗子', '不负责任'],
            '悲伤': ['难过', '心痛', '悲伤', '痛苦', '不幸', '去世', '死亡', '离开',
                    '好好的一个人', '再也见不到', '遗憾', '惋惜'],
            '失望': ['失望', '失望透顶', '太失望了', '不值', '不值得', '白跑一趟',
                    '浪费时间', '不推荐', '再也不来了'],
            '质疑': ['质疑', '怀疑', '真的吗', '可信吗', '靠谱吗', '是不是',
                    '凭什么说', '证据呢', '有证据吗', '真假'],
            '担忧': ['担心', '担忧', '害怕', '恐惧', '不敢', '害怕去',
                    '有风险', '不安全', '可怕'],
        }

        # 风险等级映射
        self.risk_level_map = {
            'high': '🔴 极高',
            'medium': '🟠 高',
            'low': '🟡 中'
        }

    def normalize_platform(self, platform: str) -> str:
        """标准化平台名称"""
        platform = platform.lower().strip()
        for key, value in self.platform_names.items():
            if key in platform:
                return value
        return platform

    def generate_report_data(
        self,
        df: pd.DataFrame,
        hospital_name: str,
        report_type: str = "special",
        report_period: str = None
    ) -> Dict[str, Any]:
        """
        生成增强版报告数据

        参数：
        - df: 舆情数据DataFrame
        - hospital_name: 医院名称
        - report_type: 报告类型（special/quarterly/monthly）
        - report_period: 报告周期（如"2026Q1"）
        """
        # 数据预处理
        df = self._preprocess_data(df)

        # 生成各个部分的数据
        report_data = {
            'hospital_name': hospital_name,
            'report_type': report_type,
            'report_period': report_period or self._auto_detect_period(df),
            'generated_time': datetime.now().strftime('%Y年%m月%d日 %H:%M'),
            'report_date': datetime.now().strftime('%Y年%m月%d日'),
            'report_date_range': self._get_report_date_range(df),
            'summary': self._generate_summary(df),
            'overview': self._generate_overview(df),
            'distribution': self._generate_distribution(df),
            'key_events': self._generate_key_events_enhanced(df),  # 增强版关键事件
            'sentiment': self._generate_sentiment_enhanced(df),  # 增强版情感分析
            'risk_assessment': self._generate_risk_assessment_enhanced(df),  # 增强版风险评估
            'recommendations': self._generate_recommendations_enhanced(df),  # 增强版建议
            'impact_forecast': self._generate_impact_forecast(df),  # 新增：影响预测
            'response_templates': self._generate_response_templates(df),  # 新增：应对模板
            'appendix': self._generate_appendix_enhanced(df),  # 增强版附录
            'raw_dataframe': df
        }

        return report_data

    def _preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据预处理"""
        df = df.copy()

        # 标准化平台名称
        df['来源_标准'] = df['来源'].apply(self.normalize_platform)

        # 解析时间
        df['创建时间_解析'] = pd.to_datetime(df['创建时间'], errors='coerce')

        # 提取日期和小时
        df['日期'] = df['创建时间_解析'].dt.date
        df['小时'] = df['创建时间_解析'].dt.hour
        df['日期_字符串'] = df['创建时间_解析'].dt.strftime('%Y-%m-%d')
        df['时间_字符串'] = df['创建时间_解析'].dt.strftime('%Y-%m-%d %H:%M')

        # 计算风险分
        df['风险分_数值'] = pd.to_numeric(df['风险分'], errors='coerce').fillna(0)

        return df

    def _auto_detect_period(self, df: pd.DataFrame) -> str:
        """自动检测报告周期"""
        if len(df) == 0:
            return datetime.now().strftime('%Y年%m月')

        dates = pd.to_datetime(df['创建时间'], errors='coerce').dropna()
        if len(dates) == 0:
            return datetime.now().strftime('%Y年%m月')

        min_date = dates.min()
        max_date = dates.max()

        if min_date.month == max_date.month:
            return min_date.strftime('%Y年%m月')
        elif min_date.year == max_date.year:
            quarter = (max_date.month - 1) // 3 + 1
            return f"{max_date.year}Q{quarter}"
        else:
            return f"{min_date.strftime('%Y年%m月')}-{max_date.strftime('%Y年%m月')}"

    def _get_report_date_range(self, df: pd.DataFrame) -> str:
        """获取报告日期范围"""
        if len(df) == 0:
            return "无数据"

        dates = pd.to_datetime(df['创建时间'], errors='coerce').dropna()
        if len(dates) == 0:
            return "无数据"

        min_date = dates.min()
        max_date = dates.max()

        return f"{min_date.strftime('%Y年%m月%d日')}-{max_date.strftime('%Y年%m月%d日')}"

    def _generate_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """生成报告摘要（增强版）"""
        total = len(df)
        high_risk = len(df[df['严重程度'] == 'high'])
        medium_risk = len(df[df['严重程度'] == 'medium'])
        active = len(df[df['状态'] == 'active'])
        avg_risk = df['风险分_数值'].mean()

        # 估算影响人数
        estimated_reach = self._estimate_reach(df)

        # 传播峰值时间
        peak_time = self._find_peak_time(df)

        # 趋势分析
        trend = self._analyze_trend(df)

        # 危险级别判断
        danger_level = self._assess_danger_level(df)

        return {
            'total_events': total,
            'high_risk_events': high_risk,
            'medium_risk_events': medium_risk,
            'active_events': active,
            'inactive_events': total - active,
            'average_risk_score': round(avg_risk, 1),
            'estimated_reach': estimated_reach,
            'peak_time': peak_time,
            'trend': trend,
            'danger_level': danger_level,
            'platforms': df['来源_标准'].nunique(),
            'departments': df.get('科室', pd.Series()).nunique()
        }

    def _assess_danger_level(self, df: pd.DataFrame) -> str:
        """评估危险级别"""
        if len(df) == 0:
            return "🟢 无风险"

        high_risk = len(df[df['严重程度'] == 'high'])
        avg_risk = df['风险分_数值'].mean()

        if avg_risk >= 90 or high_risk >= 5:
            return "🔴 极高危险级别！"
        elif avg_risk >= 70 or high_risk >= 3:
            return "🟠 高危险级别"
        elif avg_risk >= 50 or high_risk >= 1:
            return "🟡 中危险级别"
        else:
            return "🟢 低危险级别"

    def _estimate_reach(self, df: pd.DataFrame) -> str:
        """估算影响人数（增强版）"""
        if len(df) == 0:
            return "0"

        total = 0
        for _, row in df.iterrows():
            platform = row.get('来源_标准', '')
            severity = row.get('严重程度', 'low')

            # 根据平台和严重程度估算
            base_reach = 1000  # 默认1000人

            if '抖音' in platform:
                base_reach = 100000  # 抖音10万
            elif '微博' in platform:
                base_reach = 50000  # 微博5万
            elif '微信' in platform:
                base_reach = 10000  # 微信1万

            if severity == 'high':
                base_reach *= 10
            elif severity == 'medium':
                base_reach *= 3

            total += base_reach

        if total >= 10000000:
            return f"{total // 10000000}千万+"
        elif total >= 10000:
            return f"{total // 10000}万+"
        elif total >= 1000:
            return f"{total // 1000}千+"
        else:
            return str(total)

    def _find_peak_time(self, df: pd.DataFrame) -> str:
        """找到传播峰值时间"""
        if len(df) == 0:
            return "未知"

        daily_counts = df.groupby('日期').size()
        if len(daily_counts) == 0:
            return "未知"

        peak_date = daily_counts.idxmax()
        return peak_date.strftime('%Y年%m月%d日')

    def _analyze_trend(self, df: pd.DataFrame) -> str:
        """分析趋势（增强版）"""
        if len(df) < 2:
            return "数据不足"

        df_sorted = df.sort_values('创建时间_解析')

        first_half = df_sorted[:len(df_sorted)//2]
        second_half = df_sorted[len(df_sorted)//2:]

        first_count = len(first_half)
        second_count = len(second_half)

        if second_count > first_count * 1.5:
            return "📈 快速上升"
        elif second_count < first_count * 0.7:
            return "📉 下降"
        else:
            return "➡️ 平稳"

    def _generate_overview(self, df: pd.DataFrame) -> Dict[str, Any]:
        """生成概述数据"""
        total = len(df)

        # 按严重程度统计
        severity_counts = df['严重程度'].value_counts()

        # 按状态统计
        status_counts = df['状态'].value_counts()

        # 按平台统计
        platform_counts = df['来源_标准'].value_counts()

        return {
            'total': total,
            'severity_distribution': {
                'high': int(severity_counts.get('high', 0)),
                'medium': int(severity_counts.get('medium', 0)),
                'low': int(severity_counts.get('low', 0))
            },
            'status_distribution': status_counts.to_dict(),
            'platform_distribution': platform_counts.to_dict(),
            'average_risk_score': round(df['风险分_数值'].mean(), 1),
            'max_risk_score': int(df['风险分_数值'].max()),
            'min_risk_score': int(df['风险分_数值'].min())
        }

    def _generate_distribution(self, df: pd.DataFrame) -> Dict[str, Any]:
        """生成分布分析"""
        return {
            'time_distribution': self._analyze_time_distribution_enhanced(df),
            'platform_distribution': self._analyze_platform_distribution_enhanced(df),
            'type_distribution': self._analyze_type_distribution_enhanced(df),
            'department_distribution': self._analyze_department_distribution_enhanced(df)
        }

    def _analyze_time_distribution_enhanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """时间分布分析（增强版）"""
        if len(df) == 0:
            return {'timeline': [], 'pattern': '无数据', 'peak_hours': []}

        # 按日期统计
        daily_counts = df.groupby('日期').size().sort_index()

        # 构建时间轴
        timeline = []
        for date, count in daily_counts.items():
            date_str = date.strftime('%m月%d日')
            events = df[df['日期'] == date].sort_values('创建时间_解析')

            # 获取该日的时间段
            time_slots = []
            for _, event in events.iterrows():
                hour = event.get('小时', 0)
                time_slots.append(f"{hour:02d}:00")

            timeline.append({
                'date': date_str,
                'count': int(count),
                'time_slots': time_slots,
                'platforms': events['来源_标准'].unique().tolist()
            })

        # 按小时统计
        hourly_counts = df.groupby('小时').size()

        # 找出峰值时段
        peak_hours = sorted(hourly_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # 检测时间模式
        time_pattern = self._detect_time_pattern(df)

        return {
            'timeline': timeline,
            'daily_counts': {str(k): int(v) for k, v in daily_counts.items()},
            'hourly_counts': {int(k): int(v) for k, v in hourly_counts.items()},
            'peak_hours': [{'hour': int(h), 'count': int(c)} for h, c in peak_hours],
            'time_pattern': time_pattern
        }

    def _detect_time_pattern(self, df: pd.DataFrame) -> str:
        """检测时间模式"""
        if len(df) == 0:
            return "无数据"

        hour_counts = df.groupby('小时').size()

        # 判断是否夜间集中（22:00-02:00）
        night_hours = [22, 23, 0, 1, 2]
        night_count = sum(hour_counts.get(h, 0) for h in night_hours)

        # 判断是否工作日集中（周一至周五）
        weekday_count = len(df[df['创建时间_解析'].dt.dayofweek < 5])
        weekend_count = len(df) - weekday_count

        patterns = []
        if night_count > len(df) * 0.3:
            patterns.append("夜间集中（22:00-02:00）")
        if weekday_count > weekend_count * 2:
            patterns.append("工作日集中")
        elif weekend_count > weekday_count * 2:
            patterns.append("周末集中")

        return "、".join(patterns) if patterns else "无明显规律"

    def _analyze_platform_distribution_enhanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """平台分布分析（增强版）"""
        if len(df) == 0:
            return {'distribution': {}, 'analysis': '无数据'}

        platform_counts = df['来源_标准'].value_counts()

        distribution = {}
        for platform, count in platform_counts.items():
            percentage = (count / len(df)) * 100
            risk_level = '极高' if percentage > 70 else '高' if percentage > 30 else '中'

            # 获取该平台的风险分
            platform_df = df[df['来源_标准'] == platform]
            avg_risk = platform_df['风险分_数值'].mean()

            distribution[platform] = {
                'count': int(count),
                'percentage': round(percentage, 1),
                'risk_level': risk_level,
                'avg_risk_score': round(avg_risk, 1),
                'characteristics': self._get_platform_characteristics(platform)
            }

        # 主导平台
        dominant = platform_counts.index[0] if len(platform_counts) > 0 else "无"
        dominant_ratio = (platform_counts.iloc[0] / len(df)) * 100 if len(platform_counts) > 0 else 0

        analysis = f"主导平台：{dominant}（占{dominant_ratio:.1f}%）"

        return {
            'distribution': distribution,
            'analysis': analysis,
            'dominant_platform': dominant
        }

    def _get_platform_characteristics(self, platform: str) -> List[str]:
        """获取平台特征"""
        characteristics = {
            '抖音': ['传播速度快', '触达人群广', '情感传播强', '监管力度较弱'],
            '微博': ['话题性强', '转发传播快', '舆论发酵迅速', '媒体关注度高'],
            '微信': ['封闭传播', '圈层化明显', '长尾效应强', '难以监测'],
            '新闻网站': ['权威性高', '影响持久', '搜索引擎收录', '公信力强'],
            '黑猫投诉': ['投诉聚集地', '消费者维权', '媒体关注', '官方回复'],
            '百度贴吧': ['社群传播', '用户讨论', '长尾效应', '搜索可见']
        }
        return characteristics.get(platform, ['一般传播'])

    def _analyze_type_distribution_enhanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """类型分布分析（增强版）"""
        if len(df) == 0:
            return {'distribution': {}, 'analysis': '无数据'}

        # 假设有一个"类型"字段，如果没有则从内容推断
        if '类型' in df.columns:
            type_counts = df['类型'].value_counts()
        else:
            # 从内容推断类型
            type_counts = self._infer_event_types(df)

        distribution = {}
        for event_type, count in type_counts.items():
            percentage = (count / len(df)) * 100
            severity = self._get_type_severity(event_type)

            distribution[event_type] = {
                'count': int(count),
                'percentage': round(percentage, 1),
                'severity': severity
            }

        return {
            'distribution': distribution,
            'total_types': len(type_counts)
        }

    def _infer_event_types(self, df: pd.DataFrame) -> pd.Series:
        """从内容推断事件类型"""
        types = []

        for _, row in df.iterrows():
            content = str(row.get('内容', '')) + str(row.get('标题', ''))

            if any(keyword in content for keyword in ['死亡', '去世', '抢救无效', '手术死亡']):
                types.append('医疗质量-死亡事件')
            elif any(keyword in content for keyword in ['投诉', '态度差', '服务差']):
                types.append('服务质量投诉')
            elif any(keyword in content for keyword in ['费用', '收费', '贵']):
                types.append('收费问题')
            elif any(keyword in content for keyword in ['等待', '排队', '时间长']):
                types.append('流程问题')
            else:
                types.append('其他')

        return pd.Series(types)

    def _get_type_severity(self, event_type: str) -> str:
        """获取类型的严重程度"""
        if '死亡' in event_type:
            return '极高'
        elif '投诉' in event_type or '费用' in event_type:
            return '高'
        else:
            return '中'

    def _analyze_department_distribution_enhanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """科室分布分析（增强版）"""
        if len(df) == 0 or '科室' not in df.columns:
            return {'distribution': {}, 'high_risk_departments': []}

        department_counts = df['科室'].value_counts()

        distribution = {}
        high_risk_departments = []

        for dept, count in department_counts.items():
            # 获取该科室的平均风险分
            dept_df = df[df['科室'] == dept]
            avg_risk = dept_df['风险分_数值'].mean()
            max_risk = dept_df['风险分_数值'].max()

            risk_level = '🔴 极高' if avg_risk >= 80 else '🟠 高' if avg_risk >= 60 else '🟡 中'

            distribution[dept] = {
                'count': int(count),
                'avg_risk_score': round(avg_risk, 1),
                'max_risk_score': int(max_risk),
                'risk_level': risk_level
            }

            if avg_risk >= 80:
                high_risk_departments.append(dept)

        return {
            'distribution': distribution,
            'high_risk_departments': high_risk_departments,
            'total_departments': len(department_counts)
        }

    def _generate_key_events_enhanced(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """生成关键事件（增强版）"""
        if len(df) == 0:
            return []

        # 按风险分排序，取前5个高风险事件
        high_risk_df = df[df['严重程度'].isin(['high', 'medium'])].sort_values('风险分_数值', ascending=False)

        # 按相似度分组（简单的标题相似度）
        event_groups = self._group_similar_events(high_risk_df)

        key_events = []
        for group_id, group_df in event_groups.items():
            if len(group_df) == 0:
                continue

            # 获取该组的代表性事件
            representative = group_df.iloc[0]

            # 构建事件脉络
            timeline = self._build_event_timeline(group_df)

            # 传播分析
            spread_analysis = self._analyze_event_spread(group_df)

            # 情感分析
            sentiment_analysis = self._analyze_event_sentiment(group_df)

            # 影响评估
            impact_assessment = self._assess_event_impact(group_df)

            # 处置建议
            recommendations = self._generate_event_recommendations(group_df)

            event = {
                'id': group_id,
                'title': representative.get('标题', '未知事件'),
                'overview': {
                    'event_time': self._extract_event_time(group_df),
                    'department': representative.get('科室', '未知'),
                    'platform': representative.get('来源_标准', '未知'),
                    'severity': representative.get('严重程度', 'unknown'),
                    'risk_score': int(representative.get('风险分_数值', 0)),
                    'total_mentions': len(group_df)
                },
                'timeline': timeline,
                'spread_analysis': spread_analysis,
                'sentiment_analysis': sentiment_analysis,
                'impact_assessment': impact_assessment,
                'recommendations': recommendations
            }

            key_events.append(event)

            if len(key_events) >= 5:
                break

        return key_events

    def _group_similar_events(self, df: pd.DataFrame) -> Dict[int, pd.DataFrame]:
        """按相似度分组事件"""
        groups = {}
        group_id = 0

        for idx, row in df.iterrows():
            title = str(row.get('标题', ''))

            # 检查是否与已有组相似
            matched = False
            for existing_id, existing_df in groups.items():
                existing_title = str(existing_df.iloc[0].get('标题', ''))
                if self._are_titles_similar(title, existing_title):
                    groups[existing_id] = pd.concat([existing_df, pd.DataFrame([row])], ignore_index=True)
                    matched = True
                    break

            if not matched:
                groups[group_id] = pd.DataFrame([row])
                group_id += 1

        return groups

    def _are_titles_similar(self, title1: str, title2: str) -> bool:
        """判断标题是否相似"""
        # 简单的相似度判断：有3个以上相同的词
        words1 = set(title1.split())
        words2 = set(title2.split())

        intersection = words1.intersection(words2)
        return len(intersection) >= 3

    def _build_event_timeline(self, df: pd.DataFrame) -> Dict[str, Any]:
        """构建事件时间轴"""
        df_sorted = df.sort_values('创建时间_解析')

        stages = {
            'occurrence': [],
            'fermentation': [],
            'outbreak': [],
            'continuation': []
        }

        for _, row in df_sorted.iterrows():
            stage_info = {
                'time': row.get('时间_字符串', ''),
                'platform': row.get('来源_标准', ''),
                'description': row.get('标题', '')[:50]
            }

            # 根据时间判断阶段（简化版）
            hour = row.get('小时', 0)
            if hour < 6:
                stages['occurrence'].append(stage_info)
            elif hour < 12:
                stages['fermentation'].append(stage_info)
            elif hour < 18:
                stages['outbreak'].append(stage_info)
            else:
                stages['continuation'].append(stage_info)

        return stages

    def _analyze_event_spread(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析事件传播"""
        platforms = df['来源_标准'].value_counts().to_dict()

        # 估算传播路径
        spread_path = []
        for _, row in df.sort_values('创建时间_解析').iterrows():
            spread_path.append({
                'time': row.get('时间_字符串', ''),
                'platform': row.get('来源_标准', ''),
                'description': row.get('标题', '')[:30]
            })

        # 计算影响估算
        estimated_reach = self._estimate_reach(df)

        return {
            'platforms': platforms,
            'spread_path': spread_path,
            'estimated_reach': estimated_reach,
            'total_mentions': len(df),
            'spread_speed': self._calculate_spread_speed(df)
        }

    def _calculate_spread_speed(self, df: pd.DataFrame) -> str:
        """计算传播速度"""
        if len(df) < 2:
            return "无法计算"

        df_sorted = df.sort_values('创建时间_解析')
        time_diff = (df_sorted.iloc[-1]['创建时间_解析'] - df_sorted.iloc[0]['创建时间_解析']).total_seconds() / 3600

        if time_diff <= 0:
            return "瞬间"

        mentions_per_hour = len(df) / time_diff

        if mentions_per_hour > 10:
            return "极快（病毒式）"
        elif mentions_per_hour > 5:
            return "很快"
        elif mentions_per_hour > 1:
            return "较快"
        else:
            return "一般"

    def _analyze_event_sentiment(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析事件情感"""
        # 合并所有内容
        all_content = ' '.join(df['内容'].fillna('') + ' ' + df['标题'].fillna(''))

        # 情感统计
        emotion_counts = Counter()

        if JIEBA_AVAILABLE:
            words = jieba.cut(all_content)
            word_list = list(words)

            # 统计情感词
            for emotion, keywords in self.emotion_keywords.items():
                count = sum(1 for word in word_list if word in keywords)
                if count > 0:
                    emotion_counts[emotion] += count

        # 提取高频关键词
        keywords = self._extract_keywords(all_content, top_n=20)

        # 提取公众诉求
        demands = self._extract_demands(all_content)

        return {
            'emotion_distribution': dict(emotion_counts),
            'top_keywords': keywords,
            'public_demands': demands
        }

    def _extract_keywords(self, text: str, top_n: int = 20) -> List[Dict[str, Any]]:
        """提取关键词"""
        if JIEBA_AVAILABLE:
            words = jieba.cut(text)
            word_freq = Counter(words)

            # 过滤停用词
            stop_words = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人',
                         '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
                         '你', '会', '着', '没有', '看', '好', '自己', '这', '但'}

            filtered = {k: v for k, v in word_freq.items()
                       if len(k) > 1 and k not in stop_words and v > 1}

            top_keywords = sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:top_n]

            return [{'keyword': k, 'count': v} for k, v in top_keywords]
        else:
            return []

    def _extract_demands(self, text: str) -> List[str]:
        """提取公众诉求"""
        demand_patterns = [
            (r'要求.*?责任', '要求医院承担责任'),
            (r'(要求|请求).*?调查', '要求调查事件真相'),
            (r'(要求|请求).*?道歉', '要求道歉'),
            (r'(要求|请求).*?赔偿', '要求赔偿'),
            (r'(要求|请求).*?退款', '要求退款'),
            (r'(要求|请求).*?公开', '要求公开信息'),
            (r'(要求|请求).*?处理', '要求处理相关人员'),
        ]

        demands = []
        for pattern, demand in demand_patterns:
            if re.search(pattern, text):
                demands.append(demand)

        return demands

    def _assess_event_impact(self, df: pd.DataFrame) -> Dict[str, Any]:
        """评估事件影响"""
        avg_risk = df['风险分_数值'].mean()
        max_risk = df['风险分_数值'].max()
        total_mentions = len(df)

        # 社会影响
        social_impact = []
        if avg_risk >= 80:
            social_impact.append("严重损害医院声誉")
        if avg_risk >= 70:
            social_impact.append("引发公众对医院水平的质疑")
        if total_mentions > 5:
            social_impact.append("可能引发媒体跟进报道")

        # 潜在风险
        potential_risks = []
        if '死亡' in ' '.join(df['内容'].fillna('')):
            potential_risks.append("可能引发法律诉讼")
            potential_risks.append("可能影响医院评级")
        if avg_risk >= 70:
            potential_risks.append("可能导致其他患者流失")

        return {
            'social_impact': social_impact,
            'potential_risks': potential_risks,
            'legal_risk': '高' if '死亡' in ' '.join(df['内容'].fillna('')) else '中',
            'media_risk': '高' if total_mentions > 5 else '中'
        }

    def _generate_event_recommendations(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        """生成事件处置建议"""
        avg_risk = df['风险分_数值'].mean()

        immediate = []
        short_term = []
        long_term = []

        if avg_risk >= 80:
            immediate.extend([
                "立即启动危机公关响应",
                "发布官方声明",
                "启动内部调查",
                "主动与相关方沟通"
            ])

        if avg_risk >= 60:
            immediate.append("密切监控舆情发展")
            short_term.extend([
                "准备媒体应对材料",
                "评估法律风险"
            ])

        long_term.extend([
            "改进相关医疗流程",
            "加强医患沟通培训",
            "建立危机预警机制"
        ])

        return {
            'immediate': immediate,
            'short_term': short_term,
            'long_term': long_term
        }

    def _extract_event_time(self, df: pd.DataFrame) -> str:
        """提取事件时间"""
        if len(df) == 0:
            return "未知"

        min_time = df['创建时间_解析'].min()
        max_time = df['创建时间_解析'].max()

        if min_time == max_time:
            return min_time.strftime('%Y年%m月%d日')
        else:
            return f"{min_time.strftime('%m月%d日')}-{max_time.strftime('%m月%d日')}"

    def _generate_sentiment_enhanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """生成情感分析（增强版）"""
        if len(df) == 0:
            return {'emotion_distribution': {}, 'top_keywords': [], 'public_demands': []}

        # 合并所有内容
        all_content = ' '.join(df['内容'].fillna('') + ' ' + df['标题'].fillna(''))

        # 情感统计
        emotion_counts = Counter()

        if JIEBA_AVAILABLE:
            words = jieba.cut(all_content)
            word_list = list(words)

            for emotion, keywords in self.emotion_keywords.items():
                count = sum(1 for word in word_list if word in keywords)
                if count > 0:
                    emotion_counts[emotion] = count

        # 提取关键词
        keywords = self._extract_keywords(all_content, top_n=30)

        # 提取诉求
        demands = self._extract_demands(all_content)

        return {
            'emotion_distribution': dict(emotion_counts),
            'top_keywords': keywords,
            'public_demands': demands
        }

    def _generate_risk_assessment_enhanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """生成风险评估（增强版）"""
        if len(df) == 0:
            return {'current_risks': [], 'risk_levels': {}}

        current_risks = []
        risk_levels = {
            'red': [],
            'orange': [],
            'yellow': []
        }

        # 按科室分析风险
        if '科室' in df.columns:
            for dept in df['科室'].unique():
                dept_df = df[df['科室'] == dept]
                avg_risk = dept_df['风险分_数值'].mean()
                max_risk = dept_df['风险分_数值'].max()
                count = len(dept_df)

                if avg_risk >= 80:
                    level = 'red'
                    level_text = '🔴 红色预警（极高风险）'
                elif avg_risk >= 60:
                    level = 'orange'
                    level_text = '🟠 橙色预警（高风险）'
                else:
                    level = 'yellow'
                    level_text = '🟡 黄色预警（中风险）'

                risk_info = {
                    'department': dept,
                    'avg_risk_score': round(avg_risk, 1),
                    'max_risk_score': int(max_risk),
                    'event_count': int(count),
                    'level_text': level_text
                }

                current_risks.append(risk_info)
                risk_levels[level].append(dept)

        # 按事件类型分析
        event_type_risks = []
        for event_type in df.get('类型', pd.Series()).unique():
            if pd.isna(event_type):
                continue
            type_df = df[df['类型'] == event_type]
            avg_risk = type_df['风险分_数值'].mean()

            event_type_risks.append({
                'type': event_type,
                'avg_risk_score': round(avg_risk, 1),
                'event_count': len(type_df)
            })

        return {
            'current_risks': sorted(current_risks, key=lambda x: x['avg_risk_score'], reverse=True),
            'risk_levels': risk_levels,
            'event_type_risks': event_type_risks,
            'overall_risk_level': self._assess_danger_level(df)
        }

    def _generate_recommendations_enhanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """生成应对建议（增强版）"""
        avg_risk = df['风险分_数值'].mean() if len(df) > 0 else 0

        immediate = []
        short_term = []
        long_term = []

        # 立即措施（24小时内）
        if avg_risk >= 80:
            immediate.extend([
                "🚨 立即启动危机公关响应",
                "📢 发布官方声明",
                "🔍 启动内部调查",
                "⚖️ 准备法律应对",
                "🤝 主动与相关方沟通"
            ])

        # 短期措施（1周内）
        if avg_risk >= 60:
            short_term.extend([
                "📊 公布调查结果",
                "👥 处理相关责任人",
                "🔧 整改医疗流程",
                "📚 加强医患沟通培训",
                "⚠️ 建立危机预警机制"
            ])

        # 长期措施（1-3个月）
        long_term.extend([
            "🏥 提高医疗质量",
            "💬 改善服务态度",
            "⚡ 优化服务流程",
            "🔒 加强危机预防",
            "📖 建立投诉处理制度"
        ])

        # 重点防控方向
        prevention = {
            'short_term': [
                "高风险科室专项整治",
                "危机管理机制建设",
                "全院服务质量提升"
            ],
            'medium_term': [
                "医患沟通培训",
                "服务流程优化",
                "投诉处理机制"
            ]
        }

        # 舆情监测重点
        monitoring = {
            'keywords': self._generate_monitoring_keywords(df),
            'platforms': list(df['来源_标准'].unique()),
            'frequency': '实时监测（7x24小时）'
        }

        return {
            'immediate_actions': immediate,
            'short_term_actions': short_term,
            'long_term_actions': long_term,
            'prevention': prevention,
            'monitoring': monitoring
        }

    def _generate_monitoring_keywords(self, df: pd.DataFrame) -> List[str]:
        """生成监测关键词"""
        if '医院' in df.columns:
            hospital_names = df['医院'].unique().tolist()
        else:
            hospital_names = []

        keywords = []
        for name in hospital_names[:5]:
            keywords.extend([
                name,
                f"{name} 死亡",
                f"{name} 投诉",
                f"{name} 手术"
            ])

        return keywords[:20]

    def _generate_impact_forecast(self, df: pd.DataFrame) -> Dict[str, Any]:
        """生成影响预测"""
        avg_risk = df['风险分_数值'].mean() if len(df) > 0 else 0

        # 短期影响（1-7天）
        short_term = []
        if avg_risk >= 70:
            short_term.extend([
                "平台持续发酵",
                "可能出现更多相关内容",
                "医院网络评分下降"
            ])

        # 中期影响（1-4周）
        medium_term = []
        if avg_risk >= 60:
            medium_term.extend([
                "传统媒体可能报道",
                "监管部门可能关注",
                "可能引发法律诉讼"
            ])

        if avg_risk >= 70:
            medium_term.append("就诊量可能下降10-20%")

        # 长期影响（1-3个月）
        long_term = []
        if avg_risk >= 50:
            long_term.extend([
                "医院声誉受损",
                "品牌形象下降",
                "市场份额流失"
            ])

        # 法律风险评估
        legal_risk = {
            'probability': '80%' if '死亡' in ' '.join(df['内容'].fillna('')) else '30%',
            'estimated_amount': '50-200万' if avg_risk >= 70 else '10-50万',
            'description': '医疗损害赔偿诉讼风险较高' if avg_risk >= 70 else '存在诉讼风险'
        }

        return {
            'short_term': short_term,
            'medium_term': medium_term,
            'long_term': long_term,
            'legal_risk': legal_risk
        }

    def _generate_response_templates(self, df: pd.DataFrame) -> Dict[str, str]:
        """生成应对模板"""
        hospital_name = df.get('医院', pd.Series()).iloc[0] if len(df) > 0 and '医院' in df.columns else "我院"

        # 首次回应模板
        first_response = f"""关于网传{hospital_name}患者事件的首次回应

我院关注到网络平台出现关于我院的舆情，对此我们深表关切。
医院已第一时间成立专项调查组，对事件进行全面调查。

我们承诺：
1. 秉持客观、公正、透明的原则
2. 尽快查明事实真相
3. 依法依规处理
4. 及时向社会公布调查进展

感谢社会各界监督。

{hospital_name}
{datetime.now().strftime('%Y年%m月%d日')}
"""

        # 调查进展模板
        progress_update = f"""关于患者事件调查进展的通报

自启动调查以来，我院已完成以下工作：

一、已完成：
1. 封存全部病历资料
2. 调阅相关监控录像
3. 约谈相关医护人员
4. 与相关方取得联系

二、正在进行：
1. 医疗过程评估
2. 病历资料分析
3. 专家论证
4. 责任认定

三、后续安排：
1. 尽快公布调查结果
2. 依法依规处理
3. 改进医疗服务

感谢社会各界的关心和监督。

{hospital_name}
{datetime.now().strftime('%Y年%m月%d日')}
"""

        return {
            'first_response': first_response,
            'progress_update': progress_update
        }

    def _generate_appendix_enhanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """生成附录（增强版）"""
        if len(df) == 0:
            return {'event_list': [], 'contact_info': {}}

        # 完整事件清单
        event_list = []
        for _, row in df.sort_values('创建时间_解析', ascending=False).iterrows():
            event_list.append({
                'id': row.get('ID', ''),
                'time': row.get('时间_字符串', ''),
                'platform': row.get('来源_标准', ''),
                'type': row.get('类型', '未知'),
                'department': row.get('科室', ''),
                'risk_score': int(row.get('风险分_数值', 0)),
                'status': row.get('状态', 'unknown'),
                'title': row.get('标题', '')[:50]
            })

        # 传播路径（简化版）
        spread_path = self._build_spread_path(df)

        # 联系方式
        contact_info = {
            'monitoring_center': {
                '负责人': '[填写]',
                '电话': '[填写]',
                '邮箱': '[填写]'
            },
            'crisis_team': {
                '组长': '院长',
                '成员': ['医务科', '宣传科', '法务科']
            }
        }

        return {
            'event_list': event_list,
            'spread_path': spread_path,
            'contact_info': contact_info
        }

    def _build_spread_path(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """构建传播路径"""
        if len(df) == 0:
            return []

        df_sorted = df.sort_values('创建时间_解析')

        path = []
        for _, row in df_sorted.iterrows():
            path.append({
                'time': row.get('时间_字符串', ''),
                'platform': row.get('来源_标准', ''),
                'title': row.get('标题', '')[:30],
                'description': row.get('内容', '')[:50]
            })

        return path[:50]  # 最多显示50条

    def generate_markdown_report(self, report_data: Dict[str, Any]) -> str:
        """生成Markdown格式报告"""
        lines = []

        # 报告标题
        lines.append(f"# {report_data['hospital_name']}负面舆情专项分析报告\n")
        lines.append(f"**报告周期：** {report_data['report_date_range']}")
        lines.append(f"**报告时间：** {report_data['report_date']}")
        lines.append(f"**报告类型：** 舆情专项报告\n")
        lines.append("---\n")

        # 一、报告概述
        lines.extend(self._format_summary_section(report_data))

        # 二、舆情分布分析
        lines.extend(self._format_distribution_section(report_data))

        # 三、重点负面事件详析
        lines.extend(self._format_key_events_section(report_data))

        # 四、情感分析与公众关切
        lines.extend(self._format_sentiment_section(report_data))

        # 五、风险预警与评估
        lines.extend(self._format_risk_section(report_data))

        # 六、应对措施与处置情况
        lines.extend(self._format_recommendations_section(report_data))

        # 七、影响预测
        lines.extend(self._format_impact_section(report_data))

        # 八、官方声明模板
        lines.extend(self._format_templates_section(report_data))

        # 九、附录
        lines.extend(self._format_appendix_section(report_data))

        # 报告结束
        lines.append("\n## 报告结束\n")
        lines.append(f"**报告生成时间：** {report_data['generated_time']}")
        lines.append("**报告有效期：** 立即更新（建议每日更新）\n")

        return '\n'.join(lines)

    def _format_summary_section(self, data: Dict[str, Any]) -> List[str]:
        """格式化概述部分"""
        lines = []
        summary = data['summary']

        lines.append("## 一、报告概述\n")
        lines.append("### 1.1 舆情总体态势\n")
        lines.append(f"**{summary['danger_level']}**\n")

        lines.append("### 1.2 关键数据摘要\n")
        lines.append("| 指标 | 数值 | 说明 |")
        lines.append("|------|------|------|")
        lines.append(f"| **负面舆情总数** | {summary['total_events']}条 | 全部为{'高风险' if summary['high_risk_events'] > 0 else '中低风险'} |")
        lines.append(f"| **高危事件数量** | {summary['high_risk_events']}起 | 需重点关注 |")
        lines.append(f"| **影响人数估算** | {summary['estimated_reach']} | 仅估算 |")
        lines.append(f"| **传播峰值时间** | {summary['peak_time']} | 集中爆发期 |")
        lines.append(f"| **涉及平台** | {summary['platforms']}个 | {', '.join(list(data.get('overview', {}).get('platform_distribution', {}).keys())[:3])} |")
        lines.append(f"| **平均风险分** | {summary['average_risk_score']}分 | 满分100分 |\n")

        lines.append("### 1.3 环比变化\n")
        lines.append(f"- {summary['trend']}\n")
        lines.append("---\n")

        return lines

    def _format_distribution_section(self, data: Dict[str, Any]) -> List[str]:
        """格式化分布分析部分"""
        lines = []
        dist = data['distribution']

        lines.append("## 二、舆情分布分析\n")

        # 时间分布
        lines.append("### 2.1 时间分布\n")
        time_dist = dist.get('time_distribution', {})
        timeline = time_dist.get('timeline', [])

        if timeline:
            lines.append("**时间轴：**\n")
            lines.append("```")
            for item in timeline[:10]:
                lines.append(f"{item['date']}: {item['count']}条")
                if item.get('time_slots'):
                    lines.append(f"  时段: {', '.join(item['time_slots'][:3])}")
            lines.append("```")

        lines.append(f"\n**关键发现：**")
        lines.append(f"- {time_dist.get('time_pattern', '无明显规律')}")
        peak_hours_str = ', '.join([f"{h['hour']}:00" for h in time_dist.get('peak_hours', [])[:3]])
        lines.append(f"- 峰值时段: {peak_hours_str}\n")

        # 平台分布
        lines.append("### 2.2 平台分布\n")
        platform_dist = dist.get('platform_distribution', {})
        platforms = platform_dist.get('distribution', {})

        if platforms:
            lines.append("| 平台 | 数量 | 占比 | 风险等级 |")
            lines.append("|------|------|------|----------|")
            for platform, info in platforms.items():
                lines.append(f"| **{platform}** | {info['count']}条 | {info['percentage']}% | {info['risk_level']} |")

        lines.append(f"\n**{platform_dist.get('analysis', '')}**\n")

        # 类型分布
        lines.append("### 2.3 类型分布\n")
        type_dist = dist.get('type_distribution', {}).get('distribution', {})

        if type_dist:
            lines.append("| 类型 | 数量 | 占比 | 严重程度 |")
            lines.append("|------|------|------|----------|")
            for event_type, info in type_dist.items():
                lines.append(f"| **{event_type}** | {info['count']}条 | {info['percentage']}% | {info['severity']} |\n")

        # 科室分布
        if '科室' in data.get('raw_dataframe', pd.DataFrame()).columns:
            lines.append("### 2.4 科室分布\n")
            dept_dist = dist.get('department_distribution', {}).get('distribution', {})

            if dept_dist:
                lines.append("| 科室 | 事件数 | 风险等级 | 平均风险分 |")
                lines.append("|------|--------|----------|------------|")
                for dept, info in list(dept_dist.items())[:5]:
                    lines.append(f"| **{dept}** | {info['count']} | {info['risk_level']} | {info['avg_risk_score']} |")

                high_risk = dist.get('department_distribution', {}).get('high_risk_departments', [])
                if high_risk:
                    lines.append(f"\n**重点监控科室：** {', '.join([f'**{d}**' for d in high_risk])}\n")

        lines.append("---\n")

        return lines

    def _format_key_events_section(self, data: Dict[str, Any]) -> List[str]:
        """格式化关键事件部分"""
        lines = []
        events = data.get('key_events', [])

        if not events:
            return []

        lines.append("## 三、重点负面事件详析\n")

        for idx, event in enumerate(events[:3], 1):
            risk_level = '🔴' if event['overview']['severity'] == 'high' else '🟠'
            lines.append(f"### {risk_level} 事件{idx}：{event['title'][:50]}\n")

            # 概况
            lines.append("#### 3.{}.1 事件概况".format(idx))
            lines.append("| 项目 | 详情 |")
            lines.append("|------|------|")
            lines.append(f"| **事件时间** | {event['overview']['event_time']} |")
            lines.append(f"| **涉事科室** | {event['overview']['department']} |")
            lines.append(f"| **首发平台** | {event['overview']['platform']} |")
            lines.append(f"| **风险评分** | {event['overview']['risk_score']}/100 |")
            lines.append(f"| **传播次数** | {event['overview']['total_mentions']}次 |\n")

            # 传播分析
            if event.get('spread_analysis'):
                lines.append("#### 3.{}.2 传播分析".format(idx))
                spread = event['spread_analysis']
                lines.append(f"- **传播速度：** {spread.get('spread_speed', '未知')}")
                lines.append(f"- **影响估算：** {spread.get('estimated_reach', '未知')}")
                lines.append(f"- **涉及平台：** {', '.join(spread.get('platforms', {}).keys())}\n")

            # 情感分析
            if event.get('sentiment_analysis'):
                lines.append("#### 3.{}.3 情感倾向".format(idx))
                sentiment = event['sentiment_analysis']

                if sentiment.get('emotion_distribution'):
                    lines.append("**情感分布：**")
                    for emotion, count in sentiment['emotion_distribution'].items():
                        lines.append(f"- {emotion}: {count}次")

                if sentiment.get('top_keywords'):
                    lines.append("\n**高频关键词（TOP 10）：**")
                    for kw in sentiment['top_keywords'][:10]:
                        lines.append(f"- {kw['keyword']} ({kw['count']}次)")

                if sentiment.get('public_demands'):
                    lines.append("\n**公众诉求：**")
                    for demand in sentiment['public_demands']:
                        lines.append(f"- {demand}")
                lines.append("")

            # 处置建议
            if event.get('recommendations'):
                lines.append("#### 3.{}.4 处置建议".format(idx))
                recs = event['recommendations']

                if recs.get('immediate'):
                    lines.append("**立即措施：**")
                    for rec in recs['immediate']:
                        lines.append(f"- {rec}")

                if recs.get('short_term'):
                    lines.append("\n**短期措施：**")
                    for rec in recs['short_term']:
                        lines.append(f"- {rec}")
                lines.append("")

            lines.append("---\n")

        return lines

    def _format_sentiment_section(self, data: Dict[str, Any]) -> List[str]:
        """格式化情感分析部分"""
        lines = []
        sentiment = data.get('sentiment', {})

        lines.append("## 四、情感分析与公众关切\n")

        # 情感分布
        lines.append("### 4.1 情感倾向分析\n")
        emotion_dist = sentiment.get('emotion_distribution', {})

        if emotion_dist:
            lines.append("| 情感 | 占比 | 典型表述 |")
            lines.append("|------|------|----------|")
            total = sum(emotion_dist.values())
            for emotion, count in emotion_dist.items():
                percentage = (count / total * 100) if total > 0 else 0
                lines.append(f"| {emotion} | {percentage:.1f}% | 见关键词 |")
        else:
            lines.append("暂无详细情感分析数据\n")

        # 关键词
        lines.append("\n### 4.2 关键词云图\n")
        keywords = sentiment.get('top_keywords', [])

        if keywords:
            lines.append("**高频词（TOP 20）：**\n")
            lines.append("```")
            for kw in keywords[:20]:
                lines.append(f"{kw['keyword']} ({kw['count']}次)")
            lines.append("```")

        # 公众诉求
        lines.append("\n### 4.3 公众主要诉求\n")
        demands = sentiment.get('public_demands', [])

        if demands:
            for idx, demand in enumerate(demands, 1):
                lines.append(f"{idx}. {demand}")
        else:
            lines.append("暂无明确诉求")

        lines.append("\n---\n")

        return lines

    def _format_risk_section(self, data: Dict[str, Any]) -> List[str]:
        """格式化风险评估部分"""
        lines = []
        risk = data.get('risk_assessment', {})

        lines.append("## 五、风险预警与评估\n")

        # 当前风险点
        lines.append("### 5.1 当前风险点\n")
        current_risks = risk.get('current_risks', [])

        if current_risks:
            lines.append("| 风险点 | 等级 | 平均风险分 | 事件数 |")
            lines.append("|--------|------|-----------|--------|")
            for r in current_risks[:5]:
                lines.append(f"| {r['department']} | {r['level_text']} | {r['avg_risk_score']} | {r['event_count']} |")
        else:
            lines.append("暂无风险点\n")

        # 风险等级统计
        lines.append("\n### 5.2 风险等级统计\n")
        risk_levels = risk.get('risk_levels', {})

        if risk_levels.get('red'):
            lines.append(f"**🔴 红色预警（极高）：** {', '.join(risk_levels['red'])}")
        if risk_levels.get('orange'):
            lines.append(f"**🟠 橙色预警（高）：** {', '.join(risk_levels['orange'])}")
        if risk_levels.get('yellow'):
            lines.append(f"**🟡 黄色预警（中）：** {', '.join(risk_levels['yellow'])}")

        lines.append("\n---\n")

        return lines

    def _format_recommendations_section(self, data: Dict[str, Any]) -> List[str]:
        """格式化建议部分"""
        lines = []
        recs = data.get('recommendations', {})

        lines.append("## 六、应对措施与处置建议\n")

        # 立即措施
        immediate = recs.get('immediate_actions', [])
        if immediate:
            lines.append("### 6.1 立即应对措施（24小时内）\n")
            for action in immediate:
                lines.append(f"{action}")

        # 短期措施
        short_term = recs.get('short_term_actions', [])
        if short_term:
            lines.append("\n### 6.2 短期应对措施（1周内）\n")
            for action in short_term:
                lines.append(f"{action}")

        # 长期措施
        long_term = recs.get('long_term_actions', [])
        if long_term:
            lines.append("\n### 6.3 长期预防措施（1-3个月）\n")
            for action in long_term:
                lines.append(f"{action}")

        # 监测重点
        monitoring = recs.get('monitoring', {})
        if monitoring:
            lines.append("\n### 6.4 舆情监测重点\n")
            lines.append(f"**监测频率：** {monitoring.get('frequency', '')}")

            keywords = monitoring.get('keywords', [])
            if keywords:
                lines.append("\n**关键词：**")
                for kw in keywords[:10]:
                    lines.append(f"- {kw}")

        lines.append("\n---\n")

        return lines

    def _format_impact_section(self, data: Dict[str, Any]) -> List[str]:
        """格式化影响预测部分"""
        lines = []
        impact = data.get('impact_forecast', {})

        lines.append("## 七、影响预测\n")

        # 短期
        short = impact.get('short_term', [])
        if short:
            lines.append("### 7.1 短期影响（1-7天）\n")
            for item in short:
                lines.append(f"- {item}")

        # 中期
        medium = impact.get('medium_term', [])
        if medium:
            lines.append("\n### 7.2 中期影响（1-4周）\n")
            for item in medium:
                lines.append(f"- {item}")

        # 长期
        long = impact.get('long_term', [])
        if long:
            lines.append("\n### 7.3 长期影响（1-3个月）\n")
            for item in long:
                lines.append(f"- {item}")

        # 法律风险
        legal = impact.get('legal_risk', {})
        if legal:
            lines.append("\n### 7.4 法律风险评估\n")
            lines.append(f"- **诉讼概率：** {legal.get('probability', '')}")
            lines.append(f"- **预估金额：** {legal.get('estimated_amount', '')}")
            lines.append(f"- **风险说明：** {legal.get('description', '')}")

        lines.append("\n---\n")

        return lines

    def _format_templates_section(self, data: Dict[str, Any]) -> List[str]:
        """格式化声明模板部分"""
        lines = []
        templates = data.get('response_templates', {})

        lines.append("## 八、官方声明模板\n")

        # 首次回应
        first = templates.get('first_response', '')
        if first:
            lines.append("### 8.1 首次回应模板\n")
            lines.append("```")
            lines.append(first)
            lines.append("```")

        # 进展通报
        progress = templates.get('progress_update', '')
        if progress:
            lines.append("\n### 8.2 调查进展模板\n")
            lines.append("```")
            lines.append(progress)
            lines.append("```")

        lines.append("\n---\n")

        return lines

    def _format_appendix_section(self, data: Dict[str, Any]) -> List[str]:
        """格式化附录部分"""
        lines = []
        appendix = data.get('appendix', {})

        lines.append("## 九、附录\n")

        # 事件清单
        event_list = appendix.get('event_list', [])
        if event_list:
            lines.append("### 附录A：负面舆情事件清单\n")
            lines.append("| ID | 时间 | 平台 | 类型 | 科室 | 风险分 | 状态 |")
            lines.append("|----|------|------|------|------|--------|------|")
            for event in event_list[:20]:
                lines.append(f"| {event['id']} | {event['time'][:10]} | {event['platform']} | {event['type']} | {event['department']} | {event['risk_score']} | {event['status']} |")

        # 联系方式
        contact = appendix.get('contact_info', {})
        if contact:
            lines.append("\n### 附录B：联系方式\n")
            monitoring = contact.get('monitoring_center', {})
            if monitoring:
                lines.append("**舆情监测中心：**")
                lines.append(f"- 负责人：{monitoring.get('负责人', '')}")
                lines.append(f"- 电话：{monitoring.get('电话', '')}")
                lines.append(f"- 邮箱：{monitoring.get('邮箱', '')}")

            crisis = contact.get('crisis_team', {})
            if crisis:
                lines.append("\n**危机公关小组：**")
                lines.append(f"- 组长：{crisis.get('组长', '')}")
                lines.append(f"- 成员：{', '.join(crisis.get('成员', []))}")

        lines.append("\n---\n")

        return lines
