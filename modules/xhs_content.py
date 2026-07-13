"""
Xiaohongshu content generator — LLM-powered viral copywriting

Takes daily digest content and transforms it into XHS-optimized:
- Clickbait titles with curiosity gaps
- Emoji-rich scannable body text
- Algorithm-friendly hashtags
- Image captions for each card
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def build_xhs_prompt(ai_news: list[dict], stories: list[dict],
                     news_count: int = 3, stories_count: int = 3) -> str:
    """Build the LLM prompt for XHS content generation."""
    today = datetime.now().strftime("%Y年%m月%d日")

    # ── Summarize AI news for the prompt ──
    news_summary = []
    for i, item in enumerate(ai_news[:news_count], 1):
        news_summary.append(
            f"{i}. {item.get('title', '')}\n"
            f"   来源: {item.get('source', '')}\n"
            f"   摘要: {item.get('summary_zh', '')[:180]}\n"
            f"   评分: {'★' * int(item.get('score', 3))}"
        )
    news_str = "\n\n".join(news_summary) if news_summary else "无"

    # ── Summarize stories for the prompt ──
    story_summary = []
    for i, story in enumerate(stories[:stories_count], 1):
        story_summary.append(
            f"{i}. {story.get('title', '')}\n"
            f"   朝代: {story.get('dynasty', '')} | 分类: {story.get('category', '')}\n"
            f"   出处: {story.get('source', '')}\n"
            f"   故事: {story.get('story_zh', '')[:200]}\n"
            f"   寓意: {story.get('lesson', '')}"
        )
    story_str = "\n\n".join(story_summary) if story_summary else "无"

    prompt = f"""你是小红书（Xiaohongshu / RED）顶级内容运营专家，擅长创作爆款笔记。

今天是 {today}。我需要你为「每日双拼日报」创建一篇小红书爆款笔记。

## 原始素材

### 🤖 AI 快讯（共{len(ai_news)}条，精选前{news_count}条）
{news_str}

### 🏯 古代故事典故（共{len(stories)}条，精选前{stories_count}条）
{story_str}

## 创作要求

### 1. 标题（≤20字）
- 必须用「数字 + 悬念 + 痛点/好奇心」公式
- 风格参考：
  - "🚨 今天的AI圈又地震了…"
  - "今天这3条AI新闻，第2条让我失眠"
  - "😱 99%的人不知道，司马光砸缸真相是…"
  - "ChatGPT又搞大事了？今天AI圈炸了"
  - "今天的AI快讯，1条比1条炸裂🔥"
- 用emoji但不要太多（1-2个）
- 制造好奇心缺口：让人忍不住点进来

### 2. 正文（300-800字）
- **第一行**（最重要！）：用一句极具冲击力的话开篇，让人想继续读
- 每段1-2句话，大量换行
- 善用emoji作为视觉锚点（每段开头加emoji）
- 口语化，像朋友在分享，不要太正式
- 用"你"、"我"建立亲近感
- 在关键信息处使用 **加粗风格文字**（用【】标注重点）
- 末尾加一句互动话术（"你觉得哪个最…"、"评论区告诉我…"）
- 风格：信息密度高 + 阅读体验轻（看着不累）

### 3. AI快讯板块写法（占50%篇幅）
- 每条快讯提炼成 2-3 句，只说核心
- 用评分⭐标注重要程度
- 给每条加一个"一句话点评"（要有态度、有个性）
- 格式示例：
  ```
  🚀 重磅消息！今天AI圈发生了几件大事…

  ⭐⭐⭐⭐⭐ 第一条
  OpenAI深夜发布新模型，性能直接翻倍…
  💬 我的看法：这次更新比想象中更猛

  ⭐⭐⭐⭐ 第二条
  ...
  ```

### 4. 古代故事板块写法（占50%篇幅）
- 选最颠覆认知/最有趣的故事深入写
- 用「先说结论→再说出处→最后寓意」的结构
- 历史趣考类要突出"颠覆常识"的感觉
- 加入"冷知识"标签增加分享欲
- 格式示例：
  ```
  📜 今天听到一个古人居然…

  你知道吗？（悬念）

  其实真相是…（史实）

  💡 这个故事告诉我们…（寓意）
  ```

### 5. 话题标签
- 5-8个标签
- 用小红书热门标签 + 垂直标签的组合
- 示例：#AI #人工智能 #每日AI快讯 #科技前沿 #ChatGPT #古代智慧 #国学经典 #历史冷知识

## 返回格式（纯JSON，不要markdown代码块）

{{
  "title": "小红书标题（≤20字）",
  "body": "小红书正文（300-800字，大量换行和emoji）",
  "hashtags": ["#标签1", "#标签2", "#标签3", "#标签4", "#标签5", "#标签6", "#标签7"],
  "news_captions": [
    "第1张AI快讯图片的小红书配文（一句话，≤50字）",
    "第2张…",
    "第3张…"
  ],
  "story_captions": [
    "第1张故事图片的小红书配文（一句话，≤50字）",
    "第2张…",
    "第3张…"
  ]
}}"""

    return prompt


def format_news_for_xhs(item: dict) -> dict:
    """Add XHS-specific fields to an AI news item for card rendering."""
    return {
        **item,
        "insight_zh": item.get("insight_zh", item.get("summary_zh", "")),
    }


def format_story_for_xhs(story: dict) -> dict:
    """Add XHS-specific fields to a story for card rendering."""
    return story
