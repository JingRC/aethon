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
    """构建石头禅修绘本故事 LLM prompt（v2：强化叙事张力）。"""
    themes = [
        "等待的意义", "放下的智慧", "孤独是一种礼物", "慢下来的力量",
        "不争的哲学", "接受不完美", "安静的勇气", "时间的答案",
        "柔软的力量", "存在本身就是价值", "风雨都是过客", "扎根与生长",
    ]
    import random
    theme = random.choice(themes)

    return f"""你是一位绘本作家，用石头为主角创作一个让人「忍不住翻到最后一页」的故事。

## 角色设定

主角是一块圆润的河石，有圆圆的眼睛和温柔的笑容，小短手小短脚，可爱又安静。
它坐在山顶上很久很久了。它不怎么说话，但它看过太多太多。
它的存在，就是对这个世界最好的回答。

## 故事主题：{theme}

## 创作铁律（最重要！）

**每一页都要让人想翻到下一页。** 怎么做到：
- 开头（前2-3页）：设一个钩子——石头看见了什么奇怪的事？遇到了谁？发生了什么变化？
- 中段（4-9页）：递进展开——不要平铺直叙。来点意外、来点幽默、来点心酸。让读者觉得"啊原来是这样"
- 结尾（最后2-3页）：情感升华——不要总结道理，而是让读者自己体会到"啊……"的一声叹息或微笑
- **不要说教！** 石头不讲课。它只是在那里，看着，经历着。读者自己会悟到。

### 示例节奏（{max_pages} 页参考）
```
第1页：设钩子。"那天，一只从没见过的鸟落在了石头身上。"
第2页：推进。"鸟的翅膀受伤了。它飞不起来了。"
第3页：意外。"石头什么也没说。它只是让自己变得很暖很暖。"
...中段层层递进...
倒数第2页：升华。"鸟飞走的那天，石头第一次感到了风的存在。"
最后一页：留白。"石头笑了笑。它又变回了那块石头。只是心里多了一片羽毛。"
```

### 文字要求
- 每页 15-35 字，像绘本一样精炼
- 使用具象画面语言（"鸟的翅膀受伤了"），而不是抽象道理（"生活中总有挫折"）
- 偶尔来点小幽默或小反转
- 文风：宫西达也的温柔 + 几米的小忧伤 + 一点点朱德庸的俏皮

### 每页的图像描述（image_prompt）
- 英文撰写，以 "{STONE_CHARACTER}" 开头
- 然后描述场景，强调光线、氛围、情感基调
- 不同页面间变化：时间（清晨→正午→黄昏→夜晚）、季节（春夏秋冬）、天气（晴→雨→雪→风→雾）、镜头（远景→近景→特写）
- 每个场景要有故事感，而不仅仅是"石头在那里"

### 封面
- headline：≤8字的封面大字，要有爆款吸引力
- title：完整标题
- subtitle：一句话简介，制造好奇

## 返回 JSON（只返回 JSON，不要代码块）

{{
  "title": "石头的故事 · XXX",
  "headline": "封面大字 ≤8字",
  "subtitle": "好奇钩子描述",
  "hashtags": ["#石头禅修", "#治愈系绘本", "#禅意生活", "#每天一个故事"],
  "pages": [
    {{
      "text": "第一页文字，15-35字",
      "prompt": "{STONE_CHARACTER} on a mountain peak at sunrise, a wounded bird landing on its head, dramatic golden light, clouds below, emotional atmosphere"
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
