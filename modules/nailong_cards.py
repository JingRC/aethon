"""
奶龙名画 — 世界名画恶搞卡片

每天 10 张：AI 把奶龙植入世界名画，反差萌爆款。
复用 stone_image 生图 + xhs_renderer 渲染。
"""

import json
import logging
import random
from datetime import date
from pathlib import Path

from modules.xhs_renderer import render_html_to_png

logger = logging.getLogger(__name__)

CARD_W = 1080
CARD_H = 1440

# ── 名画库 ──
PAINTINGS = [
    {"title": "蒙娜丽莎", "artist": "达芬奇", "year": "1503", "parody": "奶龙丽莎的微笑",
     "prompt_en": "Mona Lisa painting by Leonardo da Vinci, but replace Mona Lisa with Nailong the cute fat yellow cartoon dragon, same pose same composition same mysterious smile, renaissance oil painting style, parody"},
    {"title": "呐喊", "artist": "蒙克", "year": "1893", "parody": "奶龙の呐喊",
     "prompt_en": "The Scream painting by Edvard Munch, but replace the screaming figure with Nailong the cute fat yellow cartoon dragon screaming, same bridge background same wavy sky, expressionist style, funny parody"},
    {"title": "戴珍珠耳环的少女", "artist": "维米尔", "year": "1665", "parody": "戴珍珠耳环的奶龙",
     "prompt_en": "Girl with a Pearl Earring painting by Vermeer, but replace the girl with Nailong the cute fat yellow cartoon dragon wearing the same pearl earring and headscarf, same dark background same lighting, Dutch golden age style, parody"},
    {"title": "星空", "artist": "梵高", "year": "1889", "parody": "奶龙星月夜",
     "prompt_en": "Starry Night painting by Van Gogh, but insert Nailong the cute fat yellow cartoon dragon floating in the swirling night sky among the stars, same brushstrokes same color palette, post-impressionist style, parody"},
    {"title": "最后的晚餐", "artist": "达芬奇", "year": "1498", "parody": "最后的夜宵",
     "prompt_en": "The Last Supper painting by Leonardo da Vinci, but replace Jesus with Nailong the cute fat yellow cartoon dragon, all disciples also replaced with various cute cartoon dragons, same composition same table setting, renaissance fresco style, funny parody"},
    {"title": "创造亚当", "artist": "米开朗基罗", "year": "1512", "parody": "创造奶龙",
     "prompt_en": "The Creation of Adam fresco by Michelangelo, but replace Adam with Nailong the cute fat yellow cartoon dragon reaching out to touch God's finger, same pose same composition, sistine chapel ceiling style, parody"},
    {"title": "维纳斯的诞生", "artist": "波提切利", "year": "1485", "parody": "奶纳斯的诞生",
     "prompt_en": "The Birth of Venus painting by Botticelli, but replace Venus with Nailong the cute fat yellow cartoon dragon standing on the giant shell, same flowing hair same sea background, renaissance tempera style, parody"},
    {"title": "清明上河图", "artist": "张择端", "year": "1085", "parody": "奶龙上河图",
     "prompt_en": "Along the River During Qingming Festival Chinese scroll painting, but insert Nailong the cute fat yellow cartoon dragon walking among the ancient Chinese crowd on the bridge, same ink wash style same detailed cityscape, Song dynasty painting style, parody"},
    {"title": "神奈川冲浪里", "artist": "葛饰北斋", "year": "1831", "parody": "奶龙冲浪里",
     "prompt_en": "The Great Wave off Kanagawa woodblock print by Hokusai, but add Nailong the cute fat yellow cartoon dragon surfing on the giant wave, same Mount Fuji background same blue color scheme, ukiyo-e Japanese woodblock style, parody"},
    {"title": "倒牛奶的女仆", "artist": "维米尔", "year": "1658", "parody": "倒奶茶的奶龙",
     "prompt_en": "The Milkmaid painting by Vermeer, but replace the maid with Nailong the cute fat yellow cartoon dragon pouring milk, same kitchen setting same window light, Dutch golden age style, parody"},
    {"title": "夜巡", "artist": "伦勃朗", "year": "1642", "parody": "奶龙夜巡队",
     "prompt_en": "The Night Watch painting by Rembrandt, but replace the militia captain and all guards with Nailong the cute fat yellow cartoon dragon and his dragon friends, same dramatic lighting same composition, baroque style, parody"},
    {"title": "自由引导人民", "artist": "德拉克罗瓦", "year": "1830", "parody": "奶龙引导人民",
     "prompt_en": "Liberty Leading the People painting by Delacroix, but replace Liberty with Nailong the cute fat yellow cartoon dragon holding the flag, same battlefield setting same dramatic pose, romanticism style, parody"},
    {"title": "记忆的永恒", "artist": "达利", "year": "1931", "parody": "奶龙的永恒",
     "prompt_en": "The Persistence of Memory surrealist painting by Dali, but add Nailong the cute fat yellow cartoon dragon lying on the melting clocks, same desert landscape same surreal atmosphere, parody"},
    {"title": "向日葵", "artist": "梵高", "year": "1888", "parody": "奶龙向日葵",
     "prompt_en": "Sunflowers painting by Van Gogh, but replace the sunflowers with Nailong the cute fat yellow cartoon dragon heads in a vase, same yellow color palette same impasto brushwork, post-impressionist style, parody"},
    {"title": "马拉之死", "artist": "大卫", "year": "1793", "parody": "奶龙之躺",
     "prompt_en": "The Death of Marat painting by Jacques-Louis David, but replace Marat with Nailong the cute fat yellow cartoon dragon lying in the bathtub holding a phone, same composition same dramatic lighting, neoclassical style, funny parody"},
]


# ═══════════════════════════════════════════════════════════
# 卡片 HTML 构建
# ═══════════════════════════════════════════════════════════

def _build_card_html(p: dict, img_path: str, idx: int, total: int) -> str:
    """构建单张奶龙名画卡片的 HTML。"""
    parody_title = p.get("parody", "")
    original = f"原作：{p.get('artist','')}《{p.get('title','')}》{p.get('year','')}"
    img_bg = ""
    if img_path:
        img_uri = Path(img_path).resolve().as_uri()
        img_bg = (
            f'<div style="position:absolute;inset:0;'
            f'background:url({img_uri}) center/cover no-repeat;'
            f'z-index:0;"></div>'
        )

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}

html, body {{
  width:{CARD_W}px; height:{CARD_H}px; overflow:hidden;
  font-family:'Microsoft YaHei','PingFang SC','SimHei',sans-serif;
  background:#1a150e; position:relative;
}}

.info-bar {{
  position:absolute; bottom:0; left:0; right:0; z-index:3;
  background:linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.75) 40%, rgba(0,0,0,0.9) 100%);
  padding:50px 60px 40px 60px;
}}

.parody-title {{
  font-size:56px; font-weight:900; color:#ffe066;
  letter-spacing:4px; line-height:1.2;
  text-shadow:0 2px 12px rgba(0,0,0,0.6);
}}

.original-info {{
  font-size:24px; font-weight:400; color:rgba(255,255,255,0.65);
  letter-spacing:2px; margin-top:10px;
}}

.badge {{
  position:absolute; top:24px; right:24px; z-index:4;
  background:rgba(0,0,0,0.6); color:#ffe066;
  font-size:22px; padding:6px 16px; border-radius:20px;
  font-weight:700; letter-spacing:2px;
}}

.series-tag {{
  position:absolute; top:24px; left:24px; z-index:4;
  font-size:24px; color:rgba(255,255,255,0.7);
  letter-spacing:4px; font-weight:700;
  text-shadow:0 1px 4px rgba(0,0,0,0.5);
}}
</style></head><body>
{img_bg}
<div class="series-tag">🐉 奶龙名画</div>
<div class="badge">{idx}/{total}</div>
<div class="info-bar">
  <div class="parody-title">{parody_title}</div>
  <div class="original-info">{original}</div>
</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def render_nailong_cards(
    output_dir: str = "docs/xhs",
    category: str = "奶龙名画",
    count: int = 10,
) -> list[str]:
    """渲染奶龙名画恶搞卡片。每天随机选 10 幅名画。"""
    project_root = Path(__file__).resolve().parent.parent
    today = date.today()
    date_dir = project_root / output_dir / today.strftime("%Y-%m-%d") / category
    date_dir.mkdir(parents=True, exist_ok=True)

    # 随机选画，但用日期做种子保证同一天结果一致
    rng = random.Random(today.toordinal())
    selected = rng.sample(PAINTINGS, min(count, len(PAINTINGS)))
    total = len(selected)

    logger.info(f"🐉 奶龙名画: {total} 张")

    # ── 生图 ──
    from modules.stone_image import generate_stone_images

    prompts = [{"index": i, "prompt": s["prompt_en"], "text": s["parody"]}
               for i, s in enumerate(selected)]

    img_map = generate_stone_images(prompts, story_seed=today.toordinal())
    logger.info(f"   获取 {len(img_map)}/{total} 张图")

    rendered: list[str] = []

    for i, p in enumerate(selected):
        name = f"{i+1:02d}_{p['parody']}.png"
        path = date_dir / name
        try:
            img_path = img_map.get(i, "")
            html = _build_card_html(p, img_path, i + 1, total)
            render_html_to_png(html, str(path))
            rendered.append(str(path.resolve()))
            logger.info(f"   [{i+1}/{total}] {p['parody']}")
        except Exception as e:
            logger.error(f"   [{i+1}] 失败: {e}")

    # ── manifest ──
    manifest = {
        "date": today.strftime("%Y-%m-%d"),
        "category": category,
        "count": total,
        "cards": [str(Path(r).relative_to(project_root)).replace("\\", "/") for r in rendered],
        "paintings": [{"parody": s["parody"], "original": f"{s['artist']}《{s['title']}》{s['year']}"}
                      for s in selected],
    }
    mp = date_dir / "manifest.json"
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"🐉 完成! {total} 张 → {date_dir}")

    return rendered
