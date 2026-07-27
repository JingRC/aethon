"""
石头禅修 — 绘本卡片渲染器

将 AI 生成的图片 + LLM 写的故事文字合成绘本风格的 PNG 卡片。
封面 + N 页故事 = 一本迷你绘本。
"""

import json
import logging
from datetime import date
from pathlib import Path

from modules.xhs_renderer import render_html_to_png

logger = logging.getLogger(__name__)

CARD_W = 1080
CARD_H = 1440

# 绘本风格的柔和配色
PALETTE = {
    "bg": "#faf7f2",
    "text": "#3d3226",
    "accent": "#8b6914",
    "muted": "#8b775a",
    "surface": "#f0e8d8",
    "gold": "#c4a35a",
    "overlay": "rgba(30,25,18,0.55)",
    "overlay_light": "rgba(30,25,18,0.35)",
}


def _build_story_html(page: dict, img_path: str, page_num: int, total: int) -> str:
    """构建单页故事 HTML。"""
    text = page.get("text", "")
    img_bg = ""
    if img_path:
        img_uri = Path(img_path).resolve().as_uri()
        img_bg = (
            f'<div style="position:absolute;inset:0;'
            f'background:url({img_uri}) center/cover no-repeat;'
            f'z-index:0;"></div>'
        )

    # 底部文字区域高度取决于文字长度
    char_count = len(text)
    text_area_h = "28%" if char_count > 60 else ("22%" if char_count > 30 else "18%")

    page_label = f"{page_num} / {total}" if page_num > 0 else ""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@300;400;700;900&display=swap');

* {{ margin:0; padding:0; box-sizing:border-box; }}

html, body {{
  width:{CARD_W}px; height:{CARD_H}px; overflow:hidden;
  font-family:'Noto Serif SC','STSong','SimSun','KaiTi',serif;
  background:{PALETTE["bg"]}; position:relative;
}}

.story-text-area {{
  position:absolute; bottom:0; left:0; right:0; height:{text_area_h};
  background:linear-gradient(180deg, transparent 0%, {PALETTE["overlay"]} 15%, {PALETTE["overlay"]} 100%);
  z-index:2; display:flex; align-items:center; justify-content:center;
  padding:30px 80px;
}}

.story-text {{
  font-size:44px; font-weight:400; color:#fdf6ee; line-height:1.7;
  text-align:center; text-shadow:0 2px 8px rgba(0,0,0,0.4);
  max-width:900px;
}}

.page-num {{
  position:absolute; bottom:20px; right:40px; z-index:3;
  font-size:22px; font-weight:300; color:rgba(255,255,255,0.6);
  letter-spacing:2px;
}}

/* 封面特殊样式 */
.cover-title {{
  font-size:88px; font-weight:900; color:#fdf6ee;
  letter-spacing:10px; line-height:1.2;
  text-shadow:0 4px 24px rgba(0,0,0,0.6), 0 0 60px rgba(180,140,80,0.3);
}}
.cover-subtitle {{
  font-size:36px; font-weight:400; color:rgba(255,255,255,0.85);
  letter-spacing:6px; margin-top:16px;
  text-shadow:0 2px 10px rgba(0,0,0,0.5);
}}
.cover-date {{
  font-size:28px; font-weight:300; color:rgba(255,255,255,0.7);
  letter-spacing:4px; margin-bottom:40px;
  text-shadow:0 1px 6px rgba(0,0,0,0.5);
}}
</style></head><body>
{img_bg}
<div class="story-text-area">
  <div class="story-text">{text}</div>
</div>
<div class="page-num">{page_label}</div>
</body></html>"""


def _build_cover_html(cover_page: dict, img_path: str, today: date, total: int, headline: str = "") -> str:
    """构建封面 HTML。"""
    img_bg = ""
    if img_path:
        img_uri = Path(img_path).resolve().as_uri()
        img_bg = (
            f'<div style="position:absolute;inset:0;'
            f'background:url({img_uri}) center/cover no-repeat;'
            f'z-index:0;"></div>'
        )

    title = headline or cover_page.get("title", "石头的禅修")
    subtitle = cover_page.get("subtitle", f"一个关于{total}个瞬间的故事")

    # 日期
    cn = "零一二三四五六七八九十"
    y, m, d = today.year, today.month, today.day

    def yn(n):
        return "".join(cn[int(c)] for c in str(n))

    cn_date = f"公元{yn(y)}年"
    cn_date += f"{cn[m]}月" if m <= 10 else f"十{'一二'[m-11]}月"
    if d <= 10:
        cn_date += f"{cn[d]}日"
    elif d < 20:
        cn_date += f"十{cn[d-10]}日"
    elif d == 20:
        cn_date += "二十日"
    elif d < 30:
        cn_date += f"二十{cn[d-20]}日"
    elif d == 30:
        cn_date += "三十日"
    else:
        cn_date += "三十一日"

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@300;400;700;900&display=swap');

* {{ margin:0; padding:0; box-sizing:border-box; }}

html, body {{
  width:{CARD_W}px; height:{CARD_H}px; overflow:hidden;
  font-family:'Noto Serif SC','STSong','SimSun','KaiTi',serif;
  background:#1a150e; position:relative;
}}

.cover-overlay {{
  position:absolute; inset:0; z-index:1;
  background:radial-gradient(ellipse at center,
    rgba(0,0,0,0.15) 0%,
    rgba(0,0,0,0.45) 55%,
    rgba(0,0,0,0.72) 100%);
}}

.cover-content {{
  position:relative; z-index:3;
  display:flex; flex-direction:column;
  align-items:center; justify-content:center;
  height:100%; text-align:center; padding:80px 60px;
}}

.cover-date {{ font-size:28px; font-weight:300; color:rgba(255,255,255,0.7);
  letter-spacing:4px; margin-bottom:48px; text-shadow:0 1px 6px rgba(0,0,0,0.5); }}

.cover-title {{ font-size:88px; font-weight:900; color:#fdf6ee;
  letter-spacing:10px; line-height:1.2;
  text-shadow:0 4px 24px rgba(0,0,0,0.6), 0 0 60px rgba(180,140,80,0.3); }}

.cover-subtitle {{ font-size:36px; font-weight:400; color:rgba(255,255,255,0.85);
  letter-spacing:6px; margin-top:20px;
  text-shadow:0 2px 10px rgba(0,0,0,0.5); }}

.cover-line {{ width:120px; height:2px;
  background:linear-gradient(to right,transparent,{PALETTE["gold"]}cc,transparent);
  margin:32px auto; }}

.cover-page-count {{ font-size:24px; font-weight:300; color:rgba(255,255,255,0.55);
  letter-spacing:4px; margin-top:36px;
  text-shadow:0 1px 4px rgba(0,0,0,0.4); }}

.cover-series {{ position:absolute; bottom:40px; z-index:3;
  font-size:22px; font-weight:300; color:rgba(255,255,255,0.45);
  letter-spacing:4px; text-align:center; width:100%; }}
</style></head><body>
{img_bg}
<div class="cover-overlay"></div>
<div class="cover-content">
  <div class="cover-date">{cn_date}</div>
  <div class="cover-title">{title}</div>
  <div class="cover-subtitle">{subtitle}</div>
  <div class="cover-line"></div>
  <div class="cover-page-count">{total + 1} 页绘本</div>
</div>
<div class="cover-series">🪨 石头的禅修 · 每日一页</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════
# LLM Prompt 构建
# ═══════════════════════════════════════════════════════════

STONE_CHARACTER = (
    "a round smooth grey river stone with simple dot eyes and a gentle curved smile, "
    "small stubby arms and legs, kawaii chibi proportions, "
    "picture book illustration style, soft watercolor texture, warm earthy tones, "
    "zen aesthetic, children's book art, consistent character design"
)


def build_stone_story_prompt(max_pages: int = 12) -> str:
    """构建石头禅修绘本故事 LLM prompt。"""
    themes = [
        "等待的意义", "放下的智慧", "孤独是一种礼物", "慢下来的力量",
        "不争的哲学", "接受不完美", "安静的勇气", "时间的答案",
        "柔软的力量", "存在本身就是价值", "风雨都是过客", "扎根与生长",
    ]
    import random
    theme = random.choice(themes)

    return f"""你是一位绘本作家，创作一个以"石头"为主角的禅意绘本故事。

## 角色设定

主角是一块圆润的河石，有简单的眼睛和微笑。它坐在山顶上，看云来云往，看世间万物。它不说话，但它的存在本身就是一种智慧。

## 故事主题：{theme}

## 创作要求

### 故事结构
- 共 {max_pages} 页（包括封面文字）
- 每页 1-3 句话，15-40 字，像绘本一样精炼
- 有情感弧线：开头引发好奇 → 中间递进展开 → 结尾留白余味
- 语言风格：温柔、有禅意、但不说教。像在跟读者一起发现，而不是在讲道理
- 每一页都是一个独立的画面，读者翻到下一页会有期待

### 每页的图像描述（image_prompt）
- 用英文撰写（AI 生图需要）
- 必须以 "{STONE_CHARACTER}" 开头（保证石头形象统一）
- 然后描述这一页的场景和氛围
- 不同页面之间场景要有变化（山顶→溪边→星空→竹林→雨中→日出等）
- 季节和光线变化增加视觉丰富度

### 封面
- headline：≤8 字的封面大字
- title：完整标题
- subtitle：一句话简介

## 返回 JSON（只返回 JSON，不要代码块）

{{
  "title": "石头的禅修 · XXX",
  "headline": "封面大字 ≤8字",
  "subtitle": "一句话简介",
  "hashtags": ["#石头禅修", "#治愈系绘本", "#禅意生活", "#每天一个故事", "#自我成长"],
  "pages": [
    {{
      "text": "第一页的故事文字，15-40字",
      "prompt": "{STONE_CHARACTER} on a mountain peak surrounded by clouds at sunrise, golden light, distant mountains visible through mist"
    }},
    ...
  ]
}}"""


def render_stone_cards(
    story: dict,
    output_dir: str = "docs/xhs",
    category: str = "石头禅修",
) -> list[str]:
    """
    渲染石头绘本卡片。

    Args:
        story: {{"title": "...", "headline": "...", "pages": [{{"text":"...","prompt":"..."}}, ...]}}
        output_dir: 输出根目录
        category: 分类目录名

    Returns:
        PNG 路径列表：[封面, 第1页, 第2页, ...]
    """
    project_root = Path(__file__).resolve().parent.parent
    today = date.today()
    date_dir = project_root / output_dir / today.strftime("%Y-%m-%d") / category
    date_dir.mkdir(parents=True, exist_ok=True)

    pages = story.get("pages", [])
    headline = story.get("headline", "")
    total_pages = len(pages)

    if total_pages == 0:
        logger.error("故事没有页面内容")
        return []

    logger.info(f"🪨 渲染石头绘本: {total_pages} 页 + 封面")

    # ── 获取图片 ──
    from modules.stone_image import generate_stone_images

    # 构建 prompt 列表
    prompts = []
    for i, page in enumerate(pages):
        prompts.append({
            "index": i,
            "prompt": page.get("prompt", ""),
            "text": page.get("text", ""),
        })

    import random
    story_seed = random.randint(1, 4294967295)
    img_map = generate_stone_images(prompts, story_seed=story_seed)
    logger.info(f"   获取 {len(img_map)}/{total_pages} 张图片")

    rendered: list[str] = []

    # ── 封面 ──
    cover_img = img_map.get(0, "")
    cover_page = {"title": story.get("title", "石头的禅修"), "subtitle": story.get("subtitle", "")}
    cover_html = _build_cover_html(cover_page, cover_img, today, total_pages, headline)
    cover_path = date_dir / "01_cover.png"
    try:
        render_html_to_png(cover_html, str(cover_path))
        rendered.append(str(cover_path.resolve()))
        logger.info(f"   封面: {cover_path.name}")
    except Exception as e:
        logger.error(f"   封面失败: {e}")

    # ── 故事页 ──
    for i, page in enumerate(pages):
        idx = i + 2
        name = f"{idx:02d}_page_{i+1:02d}.png"
        path = date_dir / name
        page_img = img_map.get(i, "")
        try:
            html = _build_story_html(page, page_img, i + 1, total_pages)
            render_html_to_png(html, str(path))
            rendered.append(str(path.resolve()))
            logger.info(f"   [{i+1}/{total_pages}] {page.get('text','')[:30]}...")
        except Exception as e:
            logger.error(f"   [{i+1}] 失败: {e}")

    # ── manifest ──
    manifest = {
        "date": today.strftime("%Y-%m-%d"),
        "title": story.get("title", "石头的禅修"),
        "headline": headline,
        "category": category,
        "page_count": total_pages,
        "cards": [str(Path(p).relative_to(project_root)).replace("\\", "/") for p in rendered],
        "hashtags": story.get("hashtags", []),
        "story_text": [p.get("text", "") for p in pages],
    }
    mp = date_dir / "manifest.json"
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"📋 manifest → {mp}")

    logger.info(f"🪨 完成！{len(rendered)} 张绘本卡片")
    return rendered
