"""
古风历史故事卡片渲染器 v2 — HTML → PNG（Chrome headless）

v2 改进：
- 字号全面提升（标题 64px / 正文 36px）
- 水墨：红日 + 五层山峦 + 飞鸟 + 雾气
- 竹简：暖黄竹色 + 3D 条状渐变 + 编绳
- 宫墙：朱红金框 + 回纹装饰 + 匾额顶栏
- 封面：更华丽的中式排版
"""

import json
import logging
from datetime import date
from pathlib import Path

from modules.xhs_renderer import render_html_to_png

logger = logging.getLogger(__name__)

CARD_W = 1080
CARD_H = 1440

PALETTES: list[dict] = [
    {"name": "rice_paper", "bg": "#f5f0e8", "accent": "#c41e3a", "text": "#3d3226",
     "muted": "#8b775a", "surface": "#ede4d3", "border": "#8b7355",
     "rod": "#9b7653", "gold": "#c4a35a", "ink_light": "#d4cfc5", "ink_dark": "#3d3226"},
    {"name": "celadon",    "bg": "#f0f3e8", "accent": "#2d5a27", "text": "#2d3028",
     "muted": "#6b7a5e", "surface": "#e5ead8", "border": "#5a6b4a",
     "rod": "#6b7a5e", "gold": "#8aaa70", "ink_light": "#d8ddd0", "ink_dark": "#3a4a30"},
    {"name": "ink",        "bg": "#ece8df", "accent": "#1a1a1a", "text": "#2a2520",
     "muted": "#6b6558", "surface": "#e0dbd0", "border": "#4a4538",
     "rod": "#4a4538", "gold": "#8b8068", "ink_light": "#d8d2c8", "ink_dark": "#1f1a15"},
    {"name": "cinnabar",   "bg": "#faf5ee", "accent": "#b22222", "text": "#3d2b1f",
     "muted": "#8b6b5a", "surface": "#f0e6d8", "border": "#8b4513",
     "rod": "#8b4513", "gold": "#c47a3a", "ink_light": "#e8ddd0", "ink_dark": "#4a2010"},
    {"name": "golden",     "bg": "#f8f3e5", "accent": "#b8860b", "text": "#3d3220",
     "muted": "#8b7d5a", "surface": "#efe4cc", "border": "#8b6914",
     "rod": "#8b6914", "gold": "#daa520", "ink_light": "#e8ddc8", "ink_dark": "#4a3810"},
    {"name": "jade",       "bg": "#f2f5f0", "accent": "#4a7c59", "text": "#2d3528",
     "muted": "#6b7d5e", "surface": "#e6ede0", "border": "#5a6b4a",
     "rod": "#5a6b4a", "gold": "#8aaa70", "ink_light": "#dde5d5", "ink_dark": "#2a3a20"},
]


def _rgb(h: str) -> str:
    h = h.lstrip("#")
    return f"{int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)}"


def _pc(p: dict, key: str, alpha: float) -> str:
    """rgba 快捷写法。"""
    return f"rgba({_rgb(p[key])},{alpha})"


def _noise_svg(opacity: float = 0.06) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">'
        f'<filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.55" '
        f'numOctaves="5" stitchTiles="stitch"/></filter>'
        f'<rect width="100%" height="100%" filter="url(#n)" opacity="{opacity}"/></svg>'
    )


def _parchment_bg(p: dict, extra_stains: bool = False) -> str:
    """羊皮纸纹理 background-image 值。"""
    parts = [
        f"linear-gradient(135deg, {p['bg']}, {p['surface']}, {p['bg']})",
        f"repeating-linear-gradient(0deg, transparent, transparent 3px, "
        f"rgba({_rgb(p['muted'])},0.025) 3px, rgba({_rgb(p['muted'])},0.025) 4px)",
        f"radial-gradient(ellipse at 20% 60%, {_pc(p,'border',0.06)} 0%, transparent 50%)",
        f"radial-gradient(ellipse at 80% 30%, {_pc(p,'muted',0.05)} 0%, transparent 40%)",
        f"radial-gradient(ellipse at 50% 85%, {_pc(p,'border',0.04)} 0%, transparent 45%)",
    ]
    if extra_stains:
        parts.append(f"radial-gradient(ellipse at 70% 70%, {_pc(p,'border',0.07)} 0%, transparent 35%)")
        parts.append(f"radial-gradient(ellipse at 10% 20%, {_pc(p,'muted',0.06)} 0%, transparent 30%)")
    return ", ".join(parts)


def _seal(text: str, p: dict, size: int = 80,
          top: str = "auto", right: str = "auto",
          bottom: str = "auto", left: str = "auto",
          extra_style: str = "") -> str:
    return (
        f'<div style="position:absolute;top:{top};right:{right};bottom:{bottom};left:{left};'
        f'width:{size}px;height:{size}px;border:3px solid {p["accent"]};color:{p["accent"]};'
        f'writing-mode:vertical-rl;font-family:KaiTi,STKaiti,serif;'
        f'font-size:{int(size*0.2)}px;font-weight:700;'
        f'display:flex;align-items:center;justify-content:center;'
        f'transform:rotate(-5deg);opacity:0.8;letter-spacing:4px;line-height:1.2;'
        f'padding:8px 0;{extra_style}">{text}</div>'
    )


# ═══════════════════════════════════════════════════════════
# 公共 CSS
# ═══════════════════════════════════════════════════════════

def _base_css(p: dict, layout: int, extra: str = "") -> str:
    bg = _parchment_bg(p, extra_stains=(layout == 0))
    noise = _noise_svg(0.06)
    return f"""
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@300;400;700;900&family=Ma+Shan+Zheng&display=swap');

* {{ margin:0; padding:0; box-sizing:border-box; }}

html, body {{
  width:{CARD_W}px; height:{CARD_H}px; overflow:hidden;
  font-family:'Noto Serif SC','STSong','SimSun','KaiTi','PingFang SC',serif;
  background:{bg}; color:{p["text"]}; position:relative;
}}

body::before {{
  content:''; position:absolute; inset:0;
  background:url("data:image/svg+xml,{noise}") center/cover;
  pointer-events:none; z-index:99;
}}

.title {{ font-size:76px; font-weight:900; line-height:1.15; color:{p["text"]}; }}
.meta {{ font-size:30px; font-weight:400; letter-spacing:5px; color:{p["muted"]}; }}
.meta .dynasty {{ color:{p["accent"]}; font-weight:700; }}
.body {{ font-size:42px; font-weight:400; line-height:1.85; color:{p["text"]}; text-align:justify; }}

.wisdom-box {{
  background:{p["surface"]}; border-left:5px solid {p["accent"]};
  padding:18px 24px; margin:16px 0 10px 0;
}}
.wisdom-label {{ font-size:28px; font-weight:700; color:{p["accent"]}; margin-bottom:6px; letter-spacing:3px; }}
.wisdom-text {{ font-size:32px; font-weight:400; line-height:1.7; color:{p["text"]}; }}

.source {{ font-size:28px; font-weight:300; color:{p["muted"]}; font-style:italic; }}
.fun-fact {{ font-size:24px; font-weight:300; color:{p["muted"]}; font-style:italic; margin-top:10px; }}

.dot {{ width:7px; height:7px; background:{p["accent"]}; border-radius:50%;
  display:inline-block; margin:0 12px; opacity:0.5; vertical-align:middle; }}
.divider {{ height:1px; background:linear-gradient(to right,transparent,{p["border"]}44,{p["border"]}88,{p["border"]}44,transparent); margin:16px 0; }}
.badge {{ font-size:26px; font-weight:700; color:{p["accent"]}; opacity:0.65; letter-spacing:4px; }}
.brand {{ font-size:20px; font-weight:300; color:{p["muted"]}99; letter-spacing:3px; }}

{extra}
"""


# ═══════════════════════════════════════════════════════════
# 布局 0：卷轴 Scroll
# ═══════════════════════════════════════════════════════════

def _layout_scroll(f: dict, p: dict, n: int, img: str = "") -> str:
    extra = f"""
.scroll-rod {{ position:absolute; left:30px; right:30px; height:20px;
  background:linear-gradient(to bottom,{p["gold"]},{p["rod"]},{p["gold"]});
  border-radius:10px; box-shadow:0 3px 8px rgba(0,0,0,0.2); z-index:2; }}
.scroll-rod-top {{ top:25px; }}
.scroll-rod-bottom {{ bottom:25px; }}
.scroll-rod::after, .scroll-rod::before {{
  content:''; position:absolute; top:-5px; width:20px; height:30px;
  background:linear-gradient(to bottom,{p["gold"]}aa,{p["gold"]}ee,{p["gold"]}aa);
  border-radius:5px; }}
.scroll-rod::after {{ left:0; }} .scroll-rod::before {{ right:0; }}
.scroll-corner {{ position:absolute; width:40px; height:40px; z-index:3; pointer-events:none; }}
.scroll-corner-tl {{ top:60px; left:55px; border-top:3px solid {p["accent"]}44; border-left:3px solid {p["accent"]}44; }}
.scroll-corner-tr {{ top:60px; right:55px; border-top:3px solid {p["accent"]}44; border-right:3px solid {p["accent"]}44; }}
.scroll-corner-bl {{ bottom:60px; left:55px; border-bottom:3px solid {p["accent"]}44; border-left:3px solid {p["accent"]}44; }}
.scroll-corner-br {{ bottom:60px; right:55px; border-bottom:3px solid {p["accent"]}44; border-right:3px solid {p["accent"]}44; }}
"""
    css = _base_css(p, 0, extra)

    meta = ""
    if f["dynasty"] or f["category"]:
        parts = []
        if f["dynasty"]:
            parts.append(f'<span class="dynasty">{f["dynasty"]}</span>')
        if f["category"]:
            parts.append(f["category"])
        sep = ' <span class="dot"></span> '
        meta = f'<div class="meta" style="text-align:center;">{sep.join(parts)}</div>'
    wisdom = ""
    if f["lesson"]:
        wisdom = f'<div class="wisdom-box"><div class="wisdom-label">📜 启示</div><div class="wisdom-text">{f["lesson"]}</div></div>'

    fun = f'<div class="fun-fact">💡 {f["fun_fact"]}</div>' if f["fun_fact"] else ""
    src = f'<div class="source" style="text-align:center;">—— {f["source"]}</div>' if f["source"] else ""
    img_layer = f'<div style="position:absolute;inset:0;background:url({img}) center/cover;opacity:0.12;filter:sepia(0.25) contrast(0.8);z-index:0;pointer-events:none;"></div>' if img else ""

    seal_html = _seal(f["dynasty"][:2] if f["dynasty"] else "古", p, size=72, top="70px", right="80px")

    img_layer = f'<div style="position:absolute;inset:0;background:url({img}) center/cover;opacity:0.12;filter:sepia(0.3) contrast(0.8);z-index:0;pointer-events:none;"></div>' if img else ""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>{css}
.content {{ position:relative; z-index:2; display:flex; flex-direction:column;
  padding:75px 100px 55px 100px; height:100%; }}
</style></head><body>
{img_layer}
<div class="scroll-rod scroll-rod-top"></div><div class="scroll-rod scroll-rod-bottom"></div>
<div class="scroll-corner scroll-corner-tl"></div><div class="scroll-corner scroll-corner-tr"></div>
<div class="scroll-corner scroll-corner-bl"></div><div class="scroll-corner scroll-corner-br"></div>
{seal_html}<div class="badge" style="position:absolute;top:80px;right:175px;z-index:3;">{n:02d} / 10</div>
<div class="content">
  <div class="title" style="text-align:center;">{f["title"]}</div>
  {meta}<div class="divider" style="margin:24px 0;"></div>
  <div class="body" style="flex:1;">{f["story_zh"]}</div>
  {wisdom}{fun}{src}
  <div style="margin-top:auto;text-align:center;"><div class="brand">Aethon · 历史卡片 · 每日典故</div></div>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════
# 布局 1：水墨 Ink Wash
# ═══════════════════════════════════════════════════════════

def _mountains_svg(p: dict) -> str:
    """五层水墨山峦 + 红日 + 飞鸟。"""
    sun_cx, sun_cy, sun_r = 820, 420, 100
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1440"
style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;">
  <defs>
    <linearGradient id="mist1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="white" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="white" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="mist2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="white" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="white" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <!-- 红日 -->
  <circle cx="{sun_cx}" cy="{sun_cy}" r="{sun_r}" fill="{p["accent"]}" opacity="0.12"/>
  <circle cx="{sun_cx}" cy="{sun_cy}" r="{int(sun_r*0.7)}" fill="{p["accent"]}" opacity="0.08"/>
  <!-- 远山 1 -->
  <path d="M0,1440 L0,600 Q80,530 180,560 Q280,510 380,540 Q500,470 600,520
    Q720,460 820,510 Q920,480 1000,500 Q1060,490 1080,500 L1080,1440Z"
    fill="{p["muted"]}" opacity="0.06"/>
  <!-- 远山 2 -->
  <path d="M0,1440 L0,700 Q150,630 260,660 Q380,600 500,650 Q630,590 750,640
    Q860,610 960,630 Q1020,620 1080,630 L1080,1440Z"
    fill="{p["border"]}" opacity="0.09"/>
  <!-- 中山 3 -->
  <path d="M0,1440 L0,820 Q120,760 240,790 Q360,740 480,780 Q600,720 700,770
    Q820,730 920,760 Q1000,740 1080,750 L1080,1440Z"
    fill="{p["muted"]}" opacity="0.12"/>
  <!-- 中山 4 -->
  <path d="M0,1440 L0,940 Q200,880 320,920 Q460,870 560,910 Q680,860 800,900
    Q920,870 1000,890 Q1050,880 1080,885 L1080,1440Z"
    fill="{p["border"]}" opacity="0.16"/>
  <!-- 近山 5 -->
  <path d="M0,1440 L0,1080 Q180,1020 300,1060 Q440,1000 560,1040 Q700,990 820,1030
    Q940,1000 1040,1015 L1080,1010 L1080,1440Z"
    fill="{p["accent"]}" opacity="0.18"/>
  <!-- 雾气层 1 -->
  <rect x="0" y="600" width="1080" height="300" fill="url(#mist1)"/>
  <!-- 雾气层 2 -->
  <rect x="0" y="850" width="1080" height="250" fill="url(#mist2)"/>
  <!-- 飞鸟 -->
  <g stroke="{p["text"]}" stroke-width="2.5" fill="none" opacity="0.25">
    <path d="M180,300 Q190,290 200,300"/>
    <path d="M210,310 Q218,302 226,310"/>
    <path d="M160,340 Q168,332 176,340"/>
    <path d="M280,250 Q288,242 296,250"/>
  </g>
</svg>"""


def _layout_ink_wash(f: dict, p: dict, n: int, img: str = "") -> str:
    extra = f"""
.title {{ font-size:84px; letter-spacing:4px; text-shadow:2px 2px 0 {p["surface"]}; }}
.body {{ font-size:44px; line-height:1.85; }}
.ink-overlay {{ position:absolute; left:0; bottom:0; width:100%; height:55%;
  background:linear-gradient(to bottom, transparent 0%, {p["bg"]}dd 40%, {p["bg"]} 100%);
  pointer-events:none; z-index:1; }}
"""
    css = _base_css(p, 1, extra)

    meta = ""
    if f["dynasty"] or f["category"]:
        parts = []
        if f["dynasty"]:
            parts.append(f'<span class="dynasty">{f["dynasty"]}</span>')
        if f["category"]:
            parts.append(f["category"])
        sep = ' <span class="dot"></span> '
        meta = f'<div class="meta" style="margin-bottom:8px;">{sep.join(parts)}</div>'

    wisdom = ""
    if f["lesson"]:
        wisdom = (
            f'<div class="wisdom-box" style="background:{_pc(p,"surface",0.55)};'
            f'backdrop-filter:blur(4px);">'
            f'<div class="wisdom-label">📜 启示</div>'
            f'<div class="wisdom-text">{f["lesson"]}</div></div>')

    src = f'<div class="source">—— {f["source"]}</div>' if f["source"] else ""
    seal_html = _seal(f["dynasty"][:2] if f["dynasty"] else "古", p, size=56, top="55px", right="75px")

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>{css}
.content {{ position:relative; z-index:3; display:flex; flex-direction:column;
  padding:55px 75px 50px 75px; height:100%; }}
</style></head><body>
{_mountains_svg(p)}
<div class="ink-overlay"></div>
{seal_html}<div class="badge" style="position:absolute;top:65px;right:150px;z-index:4;">{n:02d} / 10</div>
<div class="content">
  {meta}
  <div class="title">{f["title"]}</div>
  <div class="divider"></div>
  <div class="body" style="flex:1;">{f["story_zh"]}</div>
  {wisdom}{src}
  <div style="margin-top:auto;"><div class="brand">Aethon · 历史卡片</div></div>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════
# 布局 2：竹简 Bamboo Slip
# ═══════════════════════════════════════════════════════════

def _bamboo_strip_css(p: dict) -> str:
    """每根竹片的 3D 渐变 + 编绳。"""
    bamboo_bg = f"#e8d5a3"  # 暖黄竹色
    bamboo_hi = f"#f0e2b8"
    bamboo_lo = f"#d4bd80"
    return f"""
.bamboo-strip {{
  background:linear-gradient(180deg,{bamboo_hi} 0%,{bamboo_bg} 30%,{bamboo_lo} 70%,{bamboo_bg} 100%);
  border-bottom:1px solid rgba(139,105,20,0.2);
  position:relative;
}}
.bamboo-strip::before {{
  content:''; position:absolute; left:0; top:0; bottom:0; width:3px;
  background:linear-gradient(90deg,rgba(255,255,255,0.3),transparent);
}}
.bamboo-strip::after {{
  content:''; position:absolute; right:0; top:0; bottom:0; width:3px;
  background:linear-gradient(270deg,rgba(139,105,20,0.15),transparent);
}}
.binding-string {{
  width:12px; height:12px; background:{p["accent"]}; border-radius:50%;
  position:absolute; left:26px; box-shadow:0 0 4px rgba(0,0,0,0.3);
}}
.binding-string::after {{
  content:''; position:absolute; left:12px; top:4px; width:calc(100vw - 80px); height:2px;
  background:linear-gradient(90deg,{p["accent"]}88,{p["accent"]}44,transparent);
}}
"""


def _layout_bamboo(f: dict, p: dict, n: int, img: str = "") -> str:
    extra = _bamboo_strip_css(p)
    css = _base_css(p, 2, extra)

    # 编绳位置
    rope_positions = [130, 310, 490, 670, 850, 1030, 1210]
    ropes = "".join(f'<div class="binding-string" style="top:{y}px;"></div>' for y in rope_positions)

    meta = ""
    if f["dynasty"] or f["category"]:
        parts = []
        if f["dynasty"]:
            parts.append(f'<span class="dynasty">{f["dynasty"]}</span>')
        if f["category"]:
            parts.append(f["category"])
        sep = ' <span class="dot"></span> '
        meta = f'<div class="meta" style="text-align:center;">{sep.join(parts)}</div>'
    wisdom = ""
    if f["lesson"]:
        wisdom = f'<div class="wisdom-box"><div class="wisdom-label">📜 启示</div><div class="wisdom-text">{f["lesson"]}</div></div>'

    src = f'<div class="source" style="text-align:center;margin-top:6px;">—— {f["source"]}</div>' if f["source"] else ""
    img_layer = f'<div style="position:absolute;inset:0;background:url({img}) center/cover;opacity:0.10;filter:sepia(0.3) contrast(0.8);z-index:0;pointer-events:none;"></div>' if img else ""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>{css}
.content {{ position:relative; z-index:3; display:flex; flex-direction:column;
  padding:55px 70px 35px 85px; height:100%; }}
.title {{ font-size:68px; text-align:center; }}
.body {{ font-size:38px; line-height:2.0; text-align:justify; }}
</style></head><body>
{ropes}
{img_layer}
<div class="badge" style="position:absolute;top:35px;right:60px;z-index:4;font-size:20px;">{n:02d} / 10</div>
<div class="content">
  <div class="title">{f["title"]}</div>
  {meta}<div class="divider" style="margin:16px 0 20px 0;"></div>
  <div class="body" style="flex:1;">{f["story_zh"]}</div>
  {wisdom}{src}
  <div style="text-align:center;margin-top:10px;"><div class="brand">Aethon · 历史卡片</div></div>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════
# 布局 3：宫墙 Palace Wall
# ═══════════════════════════════════════════════════════════

def _layout_palace(f: dict, p: dict, n: int, img: str = "") -> str:
    # 从 cinnabar palette 取朱红色（覆盖 accent）
    wall_red = "#c41e3a"
    wall_gold = "#daa520"

    extra = f"""
.palace-bg {{ position:absolute; inset:0;
  background:linear-gradient(180deg,#fdf6f0 0%,#faf0e6 15%,#f5e8d8 50%,#faf0e6 85%,#fdf6f0 100%); }}
.palace-frame {{ position:absolute; inset:24px; border:3px solid {wall_gold}88;
  box-shadow:inset 0 0 0 10px {p["surface"]}, inset 0 0 0 12px {wall_red}33, inset 0 0 0 20px {p["surface"]};
  pointer-events:none; z-index:1; }}
/* 四角装饰 */
.palace-frame::before {{ content:''; position:absolute; top:-10px; left:-10px;
  width:36px; height:36px; border-top:5px solid {wall_red}; border-left:5px solid {wall_red}; }}
.palace-frame::after {{ content:''; position:absolute; top:-10px; right:-10px;
  width:36px; height:36px; border-top:5px solid {wall_red}; border-right:5px solid {wall_red}; }}
.palace-cnr-bl {{ position:absolute; bottom:14px; left:14px; width:36px; height:36px;
  border-bottom:5px solid {wall_red}; border-left:5px solid {wall_red}; z-index:3; pointer-events:none; }}
.palace-cnr-br {{ position:absolute; bottom:14px; right:14px; width:36px; height:36px;
  border-bottom:5px solid {wall_red}; border-right:5px solid {wall_red}; z-index:3; pointer-events:none; }}
/* 匾额顶栏 */
.plaque {{ position:absolute; top:28px; left:50%; transform:translateX(-50%);
  padding:12px 50px; background:linear-gradient(180deg,{wall_red}dd,{wall_red});
  border:3px solid {wall_gold}; z-index:5;
  box-shadow:0 4px 12px rgba(0,0,0,0.2); }}
.plaque-text {{ font-size:28px; font-weight:900; color:#fdf6f0; letter-spacing:8px;
  font-family:'KaiTi','STKaiti',serif; }}
/* 回纹装饰带 */
.meander {{ position:absolute; left:48px; right:48px; height:4px; z-index:3; pointer-events:none; }}
.meander-top {{ top:120px; background:repeating-linear-gradient(90deg,
  {wall_red}44 0px,{wall_red}44 12px,transparent 12px,transparent 20px,
  {wall_gold}66 20px,{wall_gold}66 32px,transparent 32px,transparent 40px); }}
.meander-bottom {{ bottom:120px; background:repeating-linear-gradient(90deg,
  {wall_red}44 0px,{wall_red}44 12px,transparent 12px,transparent 20px,
  {wall_gold}66 20px,{wall_gold}66 32px,transparent 32px,transparent 40px); }}
"""
    css = _base_css(p, 3, extra)

    meta = ""
    if f["dynasty"] or f["category"]:
        parts = []
        if f["dynasty"]:
            parts.append(f'<span class="dynasty">{f["dynasty"]}</span>')
        if f["category"]:
            parts.append(f["category"])
        sep = ' <span class="dot"></span> '
        meta = f'<div class="meta" style="text-align:center;">{sep.join(parts)}</div>'
    wisdom = ""
    if f["lesson"]:
        wisdom = (
            f'<div class="wisdom-box" style="border-left-color:{wall_gold};">'
            f'<div class="wisdom-label" style="color:{wall_red};">📜 启示</div>'
            f'<div class="wisdom-text">{f["lesson"]}</div></div>')

    src = f'<div class="source" style="text-align:center;">—— {f["source"]}</div>' if f["source"] else ""
    img_layer = f'<div style="position:absolute;inset:0;background:url({img}) center/cover;opacity:0.12;filter:sepia(0.25) contrast(0.8);z-index:0;pointer-events:none;"></div>' if img else ""
    seal_html = _seal("御览", p, size=64, top="155px", right="70px")

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>{css}
.content {{ position:relative; z-index:4; display:flex; flex-direction:column;
  padding:140px 100px 50px 100px; height:100%; }}
.title {{ font-size:72px; text-align:center; padding-bottom:16px;
  border-bottom:2px solid {wall_gold}88; }}
</style></head><body>
{img_layer}
<div class="palace-bg"></div>
<div class="palace-frame"></div>
<div class="palace-cnr-bl"></div><div class="palace-cnr-br"></div>
<div class="meander meander-top"></div>
<div class="meander meander-bottom"></div>
<div class="plaque"><div class="plaque-text">历史典故</div></div>
{seal_html}
<div class="badge" style="position:absolute;top:42px;right:80px;z-index:6;">{n:02d} / 10</div>
<div class="content">
  <div class="title">{f["title"]}</div>
  {meta}<div class="divider" style="margin:20px 0;"></div>
  <div class="body" style="flex:1;">{f["story_zh"]}</div>
  {wisdom}{src}
  <div style="margin-top:auto;text-align:center;">
    <div class="divider" style="margin:14px 0;"></div>
    <div class="brand">Aethon · 历史卡片 · 每日典故</div>
  </div>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════
# 封面
# ═══════════════════════════════════════════════════════════

def _build_cover_html(count: int, today: date, p: dict) -> str:
    cn = "零一二三四五六七八九十"
    y, m, d = today.year, today.month, today.day

    def yn(n): return "".join(cn[int(c)] for c in str(n))
    cn_date = f"公元{yn(y)}年"
    cn_date += f"{cn[m]}月" if m <= 10 else f"十{'一二'[m-11]}月"
    if d <= 10: cn_date += f"{cn[d]}日"
    elif d < 20: cn_date += f"十{cn[d-10]}日"
    elif d == 20: cn_date += "二十日"
    elif d < 30: cn_date += f"二十{cn[d-20]}日"
    elif d == 30: cn_date += "三十日"
    else: cn_date += "三十一日"

    noise = _noise_svg(0.08)
    seal_html = _seal("古风史鉴", p, size=100, top="50%", left="50%", extra_style="margin-top:-50px;margin-left:-50px;")

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
{_base_css(p, 0)}
body::before {{ content:''; position:absolute; inset:0;
  background:url("data:image/svg+xml,{noise}") center/cover; pointer-events:none; z-index:99; }}
.cover-date-cn {{ font-size:48px; font-weight:400; color:{p["accent"]}; letter-spacing:8px; margin-bottom:10px; }}
.cover-date-en {{ font-size:32px; font-weight:300; color:{p["muted"]}; letter-spacing:4px; }}
.cover-title {{ font-size:96px; font-weight:900; color:{p["text"]}; letter-spacing:14px; line-height:1.1; }}
.cover-subtitle {{ font-size:36px; font-weight:400; color:{p["muted"]}; letter-spacing:8px; margin-top:20px; }}
.cover-count {{ font-size:32px; font-weight:400; color:{p["accent"]}; letter-spacing:6px; margin-top:24px; }}
.cover-divider {{ width:140px; height:3px;
  background:linear-gradient(to right,transparent,{p["accent"]},transparent); margin:28px auto; }}
.cover-flourish {{ position:absolute; width:200px; height:2px; background:{p["gold"]}88; }}
.cover-flourish::before, .cover-flourish::after {{ content:''; position:absolute; top:-3px;
  width:8px; height:8px; background:{p["gold"]}; transform:rotate(45deg); }}
.cover-flourish::before {{ left:-12px; }} .cover-flourish::after {{ right:-12px; }}
</style></head><body>
<div style="position:relative;z-index:2;display:flex;flex-direction:column;
  align-items:center;justify-content:center;height:100%;text-align:center;padding:60px;">
  <div class="cover-date-cn">{cn_date}</div>
  <div class="cover-date-en">{today.strftime('%Y · %m · %d')}</div>
  <div class="cover-divider"></div>
  <div style="position:relative;display:inline-block;">
    <div class="cover-flourish" style="top:-20px;left:50%;margin-left:-100px;"></div>
    <div class="cover-title">历史卡片</div>
    <div class="cover-flourish" style="bottom:-20px;left:50%;margin-left:-100px;"></div>
  </div>
  <div class="cover-subtitle">每日典故 · 古风集</div>
  <div class="cover-count">十则精选 · 古今博览</div>
  <div style="position:absolute;bottom:50px;width:100%;text-align:center;">
    <div class="brand" style="font-size:20px;">Aethon · 每日自动生成</div>
  </div>
</div>
<div style="position:absolute;top:50%;left:50%;">{seal_html}</div>
</body></html>"""


# ═══════════════════════════════════════════════════════════
# 调度 & 主入口
# ═══════════════════════════════════════════════════════════

def _extract(story: dict) -> dict:
    t = (story.get("title") or "").strip()
    # 截断到 200 字（42px字号下各布局安全上限 ≈240字，留20%余量）
    body = (story.get("story_zh") or "").strip()
    if len(body) > 200:
        # 尽量在句号处截断
        cut = body[:200]
        last_period = max(cut.rfind("。"), cut.rfind("！"), cut.rfind("？"))
        if last_period > 120:
            body = cut[:last_period + 1]
        else:
            body = cut[:197] + "…"
    return {
        "title": t,
        "dynasty": (story.get("dynasty") or "").strip(),
        "category": (story.get("category") or "").strip(),
        "story_zh": body,
        "lesson": (story.get("lesson") or "").strip(),
        "source": (story.get("source") or "").strip(),
        "fun_fact": (story.get("fun_fact") or "").strip(),
    }


def _build_card_html(story: dict, idx: int, img_path: str = "") -> str:
    p = PALETTES[idx % len(PALETTES)]
    f = _extract(story)
    layouts = [_layout_scroll, _layout_ink_wash, _layout_bamboo, _layout_palace]
    return layouts[idx % 4](f, p, idx + 1, img_path)


def render_ancient_cards(stories: list[dict],
                         output_dir: str = "docs/xhs",
                         max_stories: int = 10,
                         category: str = "历史故事") -> list[str]:
    project_root = Path(__file__).resolve().parent.parent
    today = date.today()
    date_dir = project_root / output_dir / today.strftime("%Y-%m-%d") / category
    date_dir.mkdir(parents=True, exist_ok=True)

    selected = stories[:max_stories]
    total = len(selected)
    rendered: list[str] = []

    logger.info(f"🏯 渲染 {total} 则故事 → {date_dir}")

    # ── 获取图片 ──
    img_map: dict[int, str] = {}
    try:
        from modules.image_fetcher import fetch_images_for_stories
        # API key 优先从环境变量读
        import os
        api_id = os.environ.get("APIHZ_ID", "10018440")
        api_key = os.environ.get("APIHZ_KEY", "")
        if api_key:
            img_map = fetch_images_for_stories(selected, api_id, api_key)
            img_map = {k: v.resolve().as_uri() for k, v in img_map.items()}
        else:
            logger.info("   (未配置 APIHZ_KEY，跳过图片获取)")
    except Exception as e:
        logger.warning(f"   图片获取失败: {e}")

    # 封面
    cover_p = PALETTES[0]
    cover_html = _build_cover_html(total, today, cover_p)
    cover_path = date_dir / "01_cover.png"
    try:
        render_html_to_png(cover_html, str(cover_path))
        rendered.append(str(cover_path.resolve()))
        logger.info(f"   封面: {cover_path.name}")
    except Exception as e:
        logger.error(f"   封面失败: {e}")

    # 故事卡
    for i, story in enumerate(selected):
        name = f"{i+2:02d}_story_{i+1:02d}.png"
        path = date_dir / name
        try:
            img_path = img_map.get(i, "")
            html = _build_card_html(story, i, img_path)
            render_html_to_png(html, str(path))
            rendered.append(str(path.resolve()))
            logger.info(f"   [{i+1}/{total}] {story.get('title','?')}")
        except Exception as e:
            logger.error(f"   [{i+1}] 失败: {e}")

    # manifest
    manifest = {
        "date": today.strftime("%Y-%m-%d"),
        "title": "历史卡片 · 每日典故",
        "story_count": total,
        "cards": [str(Path(p).relative_to(project_root)).replace("\\", "/") for p in rendered],
        "stories": [
            {"title": s.get("title", ""), "dynasty": s.get("dynasty", ""), "category": s.get("category", "")}
            for s in selected
        ],
    }
    mp = date_dir / "manifest.json"
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"📋 manifest → {mp}")
    logger.info(f"🏯 完成！{len(rendered)} 张卡片")
    return rendered


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    sample = [
        {
            "title": "一鸣惊人", "category": "成语典故", "dynasty": "战国",
            "source": "《史记·滑稽列传》",
            "story_zh": "楚庄王即位三年，日夜饮酒作乐，不理朝政，并下令：\"敢谏者死。\"大臣伍举以隐语试探：\"有鸟在于阜，三年不飞不鸣，是何鸟也？\"楚庄王听出弦外之音，答曰：\"此鸟不飞则已，一飞冲天；不鸣则已，一鸣惊人。\"此后庄王亲政，诛杀奸佞数百人，进用贤臣孙叔敖等数百人，楚国政治焕然一新。他率师北伐，观兵周疆，问九鼎之轻重，最终在邲之战中大败晋国，成为春秋五霸之一。",
            "lesson": "三年沉默不是无能，而是蓄势待发。真正的力量往往在最不经意的时刻爆发。",
            "fun_fact": "楚庄王是春秋五霸中唯一敢于自称为\"王\"的诸侯。",
        },
        {
            "title": "卧薪尝胆", "category": "成语典故", "dynasty": "春秋",
            "source": "《史记·越王勾践世家》",
            "story_zh": "吴越争霸，越王勾践惨败于夫差，被迫入吴为奴三年。归国后，勾践立志复仇，以柴草为床，悬苦胆于座前，每日舔尝以铭记耻辱。他委任文种治国、范蠡治军，十年休养生息，国力渐复。勾践又献美女西施迷惑夫差，使其荒废朝政。公元前473年，越军攻破吴都，夫差自杀，勾践终成春秋最后一霸，留下\"苦心人天不负\"的千古佳话。",
            "lesson": "失败不可怕，可怕的是失去东山再起的决心。忍辱负重方能成大事。",
            "fun_fact": "勾践用的\"胆\"其实是猪胆而非蛇胆，因为猪胆更苦且更难入口。",
        },
        {
            "title": "破釜沉舟", "category": "成语典故", "dynasty": "秦",
            "source": "《史记·项羽本纪》",
            "story_zh": "秦末天下大乱，项羽随叔父项梁起兵反秦。巨鹿之战中，秦将章邯率四十万大军围困赵军。项羽率五万楚军渡漳水救援，渡河后下令凿沉所有渡船、砸破炊具饭锅、烧毁营帐，每人只带三日干粮。众将士见无路可退，唯有死战求生。楚军以一当十，九战九捷，大破秦军主力，俘虏秦将王离。从此诸侯莫不臣服，项羽威震天下，成为反秦联军统帅。",
            "lesson": "斩断所有退路，才能激发最强的战斗力。绝境中往往藏着最大的转机。",
            "fun_fact": "这场战役之后，各诸侯将领觐见项羽时都是跪着爬进帐中的。",
        },
        {
            "title": "纸上谈兵", "category": "成语典故", "dynasty": "战国",
            "source": "《史记·廉颇蔺相如列传》",
            "story_zh": "赵国名将赵奢之子赵括，自幼熟读兵书，谈论军事无人能敌，连父亲都辩不过他。但赵奢临终告诫妻子：\"兵者死地，括易言之，若用为将，必败。\"公元前260年，秦军攻赵，老将廉颇坚守不出。赵王中反间计，以赵括替代廉颇。赵括到任后全盘推翻廉颇部署，主动出击，结果中了秦将白起的埋伏。四十余万赵军被围困四十六日，粮尽援绝，赵括突围时被射杀，全军覆没。此役赵国元气大伤，再无力与秦抗衡。",
            "lesson": "理论再完美，不经实践检验就是空谈。真正的智慧来自知行合一。",
            "fun_fact": "长平之战是中国古代规模最大的歼灭战，秦军坑杀降卒的数量至今仍有争议。",
        },
        {
            "title": "完璧归赵", "category": "成语典故", "dynasty": "战国",
            "source": "《史记·廉颇蔺相如列传》",
            "story_zh": "赵国得楚国至宝和氏璧，秦昭襄王愿以十五座城池交换。赵王怕秦强赵弱不敢拒绝，蔺相如自请携璧出使。秦王接见时，蔺相如见其拿到玉璧后只顾传给美人赏玩，全无割城之意，便上前说：\"璧有微瑕，请为大王指点。\"取回玉璧后，他退至殿柱旁，怒发冲冠，声言若秦王强取，便将自己的头颅与玉璧一同撞碎在柱上。秦王无奈当场斋戒五日。蔺相如当夜派人将玉璧悄悄送回赵国，次日独自面对秦王，不卑不亢，最终全身而退。",
            "lesson": "智慧比武力更强大。蔺相如凭一张嘴和一颗忠心，胜过了秦国的百万大军。",
            "fun_fact": "和氏璧后来被秦始皇制成传国玉玺，上面刻着\"受命于天既寿永昌\"八个字。",
        },
        {
            "title": "负荆请罪", "category": "成语典故", "dynasty": "战国",
            "source": "《史记·廉颇蔺相如列传》",
            "story_zh": "蔺相如完璧归赵和渑池会盟两立大功，被赵王封为上卿，位在大将廉颇之上。廉颇愤愤不平，扬言当众羞辱蔺相如。蔺相如得知后处处回避，甚至称病不上朝以免与之争位。门客不解，蔺相如说：\"秦国之所以不敢加兵于赵，只因有我与廉将军在。两虎相斗必有一伤，我避让廉将军，是以国家之急为先，私仇为后。\"此话传到廉颇耳中，他大为惭愧，脱去上衣背负荆条，跪到蔺相如门前请罪。两人遂结为刎颈之交，共同辅佐赵国。",
            "lesson": "真正的强大不是压倒对方，而是为了更大的目标甘愿低头。将军背上的荆条，胜过千言万语。",
            "fun_fact": "荆条是古代一种带刺的灌木枝条，背在身上会刺入皮肤，是极重的自罚方式。",
        },
        {
            "title": "指鹿为马", "category": "成语典故", "dynasty": "秦",
            "source": "《史记·秦始皇本纪》",
            "story_zh": "秦始皇病死于沙丘后，宦官赵高与丞相李斯密谋，伪造遗诏立胡亥为帝，赐死长子扶苏。秦二世胡亥即位后昏庸无能，赵高权倾朝野。为试探朝中大臣对自己的忠诚度，一日早朝，赵高牵来一头鹿献给二世，却说这是一匹马。二世笑道：\"丞相错了，这明明是鹿。\"赵高转身问群臣：\"这是鹿还是马？\"朝中有人沉默不语，有人阿谀附和说是马，少数正直者坚持说是鹿。事后赵高借故将那些说是鹿的大臣全部除掉，从此朝堂之上再无人敢违逆其意。秦朝也加速走向灭亡。",
            "lesson": "权力失去制约就会滋生荒谬。当谎言被集体默许，真相就成了最大的敌人。",
            "fun_fact": "赵高后来逼死秦二世，立子婴为帝，最终被子婴设计诛杀，夷灭三族。",
        },
        {
            "title": "四面楚歌", "category": "成语典故", "dynasty": "汉",
            "source": "《史记·项羽本纪》",
            "story_zh": "公元前202年，刘邦会合韩信、彭越等诸侯大军，将项羽围困于垓下。项羽兵少粮尽，夜间突然听到汉军营中传来楚地民歌，四面八方此起彼伏。他大惊失色：\"难道刘邦已经占据楚国了吗？为何楚人如此之多？\"军心瞬间瓦解，将士纷纷趁夜逃亡。项羽自知大势已去，与爱妾虞姬对饮帐中，慷慨悲歌：\"力拔山兮气盖世，时不利兮骓不逝。骓不逝兮可奈何，虞兮虞兮奈若何！\"歌罢泪下，左右皆泣。当夜率八百骑突围南走，最终在乌江边自刎，时年三十一岁。",
            "lesson": "最坚固的堡垒往往从内部瓦解。心理战的威力有时胜过百万雄师。",
            "fun_fact": "韩信让汉军唱楚歌是军事史上最早有记载的心理战术之一。",
        },
        {
            "title": "暗度陈仓", "category": "成语典故", "dynasty": "汉",
            "source": "《史记·淮阴侯列传》",
            "story_zh": "秦朝灭亡后，项羽自封西楚霸王，封刘邦为汉王，将其赶到偏僻的巴蜀和汉中地区，并派秦降将章邯等人驻守关中封锁刘邦东出的道路。刘邦入蜀后，采纳韩信\"明修栈道，暗度陈仓\"的计策：一面大张旗鼓地派兵修复被烧毁的褒斜栈道，做出大军将从原路返回的假象，迷惑章邯；另一面亲率精锐主力，从无人知晓的陈仓古道翻越秦岭，神兵天降般出现在关中平原。章邯仓促应战，在陈仓大败，退守废丘。刘邦一举平定三秦，占领关中，奠定了与项羽争夺天下的坚实基地。",
            "lesson": "最聪明的策略是让对手盯着你的左手，而你的右手已经完成致命一击。",
            "fun_fact": "陈仓古道至今尚存，位于陕西省宝鸡市境内，部分路段仍可徒步穿越。",
        },
        {
            "title": "背水一战", "category": "成语典故", "dynasty": "汉",
            "source": "《史记·淮阴侯列传》",
            "story_zh": "公元前204年，韩信率汉军数万攻打赵国。赵王歇和成安君陈余在井陉口集结二十万大军迎战，占据地利。韩信得知陈余不听谋士李左车抄后路的建议，便部署一万精兵在河边背水列阵，赵军望见大笑韩信不懂兵法。天明后韩信率主力出击，佯败后撤，赵军倾巢而出追击。此时韩信预先埋伏的两千轻骑兵突袭赵军大营，拔掉赵旗换上汉军红旗。赵军攻不下背水一战的汉军死士，回头又见大营插满汉旗，军心大乱，全线崩溃。韩信以少胜多，斩杀陈余，俘虏赵王歇。",
            "lesson": "置之死地而后生。当人没有退路的时候，就会爆发出最惊人的求生意志。",
            "fun_fact": "战后韩信亲自拜访被俘的李左车，虚心请教攻打燕齐之策，可见其用人之量。",
        },
    ]

    paths = render_ancient_cards(sample, max_stories=10)
    print(f"\n✅ {len(paths)} 张")


if __name__ == "__main__":
    main()
