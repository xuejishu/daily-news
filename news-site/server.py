#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
新闻网站后端服务器
提供新闻API接口，支持分类和搜索
"""

import json
import os
import sys
import datetime
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.parse import urlparse, parse_qs
import feedparser
import html as html_module


# News sources configuration
SOURCES = [
    # 热点
    {"name": "今日头条", "url": "https://rsshub.app/toutiao/hotlist", "category": "hot"},
    {"name": "新浪热榜", "url": "https://rsshub.app/sina/weibo/board/1", "category": "hot"},
    # 财经
    {"name": "财新网", "url": "https://rsshub.app/caixin/rss", "category": "finance"},
    {"name": "华尔街见闻", "url": "https://rsshub.app/wallstreetcn/news/global", "category": "finance"},
    # 科技
    {"name": "36氪", "url": "https://rsshub.app/36kr/newsflashes", "category": "tech"},
    {"name": "TechCrunch", "url": "https://rsshub.app/techcrunch/business", "category": "tech"},
    # 军事
    {"name": "环球网", "url": "https://rsshub.app/huanqiu", "category": "military"},
    {"name": "参考消息", "url": "https://rsshub.app/cankaoxiaoxi/fast", "category": "military"},
    # 游戏
    {"name": "游民星空", "url": "https://rsshub.app/gamersky/news", "category": "game"},
    {"name": "IGN", "url": "https://rsshub.app/ign/anything", "category": "game"},
    # 国际
    {"name": "BBC中文", "url": "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml", "category": "world"},
    {"name": "Reuters", "url": "https://rsshub.app/reuters/reutersWorld", "category": "world"},
    # 体育
    {"name": "虎扑", "url": "https://rsshub.app/hupu/jrs", "category": "sports"},
    {"name": "ESPN", "url": "https://www.espn.com/espn/news/rss", "category": "sports"},
]

MAX_NEWS = 100  # Total news items to fetch


def parse_rss_feed(url, source_name, category):
    """Parse an RSS feed"""
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        response = urlopen(req, timeout=10)
        feed = feedparser.parse(response.read())

        articles = []
        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = entry.get("summary", "")

            if summary:
                desc = re.sub(r"<[^>]+>", "", summary).strip()
                desc = re.sub(r"\s+", " ", desc)
                if len(desc) > 200:
                    desc = desc[:200] + "..."
            else:
                desc = ""

            # Get image
            image = ""
            if summary:
                img_match = re.search(r'<img[^>]+src="([^"]+)"', summary)
                if img_match:
                    image = img_match.group(1)

            if title:
                articles.append({
                    "title": title,
                    "link": link,
                    "summary": desc,
                    "image": image,
                    "source": source_name,
                    "category": category,
                    "time": entry.get("published", ""),
                })

        return articles
    except Exception as e:
        print(f"Warning: Failed to fetch {source_name}: {e}")
        return []


def fetch_all_news():
    """Fetch news from all sources"""
    all_articles = []
    for source in SOURCES:
        articles = parse_rss_feed(source["url"], source["name"], source["category"])
        print(f"Fetched {len(articles)} articles from {source['name']}")
        all_articles.extend(articles)

    # Sort by time (newest first)
    all_articles.sort(key=lambda x: x.get("time", ""), reverse=True)

    # Deduplicate
    seen = set()
    unique = []
    for article in all_articles:
        key = article["title"][:30]
        if key not in seen:
            seen.add(key)
            unique.append(article)

    return unique[:MAX_NEWS]


def load_or_fetch_news():
    """Load from cache or fetch new news"""
    cache_file = "news_cache.json"
    cache_time_file = "cache_time.json"

    # Check if cache is valid (less than 1 hour old)
    cache_time = None
    if os.path.exists(cache_time_file):
        with open(cache_time_file, "r", encoding="utf-8") as f:
            cache_time = json.load(f).get("time", 0)

    now = datetime.datetime.now().timestamp()
    if cache_time and (now - cache_time) < 3600:
        # Use cache
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fetch new news
    print("Fetching news...")
    news = fetch_all_news()

    # Save cache
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"news": news, "updated": datetime.datetime.now().isoformat()}, f, ensure_ascii=False)

    with open(cache_time_file, "w", encoding="utf-8") as f:
        json.dump({"time": now}, f)

    return news


class NewsHandler(BaseHTTPRequestHandler):
    """HTTP request handler for news API"""

    def do_GET(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/api/news":
            self.handle_get_news()
        elif parsed_path.path == "/":
            self.send_static_file("index.html")
        else:
            self.send_static_file(parsed_path.path.lstrip("/"))

    def handle_get_news(self):
        """Handle /api/news endpoint"""
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)

        category = params.get("category", ["all"])[0]
        search = params.get("search", [""])[0]

        news = load_or_fetch_news()

        # Filter by category
        if category and category != "all":
            news = [n for n in news if n.get("category") == category]

        # Filter by search
        if search:
            search = search.lower()
            news = [n for n in news if search in n["title"].lower() or search in n["summary"].lower()]

        # Return JSON
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        response = {
            "news": news,
            "total": len(news),
            "updated": datetime.datetime.now().isoformat()
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

    def send_static_file(self, filename):
        """Send static files"""
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

        if not os.path.exists(file_path):
            self.send_error(404, "File not found")
            return

        content_type = "text/html"
        if filename.endswith(".css"):
            content_type = "text/css"
        elif filename.endswith(".js"):
            content_type = "application/javascript"
        elif filename.endswith(".png"):
            content_type = "image/png"
        elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
            content_type = "image/jpeg"

        with open(file_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)


def main():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), NewsHandler)
    print(f"📰 新闻网站启动在 http://localhost:{port}")
    print(f"按 Ctrl+C 停止服务器")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.server_close()


if __name__ == "__main__":
    main()
