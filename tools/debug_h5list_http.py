#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""HTTP-only debug tool for Microvivid H5 token pages.

Usage:
  python3 tools/debug_h5list_http.py --token <TOKEN>
  python3 tools/debug_h5list_http.py --url "https://lt.microvivid.com/h5List?token=..."

It prints redirect chain, key headers, a short content preview, and tries to
extract sentiment IDs from the response body (no Playwright).
"""

from __future__ import annotations

import argparse
import re
from typing import List, Optional, Set
from urllib.parse import parse_qs, urlparse

import requests


def _extract_ids_from_text(text: str) -> List[str]:
    ids: Set[str] = set()
    if not text:
        return []

    # 1) API URL strings e.g. "...searchListInfoH5?id=123,456"
    for m in re.findall(r"searchListInfoH5\\?id=([0-9,]{10,})", text):
        for x in m.split(","):
            x = x.strip()
            if x.isdigit() and len(x) >= 10:
                ids.add(x)

    # 2) JSON-ish "id": "123..." or "id": 123...
    for m in re.findall(r"\"id\"\\s*:\\s*\"(\\d{10,})\"", text):
        ids.add(m)
    for m in re.findall(r"\"id\"\\s*:\\s*(\\d{10,})", text):
        ids.add(m)

    # 3) Conservative fallback: long digit runs
    for m in re.findall(r"\\b(\\d{10,})\\b", text):
        ids.add(m)

    return sorted(ids)

def _extract_ids_from_long_link(long_link: str) -> List[str]:
    try:
        parsed = urlparse(long_link)
        params = parse_qs(parsed.query)
        id_param = (params.get("id") or [""])[0]
        ids = [x.strip() for x in id_param.split(",") if x.strip().isdigit()]
        ids = [x for x in ids if len(x) >= 10]
        return ids
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", help="token from email")
    ap.add_argument("--url", help="full h5List/h5Detail URL")
    ap.add_argument(
        "--link-api",
        action="store_true",
        help="call /prod-api/system/link/<token> first and parse longLink ids",
    )
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--dump", help="write final response body to this file")
    ap.add_argument("--preview", type=int, default=1200, help="print first N chars")
    ap.add_argument(
        "--ua",
        default=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
    )
    args = ap.parse_args()

    if not args.url and not args.token:
        ap.error("need --token or --url")

    sess = requests.Session()

    if args.link_api:
        if not args.token:
            ap.error("--link-api requires --token")

        api_url = f"https://console.microvivid.com/prod-api/system/link/{args.token}"
        headers = {
            "User-Agent": args.ua,
            "Accept": "application/json, text/plain, */*",
        }
        print(f"LINK API: {api_url}")
        try:
            r = sess.get(api_url, headers=headers, timeout=args.timeout, allow_redirects=True)
            r.raise_for_status()
        except Exception as e:
            print(f"Link API request failed: {e}")
            return 2

        print(f"Final: {r.status_code} {r.url}")
        ctype = r.headers.get("Content-Type", "")
        print(f"Content-Type: {ctype}")
        body = r.text or ""
        print(f"Body chars: {len(body)}")
        if args.preview and body:
            print("\n=== LINK API PREVIEW ===")
            print(body[: args.preview])
            print("\n=== END PREVIEW ===\n")

        long_link: Optional[str] = None
        try:
            data = r.json()
            if isinstance(data, dict):
                if isinstance(data.get("data"), dict) and isinstance(data["data"].get("longLink"), str):
                    long_link = data["data"]["longLink"]
                elif isinstance(data.get("longLink"), str):
                    long_link = data["longLink"]
        except Exception:
            m = re.search(r"\"longLink\"\\s*:\\s*\"([^\"]+)\"", body)
            if m:
                long_link = m.group(1)

        if long_link:
            print(f"longLink: {long_link}")
            ids = _extract_ids_from_long_link(long_link)
            print(f"IDs from longLink: {len(ids)}")
            if ids:
                print("IDs:", ", ".join(ids[:50]))
        else:
            print("No longLink found in response.")

        # Continue to H5 URL as well (helps compare).
        print("\n----\n")

    url = args.url
    if not url:
        url = f"https://lt.microvivid.com/h5List?token={args.token}"

    headers = {
        "User-Agent": args.ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    print(f"URL: {url}")
    try:
        resp = sess.get(url, headers=headers, timeout=args.timeout, allow_redirects=True)
    except Exception as e:
        print(f"HTTP request failed: {e}")
        return 2

    if resp.history:
        print("Redirect chain:")
        for r in resp.history:
            loc = r.headers.get("Location", "")
            print(f"  {r.status_code} {r.url} -> {loc}")

    print(f"Final: {resp.status_code} {resp.url}")
    ctype = resp.headers.get("Content-Type", "")
    print(f"Content-Type: {ctype}")
    print(f"Content-Length header: {resp.headers.get('Content-Length', '')}")
    sc = resp.headers.get("Set-Cookie")
    if sc:
        print(f"Set-Cookie: {sc[:200]}{'...' if len(sc) > 200 else ''}")

    body = resp.text or ""
    print(f"Body chars: {len(body)}")

    if args.dump:
        with open(args.dump, "w", encoding="utf-8") as f:
            f.write(body)
        print(f"Dumped to: {args.dump}")

    if args.preview and body:
        print("\n=== BODY PREVIEW ===")
        print(body[: args.preview])
        print("\n=== END PREVIEW ===\n")

    ids = _extract_ids_from_text(body)
    print(f"Extracted IDs: {len(ids)}")
    if ids:
        print("Sample IDs:", ", ".join(ids[:30]))

    # Extra hint: detect whether the page likely needs JS to run.
    if not ids:
        if "__NUXT__" in body or "window.__NUXT__" in body:
            print("Hint: page looks like Nuxt; IDs may only appear after JS runs.")
        if "searchListInfoH5" not in body:
            print("Hint: API URL pattern not present in raw HTML.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
