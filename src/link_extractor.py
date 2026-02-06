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
import platform
from typing import Iterable, List, Optional, Set
from urllib.parse import urlparse, parse_qs

import requests

try:
    # Playwright is optional now: CentOS 7 / glibc 2.17 often cannot run its bundled driver.
    from playwright.async_api import async_playwright  # type: ignore
except Exception:  # pragma: no cover
    async_playwright = None

class LinkExtractor:
    def __init__(self, config):
        self.config = config['browser']
        self.headless = self.config.get('headless', True)
        self.timeout = self.config.get('timeout', 30000)
        self.prefer_http = bool(self.config.get('prefer_http', True))
        self.allow_playwright_fallback = bool(self.config.get('allow_playwright_fallback', True))
        self.logger = logging.getLogger(__name__)
        
        # 存储拦截到的ID列表
        self.sentiment_ids = []

    def _glibc_too_old_for_playwright(self) -> bool:
        """
        Playwright's bundled driver (node) typically requires glibc >= 2.27.
        CentOS 7 is usually glibc 2.17, which will crash with:
        "GLIBC_2.27 not found" / "GLIBCXX_xxx not found".
        """
        try:
            libc, ver = platform.libc_ver()
            if libc != "glibc" or not ver:
                return False
            parts = []
            for p in ver.split("."):
                try:
                    parts.append(int(p))
                except Exception:
                    break
            if not parts:
                return False
            major = parts[0]
            minor = parts[1] if len(parts) > 1 else 0
            return (major, minor) < (2, 27)
        except Exception:
            return False

    def _extract_ids_from_text(self, text: str) -> Set[str]:
        ids: Set[str] = set()
        if not text:
            return ids

        # 1) Direct API URL strings e.g. "...searchListInfoH5?id=123,456"
        for m in re.findall(r"searchListInfoH5\\?id=([0-9,]{10,})", text):
            for x in m.split(","):
                x = x.strip()
                if x.isdigit() and len(x) >= 10:
                    ids.add(x)

        # 2) Common JSON field patterns
        for m in re.findall(r"\"id\"\\s*:\\s*\"(\\d{10,})\"", text):
            ids.add(m)
        for m in re.findall(r"\"id\"\\s*:\\s*(\\d{10,})", text):
            ids.add(m)

        # 3) Conservative fallback: pick long digit runs that look like sentiment IDs.
        # Avoid capturing unrelated short numbers.
        for m in re.findall(r"\\b(\\d{10,})\\b", text):
            ids.add(m)

        return ids

    def extract_ids_via_http(self, token: str) -> List[str]:
        """
        Try to extract IDs without any browser.
        This works if the H5 page includes IDs (embedded JSON / pre-rendered HTML),
        or contains the API URL strings.
        """
        url = f"https://lt.microvivid.com/h5List?token={token}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            r = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
            r.raise_for_status()
        except Exception as e:
            self.logger.warning(f"HTTP方式访问失败（将尝试兜底）：{e}")
            return []

        # Some deployments may return JSON directly.
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "application/json" in ctype:
            try:
                data = r.json()
                # Heuristic: search any string fields for ID patterns.
                blob = str(data)
                ids = self._extract_ids_from_text(blob)
                if ids:
                    return sorted(ids)
            except Exception:
                pass

        ids = self._extract_ids_from_text(r.text)
        return sorted(ids)
    
    async def extract_ids(self, token):
        """访问舆情链接，提取ID列表"""
        # 使用局部集合，避免跨邮件累计导致医院错配
        collected_ids = set()
        url = f"https://lt.microvivid.com/h5List?token={token}"
        
        self.logger.info(f"开始访问: {url}")

        # First try: no-browser HTTP extraction (works on CentOS 7 without Playwright).
        if self.prefer_http:
            http_ids = self.extract_ids_via_http(token)
            if http_ids:
                collected_ids.update(http_ids)
                self.sentiment_ids = sorted(collected_ids)
                self.logger.info(f"HTTP方式提取到 {len(self.sentiment_ids)} 个舆情ID")
                return self.sentiment_ids
            self.logger.info("HTTP方式未提取到ID，尝试浏览器兜底...")

        if not self.allow_playwright_fallback:
            self.logger.warning("已禁用Playwright兜底，返回空ID列表")
            self.sentiment_ids = sorted(collected_ids)
            return self.sentiment_ids

        if async_playwright is None:
            self.logger.error("Playwright未安装/不可用，且HTTP方式未取到ID")
            self.sentiment_ids = sorted(collected_ids)
            return self.sentiment_ids

        if self._glibc_too_old_for_playwright():
            self.logger.error(
                "检测到glibc版本过低（CentOS 7 常见），Playwright driver通常无法启动。"
                "建议：改用HTTP方式提取ID / 升级系统 / 使用Docker(Ubuntu)运行提取服务。"
            )
            self.sentiment_ids = sorted(collected_ids)
            return self.sentiment_ids

        # Playwright driver crashes often show up as:
        # "Connection closed while reading from the driver"
        # which is usually an OS dependency / glibc / browser-install issue (not business logic).
        browser = None
        context = None
        page = None

        max_retries = 2  # init + goto retries
        last_err = None
        for attempt in range(1, max_retries + 2):
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=self.headless)
                    context = await browser.new_context()
                    page = await context.new_page()

                    page.set_default_timeout(self.timeout)

                    async def handle_route(route, request):
                        if 'searchListInfoH5' in request.url:
                            self.logger.info(f"捕获到API请求: {request.url}")
                            ids = self.extract_ids_from_url(request.url)
                            if ids:
                                collected_ids.update(ids)
                                self.logger.info(f"提取到 {len(ids)} 个舆情ID: {ids}")
                        await route.continue_()

                    await page.route('**/*', handle_route)

                    await page.goto(url, wait_until='networkidle')
                    await page.wait_for_timeout(3000)

                    if not collected_ids:
                        self.logger.warning("未通过API捕获到ID，尝试从页面内容提取")
                        page_ids = await self.extract_ids_from_page(page)
                        collected_ids.update(page_ids)

                    self.sentiment_ids = sorted(collected_ids)
                    self.logger.info(f"总共提取到 {len(self.sentiment_ids)} 个舆情ID")
                    return self.sentiment_ids
            except Exception as e:
                last_err = e
                msg = str(e)
                # Add a targeted hint for the most common server-side failure mode.
                if "Connection closed while reading from the driver" in msg or "Connection.init" in msg:
                    self.logger.error(
                        "Playwright driver 启动失败（通常是系统依赖/GLIBC/浏览器未安装导致）。"
                        f" os={platform.platform()} python={platform.python_version()} err={e}"
                    )
                else:
                    self.logger.error(f"提取ID失败: {e}")
                if attempt <= max_retries:
                    self.logger.warning(f"重试 {attempt}/{max_retries}...")
                    await asyncio.sleep(1)
            finally:
                # Best-effort cleanup; objects may be None if init failed early.
                try:
                    if page:
                        await page.close()
                except Exception:
                    pass
                try:
                    if context:
                        await context.close()
                except Exception:
                    pass
                try:
                    if browser:
                        await browser.close()
                except Exception:
                    pass
        
        # Preserve old behavior: return [] on failure (caller will "skip").
        self.sentiment_ids = sorted(collected_ids)
        if last_err:
            self.logger.error(f"提取ID最终失败: {last_err}")
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
