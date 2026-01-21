#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
链接提取模块
使用Playwright访问舆情链接，提取舆情ID列表
"""

import asyncio
import re
import yaml
import logging
from playwright.async_api import async_playwright
from urllib.parse import urlparse, parse_qs

class LinkExtractor:
    def __init__(self, config):
        self.config = config['browser']
        self.headless = self.config.get('headless', True)
        self.timeout = self.config.get('timeout', 30000)
        self.logger = logging.getLogger(__name__)
        
        # 存储拦截到的ID列表
        self.sentiment_ids = []
    
    async def extract_ids(self, token):
        """访问舆情链接，提取ID列表"""
        # 使用局部集合，避免跨邮件累计导致医院错配
        collected_ids = set()
        url = f"https://lt.microvivid.com/h5List?token={token}"
        
        self.logger.info(f"开始访问: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()
            
            # 设置超时
            page.set_default_timeout(self.timeout)
            
            try:
                # 监控网络请求
                async def handle_route(route, request):
                    # 监听API请求
                    if 'searchListInfoH5' in request.url:
                        self.logger.info(f"捕获到API请求: {request.url}")
                        
                        # 提取ID参数
                        ids = self.extract_ids_from_url(request.url)
                        if ids:
                            collected_ids.update(ids)
                            self.logger.info(f"提取到 {len(ids)} 个舆情ID: {ids}")
                    
                    await route.continue_()
                
                await page.route('**/*', handle_route)

                # 访问页面（失败则重试）
                max_retries = 2
                for attempt in range(1, max_retries + 2):
                    try:
                        await page.goto(url, wait_until='networkidle')
                        # 等待页面完全加载
                        await page.wait_for_timeout(3000)
                        break
                    except Exception as e:
                        if attempt > max_retries:
                            raise
                        self.logger.warning(f"页面加载失败，重试 {attempt}/{max_retries}: {e}")
                        await page.wait_for_timeout(1000)
                
                # 如果没有捕获到ID，尝试从页面提取
                if not collected_ids:
                    self.logger.warning("未通过API捕获到ID，尝试从页面内容提取")
                    page_ids = await self.extract_ids_from_page(page)
                    collected_ids.update(page_ids)
                
                self.sentiment_ids = sorted(collected_ids)
                self.logger.info(f"总共提取到 {len(self.sentiment_ids)} 个舆情ID")
                
            except Exception as e:
                self.logger.error(f"提取ID失败: {e}")
            finally:
                await browser.close()
        
        return self.sentiment_ids
    
    def extract_ids_from_url(self, url):
        """从URL中提取ID"""
        try:
            # 解析URL参数
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            if 'id' in params:
                id_param = params['id'][0]
                # ID可能以逗号分隔
                ids = [id.strip() for id in id_param.split(',') if id.strip()]
                return ids
        except Exception as e:
            self.logger.error(f"解析URL ID失败: {e}")
        
        return []
    
    async def extract_ids_from_page(self, page):
        """从页面内容中提取ID"""
        try:
            # 获取页面内容
            content = await page.content()

            # 尝试匹配页面中的ID（如果页面中有显示）
            # 这里可以根据实际情况调整正则表达式
            # 示例：查找16位数字ID
            pattern = r'"id":\s*"(\d{10,})"'
            matches = re.findall(pattern, content)

            if matches:
                self.logger.info(f"从页面内容提取到 {len(matches)} 个ID")
                return list(set(matches))

        except Exception as e:
            self.logger.error(f"从页面提取ID失败: {e}")

        return []

if __name__ == '__main__':
    # 测试代码
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    extractor = LinkExtractor(config)

    # 使用之前获取的测试token
    test_token = "cb6ea6cecdb84722abd65ed4d6a3147e"

    ids = asyncio.run(extractor.extract_ids(test_token))
    print(f"提取到的ID列表: {ids}")
