#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情报告生成器 - Mail-Check专用版本
从SQLite数据库读取舆情数据，自动生成详细分析报告
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import os
import json

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class MailCheckReportGenerator:
    """Mail-Check舆情报告生成器"""

    def __init__(self, db_path: str = None):
        """
        初始化报告生成器

        Args:
            db_path: SQLite数据库路径，默认从config.yaml读取
        """
        self.db_path = self._normalize_db_path(db_path or self._get_default_db_path())
        self.conn = None

    def _get_default_db_path(self) -> str:
        """获取默认数据库路径"""
        # 尝试从config.yaml读取
        try:
            import yaml
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            config_path = os.path.join(project_root, 'config', 'config.yaml')

            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            db_path = config.get('runtime', {}).get(
                'database_path',
                os.path.join(project_root, 'data', 'processed_emails.db')
            )
            return db_path
        except:
            # 默认路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            return os.path.join(project_root, 'data', 'processed_emails.db')

    def _normalize_db_path(self, path: str) -> str:
        if not path:
            return path
        if os.path.isabs(path):
            return path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        return os.path.join(project_root, path)

    def connect(self):
        """连接数据库"""
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def query(self, sql: str, params: tuple = ()):
        """执行查询"""
        conn = self.connect()
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return rows

    def fetch_all_data(self, start_date: str = None, end_date: str = None, hospital: str = None):
        """
        获取所有负面舆情数据

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            hospital: 医院名称（可选，筛选特定医院）

        Returns:
            DataFrame: 舆情数据
        """
        # 清洗筛选参数
        if isinstance(hospital, str):
            hospital = hospital.strip()
            if hospital in ("all", "全部", "全院汇总", "all hospitals"):
                hospital = None

        if isinstance(start_date, str) and len(start_date) >= 10:
            start_date = start_date[:10]
        if isinstance(end_date, str) and len(end_date) >= 10:
            end_date = end_date[:10]

        # 构建SQL查询
        sql = """
            SELECT
                sentiment_id as ID,
                hospital_name as 医院,
                title as 标题,
                source as 来源,
                severity as 严重程度,
                processed_at as 创建时间,
                reason as 警示理由,
                content as 内容,
                url as 原文链接,
                status as 状态
            FROM negative_sentiments
            WHERE 1=1
        """
        params = []

        # 日期筛选
        if start_date:
            sql += " AND DATE(processed_at) >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND DATE(processed_at) <= ?"
            params.append(end_date)

        # 医院筛选
        if hospital:
            sql += " AND hospital_name = ?"
            params.append(hospital)

        sql += " ORDER BY processed_at DESC"

        # 执行查询
        rows = self.query(sql, tuple(params))

        # 转换为DataFrame
        data = []
        for row in rows:
            data.append({
                'ID': row['ID'],
                '医院': row['医院'],
                '标题': row['标题'],
                '来源': row['来源'],
                '严重程度': row['严重程度'],
                '创建时间': row['创建时间'],
                '警示理由': row['警示理由'],
                '内容': row['内容'],
                '原文链接': row['原文链接'],
                '状态': row['状态'] or 'active'
            })

        df = pd.DataFrame(data)

        if df.empty:
            return df

        # 添加风险分
        if '严重程度' in df.columns:
            df['风险分'] = df['严重程度'].apply(
                lambda x: 100 if x == 'high' else 60 if x == 'medium' else 30
            )

        return df

    def generate_report(
        self,
        start_date: str = None,
        end_date: str = None,
        hospital: str = None,
        report_period: str = None,
        output_format: str = 'markdown'
    ):
        """
        生成舆情报告

        Args:
            start_date: 开始日期
            end_date: 结束日期
            hospital: 医院名称
            report_period: 报告周期（如"2026年第一季度"）
            output_format: 输出格式（markdown/word）

        Returns:
            dict: 包含报告数据和文件路径
        """
        print(f"[INFO] 正在获取数据...")
        df = self.fetch_all_data(start_date, end_date, hospital)

        if len(df) == 0:
            print("[WARN] 没有找到符合条件的数据")
            return {
                'success': False,
                'message': '没有数据'
            }

        print(f"[INFO] 获取到 {len(df)} 条舆情数据")

        # 导入之前创建的report_generator
        try:
            import sys
            # 添加src目录到路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, current_dir)

            from report_generator import ReportGenerator
            gen = ReportGenerator()
        except ImportError:
            print("[ERROR] 无法导入ReportGenerator，请确保report_generator.py在src目录下")
            return {
                'success': False,
                'message': '缺少report_generator模块'
            }

        # 确定医院名称
        if hospital:
            hospital_name = hospital
        elif len(df) > 0:
            # 如果只有一个医院，使用它；否则使用通用名称
            unique_hospitals = df['医院'].unique()
            if len(unique_hospitals) == 1:
                hospital_name = unique_hospitals[0]
            else:
                hospital_name = "多医院汇总"
        else:
            hospital_name = "未知"

        # 确定报告周期
        if not report_period:
            if start_date and end_date:
                report_period = f"{start_date} 至 {end_date}"
            else:
                report_period = datetime.now().strftime('%Y年%m月')

        # 生成报告数据
        print(f"[INFO] 正在分析数据...")
        report_data = gen.generate_report_data(
            df=df,
            hospital_name=hospital_name,
            report_type='special',
            report_period=report_period
        )

        # 生成报告文件
        output_dir = Path(os.path.join(os.path.dirname(self.db_path), 'reports'))
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{hospital_name}_舆情报告_{timestamp}"

        result = {
            'success': True,
            'hospital_name': hospital_name,
            'period': report_period,
            'total_events': len(df),
            'high_risk_events': len(df[df['严重程度'] == 'high']),
            'files': {}
        }

        # Markdown格式
        if output_format in ['markdown', 'md', 'both']:
            md_path = output_dir / f"{filename}.md"
            print(f"[INFO] 正在生成Markdown报告...")
            gen.generate_markdown_report(report_data, str(md_path))
            result['files']['markdown'] = str(md_path)
            print(f"[OK] Markdown报告: {md_path}")

        # Word格式
        if output_format in ['word', 'docx', 'both'] and DOCX_AVAILABLE:
            docx_path = output_dir / f"{filename}.docx"
            print(f"[INFO] 正在生成Word报告...")
            gen.generate_word_report(report_data, str(docx_path))
            result['files']['word'] = str(docx_path)
            print(f"[OK] Word报告: {docx_path}")

        # 添加摘要
        result['summary'] = report_data['summary']
        result['overview'] = report_data['overview']

        self.close()
        return result


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='Mail-Check舆情报告生成器')
    parser.add_argument('--start-date', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--hospital', help='医院名称')
    parser.add_argument('--period', help='报告周期（如"2026年第一季度"）')
    parser.add_argument('--format', default='markdown', choices=['markdown', 'word', 'both'], help='输出格式')
    parser.add_argument('--db', help='数据库路径（可选）')

    args = parser.parse_args()

    # 创建报告生成器
    generator = MailCheckReportGenerator(db_path=args.db)

    # 生成报告
    print("="*60)
    print("  Mail-Check 舆情报告生成器")
    print("="*60)
    print()

    result = generator.generate_report(
        start_date=args.start_date,
        end_date=args.end_date,
        hospital=args.hospital,
        report_period=args.period,
        output_format=args.format
    )

    print()
    print("="*60)
    if result['success']:
        print("  报告生成成功！")
        print("="*60)
        print(f"医院: {result.get('hospital_name', 'N/A')}")
        print(f"周期: {result.get('period', 'N/A')}")
        print(f"事件总数: {result.get('total_events', 0)}")
        print(f"高风险事件: {result.get('high_risk_events', 0)}")
        print()
        print("生成的文件:")
        for fmt, path in result.get('files', {}).items():
            print(f"  [{fmt}] {path}")
    else:
        print("  报告生成失败")
        print("="*60)
        print(f"原因: {result.get('message', '未知错误')}")

    print()
    print("="*60)


if __name__ == "__main__":
    main()
