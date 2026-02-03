#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情报告生成器 - Mail-Check专用版本
从SQLite数据库读取舆情数据，自动生成详细分析报告
"""

import db
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import os
import json
import tempfile
import subprocess

try:
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except ImportError:
    WORDCLOUD_AVAILABLE = False

class MailCheckReportGenerator:
    """Mail-Check舆情报告生成器"""

    def __init__(self, db_path: str = None):
        """
        初始化报告生成器

        Args:
            db_path: SQLite数据库路径，默认从config.yaml读取
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(current_dir)
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
            self.conn = db.connect(self.project_root)
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

        # 导入增强版report_generator
        try:
            import sys
            # 添加src目录到路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, current_dir)

            from report_generator_enhanced import EnhancedReportGenerator
            gen = EnhancedReportGenerator()
        except ImportError:
            print("[ERROR] 无法导入EnhancedReportGenerator，请确保report_generator_enhanced.py在src目录下")
            return {
                'success': False,
                'message': '缺少report_generator_enhanced模块'
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

        # 生成关键词云（可选）
        wordcloud_name = self._generate_wordcloud(report_data, output_dir, filename)
        if wordcloud_name:
            report_data.setdefault('sentiment', {})['wordcloud_image'] = wordcloud_name
        wordcloud_path = output_dir / wordcloud_name if wordcloud_name else None

        result = {
            'success': True,
            'hospital_name': hospital_name,
            'period': report_period,
            'total_events': len(df),
            'high_risk_events': len(df[df['严重程度'] == 'high']),
            'files': {}
        }

        # 先生成Markdown内容（Word将基于Markdown转换）
        md_content = gen.generate_markdown_report(report_data)

        # Markdown格式
        if output_format in ['markdown', 'md', 'both']:
            md_path = output_dir / f"{filename}.md"
            print(f"[INFO] 正在生成Markdown报告...")
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            result['files']['markdown'] = str(md_path)
            print(f"[OK] Markdown报告: {md_path}")

        # Word格式（基于Markdown转换）
        if output_format in ['word', 'docx', 'both']:
            docx_path = output_dir / f"{filename}.docx"
            print(f"[INFO] 正在生成Word报告...")

            # 如果没有保存Markdown文件，则使用临时文件
            temp_md_path = None
            if 'markdown' in result['files']:
                md_for_docx = result['files']['markdown']
            else:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.md', dir=str(output_dir))
                temp_file.write(md_content.encode('utf-8'))
                temp_file.flush()
                temp_file.close()
                temp_md_path = temp_file.name
                md_for_docx = temp_md_path

            self._convert_markdown_to_docx(md_for_docx, str(docx_path))
            if wordcloud_path and wordcloud_path.exists():
                self._embed_wordcloud_in_docx(str(docx_path), str(wordcloud_path))
            result['files']['word'] = str(docx_path)
            print(f"[OK] Word报告: {docx_path}")

            if temp_md_path:
                try:
                    os.remove(temp_md_path)
                except OSError:
                    pass

        # 添加摘要
        result['summary'] = report_data['summary']
        result['overview'] = report_data['overview']

        self.close()
        return result

    def _find_chinese_font(self) -> str | None:
        """尝试寻找系统中文字体路径"""
        candidates = [
            # macOS
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            # Linux (common)
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/arphic/ukai.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
            # Windows (if mounted)
            "C:\\Windows\\Fonts\\msyh.ttc",
            "C:\\Windows\\Fonts\\simhei.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _generate_wordcloud(self, report_data: Dict[str, Any], output_dir: Path, filename: str) -> str | None:
        """根据关键词生成词云图片，返回相对文件名"""
        if not WORDCLOUD_AVAILABLE:
            print("[WARN] 未安装wordcloud，跳过关键词云生成")
            return None

        sentiment = report_data.get('sentiment', {})
        keywords = sentiment.get('top_keywords', [])
        if not keywords:
            return None

        font_path = self._find_chinese_font()
        if not font_path:
            print("[WARN] 未找到中文字体，跳过关键词云生成")
            return None

        freqs: Dict[str, int] = {}
        for item in keywords:
            if isinstance(item, dict):
                key = item.get('keyword')
                count = item.get('count', 1)
            else:
                try:
                    key, count = item
                except Exception:
                    continue
            if not key:
                continue
            freqs[str(key)] = int(count) if count else 1

        if not freqs:
            return None

        wc = WordCloud(
            font_path=font_path,
            width=1200,
            height=800,
            background_color="white",
            colormap="viridis",
            prefer_horizontal=1.0,
            max_rotation=0
        )
        wc.generate_from_frequencies(freqs)

        image_name = f"{filename}_wordcloud.png"
        image_path = output_dir / image_name
        wc.to_file(str(image_path))
        return image_name

    def _convert_markdown_to_docx(self, md_path: str, docx_path: str) -> None:
        """将Markdown转换为Word（优先pypandoc，其次调用pandoc命令）"""
        # 优先使用pypandoc
        try:
            import pypandoc  # type: ignore

            pypandoc.convert_file(md_path, 'docx', outputfile=docx_path)
            return
        except Exception:
            pass

        # 退回使用pandoc命令行
        try:
            subprocess.run(['pandoc', md_path, '-o', docx_path], check=True)
            return
        except FileNotFoundError as exc:
            raise RuntimeError("未找到pandoc，请先安装pandoc或pypandoc。") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"pandoc转换失败: {exc}") from exc

    def _embed_wordcloud_in_docx(self, docx_path: str, image_path: str) -> None:
        """将关键词云图片插入到Word文档中"""
        try:
            from docx import Document
            from docx.shared import Inches
            from docx.text.paragraph import Paragraph
            from docx.oxml import OxmlElement
        except ImportError:
            print("[WARN] 未安装python-docx，无法嵌入关键词云图片")
            return

        def _insert_paragraph_after(paragraph: Paragraph, text: str = "") -> Paragraph:
            new_p = OxmlElement("w:p")
            paragraph._p.addnext(new_p)
            new_para = Paragraph(new_p, paragraph._parent)
            if text:
                new_para.add_run(text)
            return new_para

        doc = Document(docx_path)
        target = None
        for p in doc.paragraphs:
            if "关键词云图" in p.text:
                target = p
                break

        if target:
            pic_par = _insert_paragraph_after(target)
            pic_par.add_run().add_picture(image_path, width=Inches(5.5))
        else:
            doc.add_heading("关键词云图", level=3)
            doc.add_picture(image_path, width=Inches(5.5))

        doc.save(docx_path)


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
