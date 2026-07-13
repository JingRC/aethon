"""
Xiaohongshu image card renderer — Pillow-based 1080×1440 cards

Produces polished, eye-catching cards optimized for XHS feed:
- Cover card (gradient, branding)
- AI News cards (dark tech theme)
- Ancient Story cards (classical Chinese aesthetic)
- CTA card (call-to-action)
"""

import logging
import math
import os
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────
CARD_W = 1080
CARD_H = 1440
PADDING = 60
BORDER_RADIUS = 32

# ── Color palettes ────────────────────────────────────────
AI_BG = (10, 14, 39)              # deep navy
AI_CARD_BG = (24, 30, 60)         # dark card
AI_ACCENT = (0, 212, 255)         # cyan
AI_ACCENT2 = (123, 97, 255)       # purple
AI_TEXT = (230, 235, 245)         # off-white
AI_SUBTEXT = (140, 150, 180)      # gray-blue

STORY_BG = (245, 240, 232)        # warm parchment
STORY_CARD_BG = (255, 252, 245)   # cream
STORY_ACCENT = (196, 30, 58)      # Chinese red
STORY_ACCENT2 = (180, 130, 60)    # gold
STORY_TEXT = (60, 35, 20)         # dark brown
STORY_SUBTEXT = (140, 110, 80)    # tan

COVER_C1 = (15, 20, 50)           # cover gradient top
COVER_C2 = (60, 20, 40)           # cover gradient bottom


# ── Font loading ──────────────────────────────────────────
def _find_cjk_font() -> Optional[Path]:
    """Find a CJK font on the system (cross-platform)."""
    # Common locations
    candidates = [
        # GitHub Actions Ubuntu (fonts-noto-cjk)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",       # Microsoft YaHei
        "C:/Windows/Fonts/msyhbd.ttc",      # Microsoft YaHei Bold
        "C:/Windows/Fonts/simsun.ttc",      # SimSun
        "C:/Windows/Fonts/simhei.ttf",      # SimHei
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            return Path(p)
    return None


FONT_PATH = _find_cjk_font()
FONT_BOLD_PATH = FONT_PATH  # fallback


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a font at given size, falling back to default."""
    path = FONT_BOLD_PATH if bold else FONT_PATH
    if path and os.path.exists(path):
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            pass
    # Fallback: try common names
    for name in ["NotoSansCJK-Bold.ttc", "NotoSansCJK-Regular.ttc",
                 "msyh.ttc", "PingFang.ttc", "Arial.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ── Drawing helpers ───────────────────────────────────────

def _round_corners(im: Image.Image, radius: int = BORDER_RADIUS) -> Image.Image:
    """Apply rounded corners to an image by alpha compositing."""
    mask = Image.new("L", im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (im.size[0] - 1, im.size[1] - 1)],
                           radius=radius, fill=255)
    result = im.copy()
    result.putalpha(mask)
    return result


def _draw_gradient(draw: ImageDraw.Draw, size: tuple[int, int],
                   c1: tuple[int, ...], c2: tuple[int, ...],
                   vertical: bool = True):
    """Draw a linear gradient on the draw object."""
    w, h = size
    if vertical:
        for y in range(h):
            ratio = y / max(h - 1, 1)
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
    else:
        for x in range(w):
            ratio = x / max(w - 1, 1)
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            draw.line([(x, 0), (x, h)], fill=(r, g, b))


def _draw_card_bg(draw: ImageDraw.Draw, xy: tuple[int, int, int, int],
                  fill: tuple[int, ...], radius: int = 24):
    """Draw a rounded rectangle card background."""
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _draw_badge(draw: ImageDraw.Draw, xy: tuple[int, int],
                text: str, font: ImageFont.FreeTypeFont,
                bg: tuple[int, ...], fg: tuple[int, ...] = (255, 255, 255)):
    """Draw a pill badge with text. Returns (x_end, y_end)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 18, 8
    bx, by = xy
    draw.rounded_rectangle(
        [(bx, by), (bx + tw + pad_x * 2, by + th + pad_y * 2)],
        radius=th // 2 + pad_y, fill=bg)
    draw.text((bx + pad_x, by + pad_y), text, fill=fg, font=font)
    return (bx + tw + pad_x * 2, by + th + pad_y * 2)


def _text_width(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.Draw) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _wrap_text(text: str, font: ImageFont.FreeTypeFont,
               max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """Wrap text to fit within max_width."""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = list(paragraph)  # Character-based for CJK
        current = ""
        for ch in words:
            test = current + ch
            if _text_width(test, font, draw) <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
    return lines


# ── Card rendering functions ──────────────────────────────

def render_cover_card(date_str: str, news_count: int,
                      stories_count: int) -> Image.Image:
    """Render the cover/intro card."""
    im = Image.new("RGB", (CARD_W, CARD_H))
    draw = ImageDraw.Draw(im)
    _draw_gradient(draw, (CARD_W, CARD_H), COVER_C1, COVER_C2, vertical=True)

    # Decorative circles
    for i in range(3):
        r = 200 + i * 120
        alpha = 15 - i * 3
        cx, cy = CARD_W - 100 + i * 40, 100 + i * 60
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                     fill=(*AI_ACCENT[:3], alpha) if len(AI_ACCENT) == 4
                     else (AI_ACCENT[0], AI_ACCENT[1], AI_ACCENT[2], 15))

        # We can't do alpha in RGB mode, use a lighter shade approach
        shade = tuple(min(255, c + 200) for c in AI_ACCENT)
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                     outline=shade, width=2)

    # ── Content ──
    y = 200

    # Emoji icon (rendered as large text)
    icon_font = load_font(120, bold=True)
    draw.text((CARD_W // 2, y), "📬", fill=(255, 255, 255),
              font=icon_font, anchor="mt")

    y += 160

    # Title
    title_font = load_font(64, bold=True)
    title = "每日双拼日报"
    draw.text((CARD_W // 2, y), title, fill=(255, 255, 255),
              font=title_font, anchor="mt")

    y += 90

    # Subtitle
    sub_font = load_font(32, bold=False)
    draw.text((CARD_W // 2, y), f"AI 快讯 × 古代故事  |  {date_str}",
              fill=AI_SUBTEXT, font=sub_font, anchor="mt")

    y += 80

    # Divider line
    line_w = 200
    draw.line([(CARD_W // 2 - line_w, y), (CARD_W // 2 + line_w, y)],
              fill=AI_ACCENT, width=3)

    y += 80

    # Stats
    stat_font = load_font(48, bold=True)
    label_font = load_font(28, bold=False)

    for icon, count, label in [
        ("🤖", news_count, "条 AI 快讯精选"),
        ("🏯", stories_count, "则古代故事典故"),
    ]:
        # Icon + number on one line
        stat_text = f"{icon}  {count}"
        draw.text((CARD_W // 2, y), stat_text, fill=AI_ACCENT,
                  font=stat_font, anchor="mt")
        y += 55
        draw.text((CARD_W // 2, y), label, fill=AI_SUBTEXT,
                  font=label_font, anchor="mt")
        y += 90

    # Footer
    y = CARD_H - 200
    footer_font = load_font(24, bold=False)
    draw.text((CARD_W // 2, y), "每日自动生成 · 扫码看完整日报 ↓",
              fill=(100, 110, 140), font=footer_font, anchor="mt")

    return im


def render_ai_news_card(item: dict, index: int, total: int) -> Image.Image:
    """Render a single AI news item as a beautiful card."""
    im = Image.new("RGB", (CARD_W, CARD_H))
    draw = ImageDraw.Draw(im)

    # Background
    _draw_gradient(draw, (CARD_W, int(CARD_H * 0.45)),
                   (AI_BG[0] + 6, AI_BG[1] + 8, AI_BG[2] + 12), AI_BG,
                   vertical=True)
    draw.rectangle([(0, int(CARD_H * 0.45)), (CARD_W, CARD_H)], fill=AI_BG)

    # Top decorative line
    draw.line([(PADDING, 0), (CARD_W - PADDING, 0)],
              fill=AI_ACCENT, width=4)

    # ── Header ──
    y = 60
    header_font = load_font(28, bold=True)
    _draw_badge(draw, (PADDING, y), f"AI 快讯  {index}/{total}",
                header_font, AI_ACCENT, (0, 0, 0))

    y += 70

    # Score stars
    score = int(item.get("score", 3))
    stars = "★" * score + "☆" * (5 - score)
    score_font = load_font(32, bold=False)
    draw.text((PADDING, y), stars, fill=AI_ACCENT2, font=score_font)

    # Source badge
    source = item.get("source", "")
    if source:
        src_font = load_font(24, bold=False)
        src_w = _text_width(stars, score_font, draw) + 20
        _draw_badge(draw, (PADDING + src_w + 20, y), source, src_font,
                    (40, 50, 80), AI_SUBTEXT)

    y += 80

    # Title
    title = item.get("title", "")
    title_font = load_font(44, bold=True)
    title_lines = _wrap_text(title, title_font, CARD_W - PADDING * 2, draw)[:4]
    for line in title_lines:
        draw.text((PADDING, y), line, fill=AI_TEXT, font=title_font)
        y += 58
    y += 30

    # Divider
    div_y = y
    draw.line([(PADDING, div_y), (CARD_W // 3, div_y)],
              fill=AI_ACCENT, width=2)

    y += 50

    # Summary
    summary = item.get("summary_zh", "")
    if summary:
        body_font = load_font(32, bold=False)
        summary_lines = _wrap_text(summary, body_font,
                                   CARD_W - PADDING * 2, draw)[:6]
        for line in summary_lines:
            draw.text((PADDING, y), line, fill=AI_SUBTEXT, font=body_font)
            y += 44

    # ── Bottom card for key takeaway ──
    card_y = max(y + 60, CARD_H - 360)
    card_rect = [(PADDING, card_y), (CARD_W - PADDING, card_y + 240)]
    draw.rounded_rectangle(card_rect, radius=24, fill=AI_CARD_BG,
                           outline=(*AI_ACCENT2[:3], 60), width=2)

    # Key takeaway / insight
    takeaway_font = load_font(28, bold=False)
    insight = item.get("insight_zh", item.get("summary_zh", ""))[:120]
    insight_lines = _wrap_text(f"💡 {insight}", takeaway_font,
                               CARD_W - PADDING * 2 - 80, draw)[:3]
    ty = card_y + 40
    for line in insight_lines:
        draw.text((PADDING + 40, ty), line, fill=AI_ACCENT, font=takeaway_font)
        ty += 40

    # "Read more" hint
    hint_font = load_font(24, bold=False)
    draw.text((PADDING + 40, card_y + 180), "🔗 扫码查看完整日报，获取深度解析",
              fill=AI_SUBTEXT, font=hint_font)

    # ── Footer ──
    footer_font = load_font(22, bold=False)
    draw.text((CARD_W // 2, CARD_H - 60),
              "每日双拼日报 · 自动生成", fill=(80, 90, 120),
              font=footer_font, anchor="mt")

    return im


def render_story_card(story: dict, index: int, total: int) -> Image.Image:
    """Render a single ancient story as a classical-style card."""
    im = Image.new("RGB", (CARD_W, CARD_H))
    draw = ImageDraw.Draw(im)

    # Background: warm parchment
    draw.rectangle([(0, 0), (CARD_W, CARD_H)], fill=STORY_BG)

    # Decorative border
    border_margin = 20
    draw.rounded_rectangle(
        [(border_margin, border_margin),
         (CARD_W - border_margin, CARD_H - border_margin)],
        radius=16, outline=STORY_ACCENT2, width=3)

    # Top accent line
    draw.line([(PADDING, 0), (CARD_W - PADDING, 0)],
              fill=STORY_ACCENT, width=4)

    # ── Header ──
    y = 60
    header_font = load_font(28, bold=True)
    _draw_badge(draw, (PADDING, y), f"典故  {index}/{total}",
                header_font, STORY_ACCENT)

    # Dynasty + Category
    dynasty = story.get("dynasty", "")
    category = story.get("category", "")
    if dynasty or category:
        tag_font = load_font(24, bold=False)
        tag_x = PADDING + 150
        if dynasty:
            _draw_badge(draw, (tag_x, y), dynasty, tag_font,
                        STORY_ACCENT2, (255, 255, 255))
            tag_x += 120
        if category:
            _draw_badge(draw, (tag_x, y), category, tag_font,
                        (200, 180, 150), STORY_TEXT)

    y += 90

    # Title
    title = story.get("title", "")
    title_font = load_font(52, bold=True)
    title_lines = _wrap_text(title, title_font, CARD_W - PADDING * 2, draw)[:3]
    for line in title_lines:
        draw.text((PADDING, y), line, fill=STORY_TEXT, font=title_font)
        y += 66

    y += 20

    # Source citation
    source = story.get("source", "")
    if source:
        src_font = load_font(26, bold=False)
        draw.text((PADDING, y), f"📖 {source}", fill=STORY_SUBTEXT,
                  font=src_font)
        y += 40

    y += 30

    # Story content
    story_text = story.get("story_zh", "")
    if story_text:
        body_font = load_font(30, bold=False)
        story_lines = _wrap_text(story_text, body_font,
                                 CARD_W - PADDING * 2, draw)[:10]
        for line in story_lines:
            draw.text((PADDING, y), line, fill=STORY_TEXT, font=body_font)
            y += 44

    # ── Lesson highlight ──
    lesson = story.get("lesson", "")
    if lesson:
        lesson_y = max(y + 60, CARD_H - 340)
        # Gold accent line above lesson
        draw.line([(PADDING, lesson_y), (CARD_W // 3, lesson_y)],
                  fill=STORY_ACCENT2, width=2)

        lesson_y += 30
        lesson_font = load_font(32, bold=True)
        draw.text((PADDING, lesson_y), "💡 寓意", fill=STORY_ACCENT,
                  font=lesson_font)
        lesson_y += 55

        lesson_body = load_font(28, bold=False)
        lesson_lines = _wrap_text(lesson, lesson_body,
                                  CARD_W - PADDING * 2, draw)[:4]
        for line in lesson_lines:
            draw.text((PADDING, lesson_y), line, fill=STORY_TEXT,
                      font=lesson_body)
            lesson_y += 40

    # Fun fact
    fun_fact = story.get("fun_fact", "")
    if fun_fact and lesson_y < CARD_H - 180:
        fun_y = lesson_y + 30
        fun_font = load_font(26, bold=False)
        fun_lines = _wrap_text(f"📎 {fun_fact}", fun_font,
                               CARD_W - PADDING * 2, draw)[:2]
        draw.text((PADDING, fun_y), fun_lines[0] if fun_lines else "",
                  fill=STORY_SUBTEXT, font=fun_font)

    # ── Footer ──
    footer_font = load_font(22, bold=False)
    draw.text((CARD_W // 2, CARD_H - 60),
              "每日双拼日报 · 自动生成", fill=STORY_SUBTEXT,
              font=footer_font, anchor="mt")

    return im


def render_cta_card(date_str: str, github_url: str = "") -> Image.Image:
    """Render the final call-to-action card."""
    im = Image.new("RGB", (CARD_W, CARD_H))
    draw = ImageDraw.Draw(im)
    _draw_gradient(draw, (CARD_W, CARD_H), COVER_C2, COVER_C1, vertical=True)

    # Decorative elements
    for i in range(2):
        r = 250 + i * 100
        cx, cy = CARD_W // 2, CARD_H // 2
        shade = tuple(min(255, c + 80) for c in AI_ACCENT2)
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                     outline=shade, width=1)

    # Content
    y = 350

    emoji_font = load_font(100, bold=True)
    draw.text((CARD_W // 2, y), "📬", fill=(255, 255, 255),
              font=emoji_font, anchor="mt")

    y += 150

    title_font = load_font(56, bold=True)
    draw.text((CARD_W // 2, y), "想看完整日报？", fill=(255, 255, 255),
              font=title_font, anchor="mt")

    y += 80

    body_font = load_font(30, bold=False)
    for line in [
        "每天 10 条精选 AI 快讯",
        "20 则中国古代故事典故",
        "深度分析 + 百度百科链接",
        "全部免费，每日早 8 点推送",
    ]:
        draw.text((CARD_W // 2, y), line, fill=AI_SUBTEXT,
                  font=body_font, anchor="mt")
        y += 48

    y += 70

    # CTA button
    btn_w, btn_h = 500, 80
    btn_x, btn_y = CARD_W // 2 - btn_w // 2, y
    draw.rounded_rectangle(
        [(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)],
        radius=40, fill=AI_ACCENT)
    btn_font = load_font(36, bold=True)
    draw.text((CARD_W // 2, btn_y + btn_h // 2), "👇 扫码访问",
              fill=(0, 0, 0), font=btn_font, anchor="mm")

    y += 140

    # URL
    url_font = load_font(28, bold=False)
    display_url = github_url.replace("https://", "") if github_url else "daily.small-game.dev"
    draw.text((CARD_W // 2, y), f"🔗 {display_url}",
              fill=AI_ACCENT, font=url_font, anchor="mt")

    y += 60
    note_font = load_font(24, bold=False)
    draw.text((CARD_W // 2, y), "也支持邮件订阅，回复「订阅」获取详情",
              fill=(120, 130, 160), font=note_font, anchor="mt")

    # Footer
    footer_font = load_font(22, bold=False)
    draw.text((CARD_W // 2, CARD_H - 80),
              f"每日双拼日报 · {date_str}", fill=(100, 110, 140),
              font=footer_font, anchor="mt")

    return im


# ── Main entry point ──────────────────────────────────────

def render_xhs_cards(ai_news: list[dict], stories: list[dict],
                     output_dir: str = "docs/xhs",
                     max_news: int = 3, max_stories: int = 3) -> list[str]:
    """
    Render a complete set of XHS image cards.

    Returns list of saved file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y年%m月%d日")
    date_file = datetime.now().strftime("%Y%m%d")
    paths = []
    total_cards = 1 + min(len(ai_news), max_news) + min(len(stories), max_stories) + 1
    card_num = 0

    logger.info(f"🎨 开始渲染 XHS 图片卡片 ({total_cards} 张)...")

    # 1. Cover card
    card_num += 1
    cover = render_cover_card(today, len(ai_news), len(stories))
    cover_path = out / f"{date_file}_01_cover.png"
    cover.save(str(cover_path), "PNG", optimize=True)
    paths.append(str(cover_path))
    logger.info(f"  [{card_num}/{total_cards}] 封面卡片 → {cover_path.name}")

    # 2. AI News cards
    selected_news = ai_news[:max_news]
    for i, item in enumerate(selected_news):
        card_num += 1
        card = render_ai_news_card(item, i + 1, len(selected_news))
        card_path = out / f"{date_file}_{card_num:02d}_ai_{i+1}.png"
        card.save(str(card_path), "PNG", optimize=True)
        paths.append(str(card_path))
        logger.info(f"  [{card_num}/{total_cards}] AI快讯卡片 → {card_path.name}")

    # 3. Ancient Story cards
    selected_stories = stories[:max_stories]
    for i, story in enumerate(selected_stories):
        card_num += 1
        card = render_story_card(story, i + 1, len(selected_stories))
        card_path = out / f"{date_file}_{card_num:02d}_story_{i+1}.png"
        card.save(str(card_path), "PNG", optimize=True)
        paths.append(str(card_path))
        logger.info(f"  [{card_num}/{total_cards}] 故事卡片 → {card_path.name}")

    # 4. CTA card
    card_num += 1
    cta = render_cta_card(today,
                          f"https://github.com/JingRC/daily-dual-digest")
    cta_path = out / f"{date_file}_{card_num:02d}_cta.png"
    cta.save(str(cta_path), "PNG", optimize=True)
    paths.append(str(cta_path))
    logger.info(f"  [{card_num}/{total_cards}] CTA卡片 → {cta_path.name}")

    logger.info(f"✅ XHS 卡片渲染完成: {len(paths)} 张 → {out}/")
    return paths
