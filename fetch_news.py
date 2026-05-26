#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Daily World News Digest - Simplified Chinese Edition
Fetches news from RSS feeds, translates English to Chinese, generates HTML page,
and sends to Feishu webhook as interactive cards with images.
"""

import os
import sys
import datetime
import re
import json
from urllib.request import urlopen, Request
from urllib.parse import quote
import feedparser
import html as html_module


# RSS Feeds - Chinese sources only
RSS_FEEDS = [
    ("央视新闻", "https://rw2-cctvnews-rss-mbp.pages.dev/rss.xml"),
    ("新华社", "https://rsshub.app/xinhuanet"),
    ("澎湃新闻", "https://rsshub.app/thepaper/channel/310"),
    ("BBC中文", "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml"),
    ("36氪", "https://rsshub.app/36kr/newsflashes"),
    ("界面新闻", "https://rsshub.app/jiemian/channel/41"),
    ("FT中文网", "https://rsshub.app/ft/chinese"),
]

MAX_NEWS = 10

# Free translation API (MyMemory, no API key needed)
TRANSLATE_API = "https://api.mymemory.translated.net/get?q={}&langpair=en|zh-CN"


def translate_text(text):
    """Translate English text to Simplified Chinese using MyMemory API"""
    try:
        url = TRANSLATE_API.format(quote(text))
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        response = urlopen(req, timeout=5)
        data = json.loads(response.read().decode("utf-8"))
        translated = data.get("responseData", {}).get("translatedText", "")
        if translated:
            return translated
    except Exception:
        pass
    return text


def parse_rss_feed(url, source_name):
    """Parse an RSS feed using feedparser"""
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        response = urlopen(req, timeout=15)
        xml_data = response.read()

        feed = feedparser.parse(xml_data)

        articles = []
        for entry in feed.entries[:15]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = entry.get("summary", "")

            # Clean summary
            if summary:
                desc = re.sub(r"<[^>]+>", "", summary).strip()
                desc = re.sub(r"\s+", " ", desc)
                if len(desc) > 200:
                    desc = desc[:200] + "..."
            else:
                desc = ""

            # Try to get image from summary or media
            image = ""
            if summary:
                img_match = re.search(r'<img[^>]+src="([^"]+)"', summary)
                if img_match:
                    image = img_match.group(1)
            if not image:
                media = entry.get("media_content", [])
                if media:
                    image = media[0].get("url", "")

            if title:
                articles.append({
                    "title": title,
                    "link": link,
                    "description": desc,
                    "pub_date": entry.get("published", entry.get("updated", "")),
                    "image": image,
                    "source": source_name,
                })

        return articles
    except Exception as e:
        print(f"Warning: Failed to fetch {source_name}: {e}")
        return []


def fetch_all_news():
    """Fetch news from all sources"""
    all_articles = []
    for source, url in RSS_FEEDS:
        articles = parse_rss_feed(url, source)
        print(f"Fetched {len(articles)} articles from {source}")
        all_articles.extend(articles)
    return all_articles


def curate_top_news(articles, count=MAX_NEWS):
    """Select top N diverse news articles"""
    # Deduplicate
    seen = set()
    unique = []
    for article in articles:
        title_key = article["title"].lower().strip()[:50]
        if title_key not in seen:
            seen.add(title_key)
            unique.append(article)

    # Take first N
    return unique[:count]


def translate_articles(articles):
    """Translate English articles to Simplified Chinese"""
    translated = []
    for article in articles:
        title = article["title"]
        desc = article.get("description", "")

        # Check if article is in English
        if not any("\u4e00" <= c <= "\u9fff" for c in title):
            print(f"  Translating: {title[:50]}...")
            title = translate_text(title)
            if desc and not any("\u4e00" <= c <= "\u9fff" for c in desc):
                desc = translate_text(desc)

        article["title"] = title
        article["description"] = desc
        translated.append(article)

    return translated


def generate_html(articles, output_file):
    """Generate a styled HTML page"""
    today = datetime.date.today().strftime("%Y年%m月%d日")

    cards_html = ""
    for i, article in enumerate(articles, 1):
        image_html = ""
        if article.get("image"):
            image_html = f'<img src="{article["image"]}" alt="" onerror="this.parentElement.querySelector(\'.news-img-placeholder\').style.display=\'block\'" loading="lazy">'
        else:
            image_html = '<div class="news-img-placeholder">📰</div>'

        cards_html += f"""
        <div class="news-card">
            <div class="news-number">{i}</div>
            <div class="news-content">
                <div class="news-header">
                    <span class="source-badge">{article['source']}</span>
                    <h2><a href="{article['link']}" target="_blank">{html_module.escape(article['title'])}</a></h2>
                </div>
                <p class="news-summary">{html_module.escape(article.get('description', ''))}</p>
                <div class="news-footer">
                    <span class="news-time">{article.get('pub_date', '')}</span>
                    <a href="{article['link']}" target="_blank" class="read-more">阅读全文 →</a>
                </div>
            </div>
            <div class="news-image">
                {image_html}
            </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>每日世界新闻 - {today}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .header {{ text-align: center; padding: 30px 20px; color: white; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); }}
        .header .date {{ font-size: 1.1em; opacity: 0.9; }}
        .news-card {{
            background: white;
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            display: flex;
            gap: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
            transition: transform 0.3s ease;
            align-items: flex-start;
        }}
        .news-card:hover {{ transform: translateY(-3px); }}
        .news-number {{
            font-size: 2em; font-weight: bold; color: #667eea; min-width: 50px; text-align: center; line-height: 1;
        }}
        .news-content {{ flex: 1; }}
        .news-header {{ display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; }}
        .source-badge {{
            font-size: 0.75em; padding: 3px 10px; border-radius: 20px; font-weight: 600; white-space: nowrap;
            background: #e3f2fd; color: #1565c0;
        }}
        .news-header h2 {{ font-size: 1.2em; margin: 0; line-height: 1.4; }}
        .news-header h2 a {{ color: #2d3748; text-decoration: none; }}
        .news-header h2 a:hover {{ color: #667eea; }}
        .news-summary {{ color: #718096; line-height: 1.6; margin-bottom: 12px; font-size: 0.95em; }}
        .news-footer {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.85em; }}
        .news-time {{ color: #a0aec0; }}
        .read-more {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .news-image {{
            width: 140px; height: 100px; border-radius: 10px; overflow: hidden; flex-shrink: 0;
            background: #f7fafc; display: flex; align-items: center; justify-content: center;
        }}
        .news-image img {{ width: 100%; height: 100%; object-fit: cover; }}
        .news-img-placeholder {{ font-size: 2.5em; }}
        .footer {{ text-align: center; color: rgba(255,255,255,0.8); padding: 20px; font-size: 0.9em; }}
        @media (max-width: 600px) {{
            .news-card {{ flex-direction: column; }}
            .news-image {{ width: 100%; height: 150px; }}
            .header h1 {{ font-size: 1.8em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📰 每日世界新闻</h1>
            <div class="date">{today}</div>
        </div>
        {cards_html}
        <div class="footer">
            <p>Generated on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML page generated: {output_file}")


def send_to_feishu(webhook_url, articles):
    """Send news to Feishu webhook using interactive card format"""
    if not webhook_url:
        print("Warning: No FEISHU_WEBHOOK set. Skipping notification.")
        return

    try:
        import requests

        elements = []

        # Header
        elements.append({
            "tag": "markdown",
            "content": f"📰 每日世界新闻 - {datetime.date.today()}\n"
        })

        for i, article in enumerate(articles, 1):
            title = html_module.escape(article["title"])
            link = article["link"]
            source = article["source"]
            summary = article.get("description", "")[:100]

            # Title with link
            elements.append({
                "tag": "markdown",
                "content": f"**{i}. [{source}] [{title}]({link})**"
            })

            # Summary
            if summary:
                elements.append({
                    "tag": "markdown",
                    "content": summary
                })

            # Divider
            elements.append({"tag": "div", "divider_style": 0})

        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"content": "每日世界新闻", "tag": "plain_text"},
                    "template": {"value": "blue", "tag": "plain_text"}
                },
                "elements": elements
            }
        }

        response = requests.post(webhook_url, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                print("Feishu notification sent successfully!")
            else:
                print(f"Feishu API error: {result}")
                # Fallback to post format
                _send_post_format(webhook_url, articles)
        else:
            print(f"Feishu HTTP error: {response.status_code}")
            _send_post_format(webhook_url, articles)

    except Exception as e:
        print(f"Failed to send Feishu notification: {e}")
        _send_post_format(webhook_url, articles)


def _send_post_format(webhook_url, articles):
    """Fallback: send simple post format"""
    import requests

    lines = [f"📰 每日世界新闻 - {datetime.date.today()}\n"]
    for i, article in enumerate(articles, 1):
        title = article["title"]
        link = article["link"]
        source = article["source"]
        summary = article.get("description", "")[:100]

        lines.append(f"{i}. **{source}**")
        lines.append(f"{title}")
        if summary:
            lines.append(f"{summary}")
        lines.append("")

    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": "每日世界新闻",
                    "content": [
                        [{"tag": "text", "text": "\n".join(lines)}]
                    ]
                }
            }
        }
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                print("Feishu notification sent (post format)!")
    except Exception as e:
        print(f"Failed to send Feishu notification: {e}")


def main():
    print("=" * 50)
    print("📰 每日世界新闻")
    print("=" * 50)

    webhook_url = os.environ.get("FEISHU_WEBHOOK", "")

    print("\nFetching news...")
    all_articles = fetch_all_news()
    print(f"Total articles: {len(all_articles)}")

    if not all_articles:
        print("Error: No articles fetched.")
        sys.exit(1)

    top_news = curate_top_news(all_articles, MAX_NEWS)
    print(f"\nTop {len(top_news)} news selected:")
    for i, article in enumerate(top_news, 1):
        print(f"  {i}. {article['source']}: {article['title'][:60]}...")

    print("\nTranslating English articles...")
    top_news = translate_articles(top_news)

    print("\nGenerating HTML...")
    generate_html(top_news, "daily_news.html")

    print("\nSending to Feishu...")
    send_to_feishu(webhook_url, top_news)

    print("\n" + "=" * 50)
    print("✅ Done!")
    print("=" * 50)


if __name__ == "__main__":
    main()
