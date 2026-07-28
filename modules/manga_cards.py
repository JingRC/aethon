"""
小道士下山记 — 漫画卡片渲染器

每章最多 17 页（含封面），每页可变格数 1-5 格。
AI 生图 + CSS 漫画排版 + 中文对话框。
"""

import json
import logging
from datetime import date
from pathlib import Path

from modules.xhs_renderer import render_html_to_png

logger = logging.getLogger(__name__)

CARD_W = 1080
CARD_H = 1440

# 漫画配色
MC = {
    "bg": "#fafaf8",
    "panel_border": "#2a2a2a",
    "bubble_bg": "#ffffff",
    "bubble_border": "#333333",
    "text_dark": "#1a1a1a",
    "narration_bg": "rgba(0,0,0,0.72)",
    "sfx_color": "#e63946",
    "page_num": "#888888",
}

# ── 角色描述（所有生图 prompt 统一加前缀） ──
MANGA_CHARACTER = (
    "a cute young Taoist monk boy with big expressive eyes, round face, "
    "wearing simple grey Taoist robe and cloth shoes, carrying a small cloth bag, "
    "Studio Ghibli anime style, soft cel shading, clean linework, "
    "warm lighting, kawaii character design, consistent character appearance"
)


# ═══════════════════════════════════════════════════════════
# 对话框组件
# ═══════════════════════════════════════════════════════════

def _speech_bubble(text: str, side: str = "left", style: str = "normal") -> str:
    """漫画对话气泡——绝对定位浮在画面上。"""
    if not text:
        return ""

    if style == "narration":
        return (
            '<div class="narration-box">'
            f'<div class="narration-text">{text}</div>'
            '</div>'
        )

    if style == "shout":
        bkg = "rgba(255,245,245,0.93)"
        bdr = "3px solid #e63946"
        fsz = "30px"
    elif style == "think":
        bkg = "rgba(250,250,250,0.90)"
        bdr = "2px dashed #999"
        fsz = "26px"
    else:
        bkg = "rgba(255,255,255,0.92)"
        bdr = "2px solid #333"
        fsz = "28px"

    al = "right:6px;" if side == "right" else "left:6px;"
    return (
        f'<div style="position:absolute;bottom:6px;{al}max-width:88%;'
        f'padding:8px 12px;{bdr}border-radius:6px;background:{bkg};'
        f'font-size:{fsz};font-weight:700;color:#1a1a1a;line-height:1.4;'
        f'z-index:3;box-shadow:0 1px 3px rgba(0,0,0,0.12);">{text}</div>'
    )


def _sfx(text: str) -> str:
    """拟声词——居中浮在画面上。"""
    return (
        f'<div class="sfx-overlay" style="font-size:56px;font-weight:900;'
        f'color:{MC["sfx_color"]};letter-spacing:4px;opacity:0.85;'
        f'transform:translate(-50%,-50%) rotate(-8deg);'
        f'text-shadow:2px 2px 0 rgba(0,0,0,0.15);">{text}</div>'
    )


# ═══════════════════════════════════════════════════════════
# 布局样式 CSS
# ═══════════════════════════════════════════════════════════

LAYOUT_CSS = {
    "splash": """
        .panels { display:flex; flex-direction:column; height:100%; }
        .panel-img { flex:1; object-fit:cover; width:100%; }
    """,
    "half": """
        .panels { display:grid; grid-template-columns:1fr 1fr; gap:8px; height:100%; }
        .panel-img { width:100%; height:100%; object-fit:cover; }
    """,
    "trio": """
        .panels { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; height:100%; }
        .panel-img { width:100%; height:100%; object-fit:cover; }
    """,
    "grid4": """
        .panels { display:grid; grid-template:1fr 1fr / 1fr 1fr; gap:6px; height:100%; }
        .panel-img { width:100%; height:100%; object-fit:cover; }
    """,
    "cinema": """
        .panels { display:grid; grid-template-rows:2.5fr 1fr; gap:6px; height:100%; }
        .panel-main { grid-column:1/-1; }
        .panel-img { width:100%; height:100%; object-fit:cover; }
        .sub-panels { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; }
    """,
    "stack": """
        .panels { display:grid; grid-template:1fr 1fr / 2fr 1fr; gap:6px; height:100%; }
        .panel-img { width:100%; height:100%; object-fit:cover; }
    """,
    "grid5": """
        .panels { display:grid; grid-template:1fr 1fr / 1fr 1fr 1fr; gap:6px; height:100%; }
        .panel-img { width:100%; height:100%; object-fit:cover; }
        .panel-top { grid-column:1/-1; }
    """,
}


# ═══════════════════════════════════════════════════════════
# 单页构建
# ═══════════════════════════════════════════════════════════

def _build_page_html(
    page: dict,
    img_map: dict[int, str],
    page_num: int,
    total: int,
    panel_offset: int = 0,
    series_name: str = "山海经外卖",
) -> str:
    """构建一页漫画 HTML。"""
    layout = page.get("layout", "grid4")
    panels = page.get("panels", [])

    if not panels:
        return ""

    # 构建面板 HTML
    panel_html_parts = []
    for i, panel in enumerate(panels):
        global_idx = panel_offset + i
        img_path = img_map.get(global_idx, "")
        img_tag = ""
        if img_path:
            img_uri = Path(img_path).resolve().as_uri()
            img_tag = (
                f'<img class="panel-img" src="{img_uri}" '
                f'style="border:2px solid {MC["panel_border"]}; border-radius:3px;" />'
            )
        else:
            # 占位
            img_tag = (
                f'<div class="panel-img" style="background:{MC["bg"]}; '
                f'border:2px solid {MC["panel_border"]}20; border-radius:3px; '
                f'display:flex; align-items:center; justify-content:center; '
                f'color:#ccc; font-size:24px;">🖼</div>'
            )

        dialogue = panel.get("dialogue", "")
        narration = panel.get("narration", "")
        sfx_text = panel.get("sfx", "")
        speaker = panel.get("speaker", "left")

        # 面板容器
        panel_css_class = f"panel-{i+1}"
        inner = img_tag

        # 对话框叠加在图片上
        if dialogue:
            inner += _speech_bubble(dialogue, side=speaker, style="normal")
        if narration:
            inner += _speech_bubble(narration, style="narration")
        if sfx_text:
            inner += _sfx(sfx_text)

        panel_html_parts.append(
            f'<div class="{panel_css_class}" style="position:relative;">{inner}</div>'
        )

    panels_html = "\n".join(panel_html_parts)

    # Cinema 布局特殊处理
    if layout == "cinema" and len(panels) >= 2:
        panels_html = (
            f'<div class="panel-main" style="position:relative;">{panel_html_parts[0]}</div>'
            f'<div class="sub-panels">{"".join(panel_html_parts[1:])}</div>'
        )

    page_label = f"{page_num} / {total}" if page_num > 0 else ""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700;900&family=Ma+Shan+Zheng&display=swap');

* {{ margin:0; padding:0; box-sizing:border-box; }}

html, body {{
  width:{CARD_W}px; height:{CARD_H}px; overflow:hidden;
  font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;
  background:#fafaf8; position:relative;
}}

.page-container {{
  width:100%; height:100%; padding:16px;
  display:flex; flex-direction:column;
}}

{LAYOUT_CSS.get(layout, LAYOUT_CSS["grid4"])}

.panels {{ flex:1; }}

.narration-box {{
  position:absolute; top:0; left:0; right:0;
  background:{MC["narration_bg"]}; padding:14px 24px; z-index:5;
}}
.narration-text {{
  font-size:30px; color:#fff; letter-spacing:2px;
  font-weight:400; text-align:center;
}}

.speech-bubble {{
  position:absolute; bottom:8px; left:8px; right:8px;
  background:rgba(255,255,255,0.92); border:2px solid #333;
  border-radius:6px; padding:6px 10px; z-index:3;
  font-size:26px; font-weight:700; color:#1a1a1a; line-height:1.4;
}}
.sfx-overlay {{
  position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
  z-index:4; pointer-events:none;
}}
.narration-box {{
  position:absolute; top:0; left:0; right:0;
  background:{MC["narration_bg"]}; padding:10px 20px; z-index:5;
}}
.narration-text {{
  font-size:26px; color:#fff; letter-spacing:2px; font-weight:400; text-align:center;
}}
.page-footer {{
  display:flex; justify-content:space-between; align-items:center;
  padding:6px 8px 0 8px; font-size:20px; color:{MC["page_num"]};
}}
.chapter-title {{ font-weight:700; }}
.page-num {{ font-weight:400; }}
</style></head><body>
<div class="page-container">
  <div class="panels">{panels_html}</div>
  <div class="page-footer">
    <div class="chapter-title">{series_name}</div>
    <div class="page-num">{page_label}</div>
  </div>
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════
# 封面构建
# ═══════════════════════════════════════════════════════════

def _build_manga_cover_html(
    chapter_info: dict,
    img_path: str,
    today: date,
    chapter_num: int,
    total_pages: int,
) -> str:
    """构建漫画封面。"""
    title = chapter_info.get("title", f"第{chapter_num}章")
    headline = chapter_info.get("headline", "小道士下山记")
    subtitle = chapter_info.get("subtitle", "")

    img_bg = ""
    if img_path:
        img_uri = Path(img_path).resolve().as_uri()
        img_bg = (
            f'<div style="position:absolute;inset:0;'
            f'background:url({img_uri}) center/cover no-repeat;'
            f'z-index:0;"></div>'
        )

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
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700;900&family=Ma+Shan+Zheng&display=swap');

* {{ margin:0; padding:0; box-sizing:border-box; }}

html, body {{
  width:{CARD_W}px; height:{CARD_H}px; overflow:hidden;
  font-family:'Noto Serif SC','STSong','KaiTi',serif;
  background:#1a150e; position:relative;
}}

.cover-overlay {{
  position:absolute; inset:0; z-index:1;
  background:linear-gradient(180deg,
    rgba(0,0,0,0.55) 0%,
    rgba(0,0,0,0.2) 40%,
    rgba(0,0,0,0.5) 85%,
    rgba(0,0,0,0.8) 100%);
}}

.cover-content {{
  position:relative; z-index:3;
  display:flex; flex-direction:column;
  align-items:center; justify-content:flex-end;
  height:100%; text-align:center; padding:60px 50px 80px 50px;
}}

.series-name {{
  font-size:28px; font-weight:700; color:rgba(255,255,255,0.6);
  letter-spacing:8px; margin-bottom:32px;
  text-shadow:0 2px 6px rgba(0,0,0,0.5);
}}

.cover-title {{
  font-family:'Ma Shan Zheng','KaiTi',cursive;
  font-size:96px; font-weight:900; color:#fdf6ee;
  letter-spacing:6px; line-height:1.2;
  text-shadow:0 4px 24px rgba(0,0,0,0.7);
}}

.cover-subtitle {{
  font-size:34px; font-weight:400; color:rgba(255,255,255,0.8);
  letter-spacing:4px; margin-top:14px;
  text-shadow:0 2px 8px rgba(0,0,0,0.5);
}}

.cover-line {{ width:100px; height:2px;
  background:linear-gradient(to right,transparent,rgba(255,255,255,0.5),transparent);
  margin:24px auto; }}

.cover-meta {{
  font-size:22px; font-weight:400; color:rgba(255,255,255,0.5);
  letter-spacing:3px; margin-top:8px;
}}

.cover-date {{
  position:absolute; top:40px; width:100%; text-align:center; z-index:3;
  font-size:24px; font-weight:300; color:rgba(255,255,255,0.55);
  letter-spacing:4px; text-shadow:0 1px 4px rgba(0,0,0,0.5);
}}
</style></head><body>
{img_bg}
<div class="cover-overlay"></div>
<div class="cover-date">{cn_date}</div>
<div class="cover-content">
  <div class="series-name">小 道 士 下 山 记</div>
  <div class="cover-title">{headline}</div>
  <div class="cover-subtitle">{subtitle}</div>
  <div class="cover-line"></div>
  <div class="cover-meta">第{chapter_num}章 · {total_pages}页</div>
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════
# LLM Prompt 构建
# ═══════════════════════════════════════════════════════════

def build_manga_chapter_prompt(chapter_num: int, max_pages: int = 16) -> str:
    """构建小道士下山记章节 LLM prompt。"""
    return f"""你是一位漫画编剧，为连载漫画《小道士下山记》创作第{chapter_num}章。

## 世界观

深山古观里住着一位老师父和一个小道士。小道士从小在山上长大，单纯、善良、对山下的世界一无所知。第1章中，师父终于准许他下山"看看人间"。每一章遇到一个故事、一个人、一个道理。

## 角色设定

### 小道士（主角）
- 15岁，圆圆的脸，大眼睛，表情丰富
- 穿灰色道袍，背着小布包，布鞋
- 性格：好奇、单纯、善良、有点笨拙、但很勇敢
- 说话方式：天真直接，偶尔冒出师父教的道理

### 可出场角色（每章选1-2个）
- 山下村民、流浪艺人、茶摊老板、赶路的书生
- 其他道士、山中精怪（可爱的，不恐怖）
- 受伤的小动物、迷路的小孩

## 创作要求

### 章节结构（{max_pages} 页正文 + 1 封面）
- 第1页：开篇大画（splash 布局），建立场景和悬念
- 第2-{max_pages-2}页：剧情展开，使用多种布局
- 最后1-2页：情感升华或悬念（让人期待下一章）

### 布局选择指南
| 布局 | 格数 | 何时使用 |
|------|------|----------|
| splash | 1 | 章节开篇、重要场景、情绪高潮 |
| half | 2 | 两人对话、对比、前后呼应 |
| trio | 3 | 连续动作、时间推移、三连拍 |
| grid4 | 4 | 标准叙事推进、日常对话 |
| cinema | 4 | 大场面+细节、先全景再特写 |
| stack | 4 | 主画面+配角反应 |
| grid5 | 5 | 快节奏、动作场面、忙碌感 |

### 对话要求
- 全中文，口语化，有角色个性
- 小道士说话天真但不说教
- 可以加拟声词（sfx 字段）：啪！/ 轰—— / 哗啦 / 吱呀 / 咕噜噜
- narration 用于旁白（顶部的叙事文字条）
- speaker 用 "left" 或 "right"

### 每格图像描述（image_prompt）
- 英文撰写，以 "{MANGA_CHARACTER}" 开头
- 然后描述该格的场景、动作、角色表情、镜头角度
- 不同格之间要有景别变化（远景→中景→特写）

## 第{chapter_num}章创作

### 前期回顾（如果不是第1章）
第1章：师父让小道士下山。小道士第一次踏入山下的世界。

### 本章任务
{"创作第1章：小道士告别师父、走出山门、第一次见到山下世界的故事。这章是系列的开篇，要有惊艳的第一印象。" if chapter_num == 1 else f"承接上一章，继续小道士的旅程。本章要有新的遭遇、新的感悟。可以引入新角色。"}

## 返回 JSON（只返回 JSON）

{{
  "title": "第{chapter_num}章 · XXX（8-15字）",
  "headline": "封面大字 4-8字",
  "subtitle": "一句话简介",
  "hashtags": ["#小道士下山记", "#原创漫画", "#治愈系", "#国风动漫"],
  "pages": [
    {{
      "layout": "splash",
      "panels": [
        {{
          "image_prompt": "{MANGA_CHARACTER} standing at an ancient mountain temple gate, looking down at the vast world below, morning mist, golden sunrise, emotional moment, wide shot cinematic",
          "narration": "旁白文字",
          "dialogue": null,
          "sfx": null,
          "speaker": "left"
        }}
      ]
    }},
    {{
      "layout": "grid4",
      "panels": [
        {{
          "image_prompt": "{MANGA_CHARACTER} packing his small cloth bag, close-up of hands folding a robe, warm interior of temple, soft candlelight",
          "dialogue": "师父，山下有什么？",
          "narration": null,
          "sfx": null,
          "speaker": "left"
        }},
        ...
      ]
    }},
    ...
  ]
}}

注意：
- 格数 = panels 数组长度，必须和 layout 匹配
- 对话分配到具体 panel 中，不要把所有对话堆在一个 panel
- splash 布局只有 1 个 panel，cinema 和 stack 有 4 个，grid5 有 5 个
- 总共输出 {max_pages} 个页面对象
"""

def render_manga_chapter(
    chapter: dict,
    chapter_num: int = 1,
    output_dir: str = "docs/xhs",
    category: str = "小道士下山",
) -> list[str]:
    """
    渲染一整个漫画章节。

    Args:
        chapter: {{"title","headline","subtitle","pages":[...]}}
        chapter_num: 章节号
        output_dir: 输出根目录
        category: 分类目录名

    Returns:
        PNG 路径列表 [封面, 第1页, ...]
    """
    project_root = Path(__file__).resolve().parent.parent
    today = date.today()
    date_dir = project_root / output_dir / today.strftime("%Y-%m-%d") / category
    date_dir.mkdir(parents=True, exist_ok=True)

    pages = chapter.get("pages", [])
    total_pages = len(pages)

    if total_pages == 0:
        logger.error("漫画没有页面内容")
        return []

    logger.info(f"📘 渲染漫画: 第{chapter_num}章 ({total_pages} 页)")

    # ── 收集所有面板的生图 prompt ──
    from modules.stone_image import generate_stone_images

    # 强制追加漫画风格后缀，保证全章视觉统一
    STYLE_SUFFIX = (
        ", professional manga panel, Japanese comic art style, "
        "clean black linework with screentones, cel-shaded anime coloring, "
        "sharp outlines, dramatic lighting, comic panel composition, "
        "flat color areas with halftone shading, 1990s manga aesthetic, "
        "consistent character design, same art style across all panels"
    )

    prompts = []
    panel_idx = 0
    for page in pages:
        for panel in page.get("panels", []):
            raw_prompt = panel.get("image_prompt", "").strip()
            if raw_prompt:
                raw_prompt = raw_prompt + STYLE_SUFFIX
            prompts.append({
                "index": panel_idx,
                "prompt": raw_prompt,
                "text": panel.get("dialogue", "") or panel.get("narration", ""),
            })
            panel_idx += 1

    total_panels = len(prompts)
    logger.info(f"   共 {total_panels} 个漫画格，开始生图...")

    import random
    story_seed = random.randint(1, 4294967295)
    img_map = generate_stone_images(prompts, story_seed=story_seed)
    logger.info(f"   获取 {len(img_map)}/{total_panels} 张格图")

    rendered: list[str] = []

    # ── 封面 ──
    cover_img = img_map.get(0, "")
    cover_html = _build_manga_cover_html(
        chapter, cover_img, today, chapter_num, total_pages
    )
    cover_path = date_dir / "01_cover.png"
    try:
        render_html_to_png(cover_html, str(cover_path))
        rendered.append(str(cover_path.resolve()))
        logger.info(f"   封面: {cover_path.name}")
    except Exception as e:
        logger.error(f"   封面失败: {e}")

    # ── 漫画页 ──
    running_panel_offset = 0
    for i, page in enumerate(pages):
        idx = i + 2
        name = f"{idx:02d}_page_{i+1:02d}.png"
        path = date_dir / name
        try:
            html = _build_page_html(
                page, img_map, i + 1, total_pages,
                panel_offset=running_panel_offset,
                series_name=category,
            )
            running_panel_offset += len(page.get("panels", []))
            render_html_to_png(html, str(path))
            rendered.append(str(path.resolve()))
            logger.info(f"   [{i+1}/{total_pages}] {page.get('layout','grid4')} · "
                       f"{len(page.get('panels',[]))} 格")
        except Exception as e:
            logger.error(f"   第{i+1}页失败: {e}")

    # ── manifest ──
    manifest = {
        "date": today.strftime("%Y-%m-%d"),
        "series": "小道士下山记",
        "chapter": chapter_num,
        "title": chapter.get("title", ""),
        "headline": chapter.get("headline", ""),
        "category": category,
        "page_count": total_pages,
        "panel_count": total_panels,
        "cards": [str(Path(p).relative_to(project_root)).replace("\\", "/") for p in rendered],
        "hashtags": chapter.get("hashtags", []),
    }
    mp = date_dir / "manifest.json"
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"📋 manifest → {mp}")

    logger.info(f"📘 完成！第{chapter_num}章 {len(rendered)} 张")
    return rendered
