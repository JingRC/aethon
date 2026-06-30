"""
AI 快讯模块 —— 多源聚合 + LLM 智能筛选/评分/摘要
"""
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── RSS 数据源 ──────────────────────────────────────────
DEFAULT_RSS_SOURCES = [
    "https://huggingface.co/blog/feed.xml",
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.36kr.com/feed",
    "https://www.ifanr.com/feed",
    "https://rss.arxiv.org/rss/cs.AI",
]

# GitHub Trending 备选（需要爬虫）
GITHUB_TRENDING_URL = "https://github.com/trending?since=daily"


def fetch_rss_entries(sources: list[str], max_per_source: int = 15) -> list[dict]:
    """抓取所有 RSS 源的条目，返回统一格式列表"""
    all_entries = []
    for url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_source]:
                all_entries.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "summary": _clean_html(entry.get("summary", "")),
                    "source": feed.feed.get("title", url),
                    "published": entry.get("published", ""),
                })
            logger.info(f"✓ RSS {url}: {min(len(feed.entries), max_per_source)} 条")
        except Exception as e:
            logger.warning(f"✗ RSS {url}: {e}")
    return all_entries


def fetch_github_trending(max_items: int = 10) -> list[dict]:
    """抓取 GitHub Trending 每日热门仓库"""
    entries = []
    try:
        resp = httpx.get(GITHUB_TRENDING_URL, timeout=15, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")
        repos = soup.select("article.Box-row")[:max_items]
        for repo in repos:
            h2 = repo.select_one("h2")
            desc = repo.select_one("p")
            entries.append({
                "title": h2.get_text(strip=True) if h2 else "",
                "url": "https://github.com" + h2.a["href"] if h2 and h2.a else "",
                "summary": desc.get_text(strip=True) if desc else "",
                "source": "GitHub Trending",
                "published": datetime.now(timezone.utc).isoformat(),
            })
        logger.info(f"✓ GitHub Trending: {len(entries)} 条")
    except Exception as e:
        logger.warning(f"✗ GitHub Trending: {e}")
    return entries


def build_news_prompt(entries: list[dict], count: int = 10) -> str:
    """构建给 LLM 的新闻筛选 prompt"""
    today = datetime.now().strftime("%Y年%m月%d日")
    items_text = "\n\n".join(
        f"[{i+1}] 标题: {e['title']}\n    来源: {e['source']}\n    摘要: {e['summary'][:300]}\n    链接: {e['url']}"
        for i, e in enumerate(entries)
    )

    return f"""你是资深AI科技编辑。以下是 {today} 的AI领域资讯（共{len(entries)}条候选）。

请从中**精选出最重要的{count}条新闻**，要求：
1. 优先选择对AI行业有重大影响的事件（融资/产品发布/技术突破/政策法规）
2. 去除重复报道（同一事件选最佳来源）
3. 去除纯营销软文

对每条新闻，用中文撰写一段**60-100字的精炼摘要**（抓住核心要点），并给出 **重要性评分（1-5星）**。

返回JSON数组格式（只返回JSON，不要markdown代码块）：
[
  {{
    "title": "中文标题（简洁有力）",
    "title_en": "English title",
    "summary_zh": "60-100字中文摘要",
    "summary_en": "English summary in 40-60 words",
    "source": "来源名称",
    "url": "原文链接",
    "score": 5
  }}
]

候选新闻列表：
{items_text}"""


def build_github_trending_prompt(repos: list[dict], count: int = 3) -> str:
    """构建 GitHub Trending LLM 总结 prompt（合并到日报中）"""
    if not repos:
        return ""
    items = "\n".join(f"- {r['title']}: {r['summary'][:200]}" for r in repos[:count])
    return f"\n\n【GitHub Trending 今日热点】\n{items}"


def _clean_html(html_text: str) -> str:
    """去除 HTML 标签"""
    if not html_text:
        return ""
    try:
        soup = BeautifulSoup(html_text, "lxml")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", "", html_text)


def normalise_score_distribution(items: list[dict]) -> list[dict]:
    """确保评分呈正态分布（不会全部5星或全部1星）"""
    scores = [it.get("score", 3) for it in items]
    if len(set(scores)) <= 1 and scores:
        # 全部同分 → 手动拉开差距
        for i, it in enumerate(items):
            it["score"] = max(1, min(5, 5 - i * 0.5))
    return items


# ── 辅助函数 ──────────────────────────────────────────

def get_today_key() -> str:
    """生成今天的日期键（北京时间）"""
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d")


def deduplicate_entries(entries: list[dict]) -> list[dict]:
    """按标题相似度去重"""
    seen = set()
    result = []
    for e in entries:
        key = hashlib.md5(e["title"].encode()[:50]).hexdigest()[:12]
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result
