#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情内容获取模块
从API获取舆情详情
"""

import requests
import yaml
import logging

class ContentFetcher:
    def __init__(self, config):
        self.config = config['sentiment']
        self.base_url = self.config['base_url']
        self.logger = logging.getLogger(__name__)
    
    def fetch_sentiment_details(self, ids):
        """批量获取舆情详情"""
        if not ids:
            self.logger.warning("ID列表为空")
            return []

        # 构建URL
        ids_param = ','.join(ids)
        url = f"{self.base_url}/vueData/searchListInfoH5?id={ids_param}"

        self.logger.info(f"请求API: {url}")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            if data.get('code') == 200:
                sentiments = data.get('data', [])
                self.logger.info(f"成功获取 {len(sentiments)} 条舆情")
                return sentiments
            else:
                self.logger.error(f"API返回错误: {data.get('msg')}")
                return []

        except requests.exceptions.Timeout:
            self.logger.error("请求超时")
            return []
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"解析响应失败: {e}")
            return []

    def fetch_single_sentiment(self, sentiment_id):
        """获取单个舆情详情（包含原文链接）"""
        if not sentiment_id:
            self.logger.warning("舆情ID为空")
            return None

        url = f"{self.base_url}/vueData/searchOneInfoH5?id={sentiment_id}"

        self.logger.info(f"请求单个舆情API: {url}")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            if data.get('code') == 200:
                sentiment = data.get('data', {})
                self.logger.info(f"成功获取舆情详情，ID: {sentiment_id}")
                return sentiment
            else:
                self.logger.error(f"API返回错误: {data.get('msg')}")
                return None

        except requests.exceptions.Timeout:
            self.logger.error("请求超时")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求失败: {e}")
            return None
        except Exception as e:
            self.logger.error(f"解析响应失败: {e}")
            return None

    def get_original_url(self, sentiment_id):
        """获取舆情的原文链接"""
        sentiment = self.fetch_single_sentiment(sentiment_id)

        if sentiment:
            original_url = sentiment.get('url', '')
            if original_url:
                self.logger.info(f"获取到原文链接: {original_url}")
                return original_url
            else:
                self.logger.warning("API返回的数据中没有原文链接字段")
                return None

        return None
    
    def get_sentiment_summary(self, sentiments):
        """获取舆情摘要"""
        if not sentiments:
            return "无舆情数据"
        
        total = len(sentiments)
        negative = len([s for s in sentiments if s.get('attitudeMerge') == '-1'])
        positive = len([s for s in sentiments if s.get('attitudeMerge') == '1'])
        
        summary = {
            'total': total,
            'negative': negative,
            'positive': positive,
            'sources': {}
        }
        
        # 统计来源
        for s in sentiments:
            source = s.get('webName', '未知')
            summary['sources'][source] = summary['sources'].get(source, 0) + 1
        
        return summary

if __name__ == '__main__':
    # 测试代码
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    fetcher = ContentFetcher(config)
    
    # 使用之前获取的测试ID
    test_ids = ['2393212730', '2393516860', '2393725037']
    
    sentiments = fetcher.fetch_sentiment_details(test_ids)
    
    print(f"\n获取到 {len(sentiments)} 条舆情:\n")
    
    for i, s in enumerate(sentiments, 1):
        print(f"{i}. {s.get('title', '无标题')}")
        print(f"   来源: {s.get('webName', '未知')}")
        print(f"   情感: {s.get('attitudeMerge', '未知')}")
        print()
