#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 token 进行舆情抓取与AI判断（不推送、不入库）
用法:
  python3 src/test_ai_by_token.py --token <token>
"""

import argparse
import asyncio
import os
import sys
import yaml

# 让脚本可直接调用 src 内部模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from link_extractor import LinkExtractor
from content_fetcher import ContentFetcher
from sentiment_analyzer import SentimentAnalyzer


def load_config():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(root, "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="按 token 抓取舆情并做AI判断（不推送）")
    parser.add_argument("--token", required=True, help="邮件中的 token")
    parser.add_argument("--max", type=int, default=0, help="最多分析前 N 条（默认全部）")
    args = parser.parse_args()

    config = load_config()
    token = args.token.strip()

    extractor = LinkExtractor(config)
    fetcher = ContentFetcher(config)
    analyzer = SentimentAnalyzer(config)

    print(f"Token: {token}")
    ids = asyncio.run(extractor.extract_ids(token))
    if not ids:
        print("未提取到舆情ID，结束。")
        return

    print(f"提取到 {len(ids)} 个舆情ID")
    sentiments = fetcher.fetch_sentiment_details(ids)
    if not sentiments:
        print("未获取到舆情详情，结束。")
        return

    if args.max and args.max > 0:
        sentiments = sentiments[:args.max]

    print(f"开始分析 {len(sentiments)} 条舆情...\n")
    negative_count = 0

    for idx, sentiment in enumerate(sentiments, 1):
        title = sentiment.get("title", "无标题")
        hospital_name = sentiment.get("hospitalName") or sentiment.get("hospital_name") or "未知医院"
        result = analyzer.analyze(sentiment, hospital_name)
        if result.get("is_negative"):
            negative_count += 1

        print(f"[{idx}/{len(sentiments)}] {title}")
        print(f"  医院: {hospital_name}")
        print(f"  来源: {sentiment.get('webName', '未知')}")
        print(f"  结论: {'负面' if result.get('is_negative') else '非负面'}")
        print(f"  理由: {result.get('reason')}")
        print(f"  严重程度: {result.get('severity')}")
        print("-" * 40)

    print(f"\n完成。负面数: {negative_count}/{len(sentiments)}")


if __name__ == "__main__":
    main()
