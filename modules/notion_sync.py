"""
Notion 同步模块 —— 每日日报自动推送到 Notion 数据库
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Notion API 配置
NOTION_API_VERSION = "2022-06-28"


def create_daily_page(
    token: str,
    database_id: str,
    ai_news: list[dict],
    stories: list[dict],
) -> Optional[str]:
    """
    在 Notion 数据库中创建每日日报页面

    Args:
        token: Notion Internal Integration Secret
        database_id: Notion 数据库 ID（从 URL 获取）
        ai_news: AI 快讯列表
        stories: 古代故事列表

    Returns:
        创建的页面 URL，失败返回 None
    """
    if not token or not database_id:
        logger.warning("Notion 配置不完整，跳过同步")
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    today_cn = datetime.now().strftime("%Y年%m月%d日")

    # ── 构建页面内容（blocks） ──
    children = _build_page_blocks(ai_news, stories, today_cn)

    # ── 调用 Notion API 创建页面 ──
    try:
        import httpx

        url = "https://api.notion.com/v1/pages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json",
        }

        # 页面属性（标题 + 日期）
        properties = {
            "Name": {  # 数据库标题列名（默认 "Name"，如果你的列名不同需修改）
                "title": [{"text": {"content": f"📬 每日双拼日报 — {today_cn}"}}]
            },
        }

        body = {
            "parent": {"database_id": database_id},
            "properties": properties,
            "children": children,
        }

        resp = httpx.post(url, headers=headers, json=body, timeout=30)

        if resp.status_code == 200:
            page_data = resp.json()
            page_id = page_data["id"].replace("-", "")
            page_url = f"https://notion.so/{page_id}"
            logger.info(f"✓ Notion 同步成功 → {page_url}")
            return page_url
        else:
            logger.error(f"✗ Notion API 错误 [{resp.status_code}]: {resp.text[:500]}")
            return None

    except Exception as e:
        logger.error(f"✗ Notion 同步失败: {e}")
        return None


def _build_page_blocks(
    ai_news: list[dict],
    stories: list[dict],
    today_cn: str,
) -> list[dict]:
    """构建 Notion 页面的 blocks（子块数组）"""
    blocks = []

    # ── 页面顶部简介 ──
    blocks.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"type": "text", "text": {"content": f"🤖 AI 快讯 {len(ai_news)} 条 · 🏯 古代故事 {len(stories)} 则 · 自动生成于 {today_cn}"}}
            ]
        }
    })
    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # ═══════════ AI 快讯板块 ═══════════
    blocks.append({
        "object": "block",
        "type": "heading_1",
        "heading_1": {
            "rich_text": [{"type": "text", "text": {"content": f"🤖 AI 快讯 · 今日必读 ({len(ai_news)} 条)"}}]
        }
    })

    for i, item in enumerate(ai_news, 1):
        stars = "★" * int(item.get("score", 3)) + "☆" * (5 - int(item.get("score", 3)))
        source = item.get("source", "")
        url = item.get("url", "")

        # 标题
        blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": f"{i}. {item.get('title', '')}  {stars}"}}]
            }
        })

        # 摘要
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": item.get("summary_zh", "")}}]
            }
        })

        # 来源 + 原文链接
        link_text = []
        if source:
            link_text.append({"type": "text", "text": {"content": f"📌 来源：{source}"}})
        if url:
            link_text.append({"type": "text", "text": {"content": "  🔗 "}})
            link_text.append({"type": "text", "text": {"content": "原文链接", "link": {"url": url}}})
        if link_text:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": link_text}
            })

    # 分隔线
    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # ═══════════ 古代故事板块 ═══════════
    blocks.append({
        "object": "block",
        "type": "heading_1",
        "heading_1": {
            "rich_text": [{"type": "text", "text": {"content": f"🏯 中国古代故事 · 典故 · 天文地理 ({len(stories)} 则)"}}]
        }
    })

    for i, story in enumerate(stories, 1):
        title = story.get("title", "")
        dynasty = story.get("dynasty", "")
        category = story.get("category", "")
        source = story.get("source", "")
        story_text = story.get("story_zh", "")
        lesson = story.get("lesson", "")
        fun_fact = story.get("fun_fact", "")
        links = story.get("_links", [])

        # 标题（折叠块）
        toggle_text = f"{i}. {title}"
        if dynasty:
            toggle_text += f"  ·  {dynasty}"
        if category:
            toggle_text += f"  ·  {category}"

        toggle_children = []

        # 出处标签
        toggle_children.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": f"📖 出处：{source}"}}],
                "icon": {"emoji": "📖"},
                "color": "brown_background",
            }
        })

        # 故事内容
        toggle_children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": story_text[:2000]}}]
            }
        })

        # 寓意（高亮块）
        if lesson:
            toggle_children.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {"content": f"💡 {lesson}"}}],
                    "icon": {"emoji": "💡"},
                    "color": "yellow_background",
                }
            })

        # 冷知识
        if fun_fact:
            toggle_children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": f"📎 {fun_fact}"}}]
                }
            })

        # 百度百科链接
        if links:
            link_rich = [{"type": "text", "text": {"content": "🔗 深入了解： "}}]
            for j, (text, url) in enumerate(links):
                if j > 0:
                    link_rich.append({"type": "text", "text": {"content": " · "}})
                link_rich.append({"type": "text", "text": {"content": text, "link": {"url": url}}})
            toggle_children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": link_rich}
            })

        # 折叠块
        blocks.append({
            "object": "block",
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": toggle_text}}],
                "children": toggle_children,
            }
        })

    return blocks


def get_or_create_database(token: str, parent_page_id: str, db_name: str = "每日日报归档") -> Optional[str]:
    """
    在指定页面下查找或创建日报数据库
    返回数据库 ID
    """
    # 先直接返回 None，让用户手动提供 database_id
    # Notion API 的数据库搜索比较复杂，建议用户手动创建
    return None
