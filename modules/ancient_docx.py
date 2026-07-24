"""
Word 文档生成器 — 历史故事小红书发布套装

生成一份 .docx 文件，包含：
  1. 爆款标题
  2. 正文描述
  3. 话题标签
  4. 10 则故事速览表
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def build_history_xhs_prompt(stories: list[dict], count: int = 10) -> str:
    """构建历史故事 XHS 爆款文案 LLM prompt。"""
    story_blocks = []
    for i, s in enumerate(stories[:count], 1):
        blocks = (
            f"{i}. 标题：{s.get('title','')}\n"
            f"   朝代：{s.get('dynasty','')}\n"
            f"   分类：{s.get('category','')}\n"
            f"   故事摘要：{s.get('story_zh','')[:120]}\n"
            f"   启示：{s.get('lesson','')}\n"
        )
        story_blocks.append(blocks)

    return f"""你是一位小红书国学/历史类万粉博主，擅长用年轻化、有网感的语言包装中国传统文化。

请根据以下 {count} 则中国古代历史故事，撰写一篇小红书图文笔记的文案。

## 故事素材
{chr(10).join(story_blocks)}

## 写作要求

### 标题（≤20字）
- **必须制造好奇心缺口**：让人看了忍不住点开
- 公式参考："大多数人不知道的X个历史真相" / "古人的XX操作有多绝" / "读完这X个故事我悟了"
- **禁止**用"每日典故"、"历史卡片"等平淡表述
- 示例风格："10个被误读千年的成语" / "战国"卷王"有多拼" / "看完古人操作我跪了"

### 正文（300-500字）
- **用小红书口吻**：口语化但不低幼，像在跟闺蜜/兄弟分享有意思的冷知识
- **前3句必须抓人**：用一个最震撼/最颠覆/最好笑的故事开场
- 每段 1-2 句，用 emoji 做视觉锚点（🔥📖⚔️🏯💡 等）
- **不要**逐条罗列所有故事，而是选 3-4 个最精彩的展开讲
- 文末加一句引导互动的话（如"你最想穿越到哪个朝代？"）

### 话题标签（5-8个）
- 优先：#历史故事 #国学智慧 #成语典故 #古人智慧
- 补充：#每天学点历史 #传统文化 #冷知识 #读书笔记
- **必须全中文**，不要英文标签

## 返回 JSON（只返回 JSON，不要代码块）
{{
  "title": "爆款标题 ≤20字",
  "body": "正文 300-500字",
  "hashtags": ["标签1", "标签2", ...],
  "headline": "封面大字（≤8字，用于卡片封面）"
}}"""


def generate_ancient_docx(stories: list[dict],
                          xhs_copy: dict,
                          output_path: str) -> str:
    """生成历史故事小红书发布文案 Word 文档。"""
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    style = doc.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(6)

    # ── 标题 ──
    title_text = xhs_copy.get("title", "历史故事精选")
    h = doc.add_heading(title_text, level=1)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in h.runs:
        run.font.color.rgb = RGBColor(0xCC, 0x33, 0x33)

    # ── 日期 ──
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = date_para.add_run(datetime.now().strftime("%Y年%m月%d日"))
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    doc.add_paragraph()

    # ── 正文 ──
    body = xhs_copy.get("body", "")
    doc.add_heading("📝 正文描述", level=2)
    body_para = doc.add_paragraph(body[:800])
    body_para.paragraph_format.line_spacing = 1.6

    # ── 话题标签 ──
    hashtags = xhs_copy.get("hashtags", [])
    if hashtags:
        doc.add_heading("🏷️ 话题标签", level=2)
        tags_para = doc.add_paragraph("  ".join(hashtags))
        for run in tags_para.runs:
            run.font.color.rgb = RGBColor(0xCC, 0x33, 0x33)

    # ── 封面标题 ──
    headline = xhs_copy.get("headline", "")
    if headline:
        doc.add_heading("🖼️ 封面大字", level=2)
        hl = doc.add_paragraph(headline)
        for run in hl.runs:
            run.font.size = Pt(16)
            run.font.bold = True

    # ── 故事速览表 ──
    doc.add_heading("📜 10则故事速览", level=2)
    for i, s in enumerate(stories[:10], 1):
        title = s.get("title", "")
        dynasty = s.get("dynasty", "")
        category = s.get("category", "")
        lesson = s.get("lesson", "")

        h3 = doc.add_heading(f"#{i}  {dynasty} · {title}  [{category}]", level=3)
        for run in h3.runs:
            run.font.size = Pt(12)

        if lesson:
            p = doc.add_paragraph(f"💡 {lesson}")
            p.paragraph_format.line_spacing = 1.4

        doc.add_paragraph()

    doc.save(output_path)
    logger.info(f"[DOCX] 历史故事文案: {output_path}")
    return output_path
