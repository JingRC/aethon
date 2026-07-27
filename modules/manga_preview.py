"""
漫画剧本 HTML 预览生成器

将 LLM 生成的章节 JSON 渲染为可视化预览页面，
用户可以在浏览器中查看、确认后再生图。
"""

import json
import logging
import webbrowser
from pathlib import Path

logger = logging.getLogger(__name__)

# 布局模拟 CSS Grid
LAYOUT_GRID_CSS = {
    "splash": "grid-template: 1fr / 1fr;",
    "half": "grid-template: 1fr / 1fr 1fr;",
    "trio": "grid-template: 1fr / 1fr 1fr 1fr;",
    "grid4": "grid-template: 1fr 1fr / 1fr 1fr;",
    "cinema": "grid-template: 2fr 1fr / 1fr;",
    "stack": "grid-template: 1fr 1fr / 2fr 1fr;",
    "grid5": "grid-template: 1fr 1fr / 1fr 1fr 1fr;",
}


def _panel_html(panel: dict, idx: int) -> str:
    """渲染单个漫画格的预览。"""
    dialogue = panel.get("dialogue", "")
    narration = panel.get("narration", "")
    sfx = panel.get("sfx", "")
    img_prompt = panel.get("image_prompt", "")[:80]

    content = ""

    if narration:
        content += (
            f'<div class="narration-tag">📝 旁白: {narration[:60]}</div>'
        )
    if dialogue:
        content += (
            f'<div class="dialogue-tag">💬 {dialogue[:60]}</div>'
        )
    if sfx:
        content += (
            f'<div class="sfx-tag">💥 {sfx}</div>'
        )
    if img_prompt:
        content += (
            f'<div class="prompt-tag">🎨 {img_prompt}…</div>'
        )

    if not content:
        content = '<div class="empty-tag">（空）</div>'

    return f'<div class="panel-box">{content}</div>'


def generate_preview_html(chapter: dict, chapter_num: int, output_path: str | Path) -> str:
    """生成章节剧本的 HTML 预览文件，返回文件路径。"""
    output_path = Path(output_path)
    title = chapter.get("title", f"第{chapter_num}章")
    headline = chapter.get("headline", "")
    subtitle = chapter.get("subtitle", "")
    pages = chapter.get("pages", [])
    total_panels = sum(len(p.get("panels", [])) for p in pages)

    # 构建页面 HTML
    page_sections = []
    for i, page in enumerate(pages):
        layout = page.get("layout", "grid4")
        panels = page.get("panels", [])
        panel_count = len(panels)

        panels_html = "\n".join(
            _panel_html(p, j) for j, p in enumerate(panels)
        )

        grid_css = LAYOUT_GRID_CSS.get(layout, LAYOUT_GRID_CSS["grid4"])

        page_sections.append(f"""
        <div class="page-card">
            <div class="page-header">
                <span class="page-num">第 {i+1} 页</span>
                <span class="layout-badge">{layout} · {panel_count}格</span>
            </div>
            <div class="panels-grid" style="{grid_css}">
                {panels_html}
            </div>
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>小道士下山记 · 第{chapter_num}章 剧本预览</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: 'Microsoft YaHei','PingFang SC',sans-serif;
    background:#f0ebe0; color:#333; padding:20px;
}}
.container {{ max-width:800px; margin:0 auto; }}

/* 封面区 */
.cover-section {{
    background:linear-gradient(180deg,#2a2015,#4a3820);
    color:#fdf6ee; padding:40px 30px; border-radius:12px;
    text-align:center; margin-bottom:24px;
}}
.cover-series {{ font-size:14px; letter-spacing:6px; opacity:0.6; margin-bottom:16px; }}
.cover-headline {{ font-size:56px; font-weight:900; margin-bottom:8px; }}
.cover-title {{ font-size:22px; opacity:0.85; }}
.cover-subtitle {{ font-size:16px; opacity:0.6; margin-top:12px; }}
.cover-stats {{ display:flex; justify-content:center; gap:24px; margin-top:20px; }}
.cover-stat {{ font-size:14px; opacity:0.6; }}

/* 页面卡片 */
.page-card {{
    background:#fff; border-radius:10px; padding:20px;
    margin-bottom:20px; box-shadow:0 2px 8px rgba(0,0,0,0.06);
}}
.page-header {{
    display:flex; justify-content:space-between; align-items:center;
    margin-bottom:14px; padding-bottom:10px;
    border-bottom:1px solid #e8e0d5;
}}
.page-num {{ font-size:16px; font-weight:700; color:#8b6914; }}
.layout-badge {{
    font-size:12px; background:#f0ebe0; color:#8b6914;
    padding:3px 10px; border-radius:12px;
}}

/* 面板网格 */
.panels-grid {{
    display:grid; gap:8px; min-height:120px;
}}

/* 面板内容 */
.panel-box {{
    border:2px dashed #d8d0c0; border-radius:8px;
    padding:12px; background:#fafaf6;
    display:flex; flex-direction:column; gap:4px;
    font-size:13px; min-height:60px;
}}
.narration-tag {{
    background:#e8e0f0; color:#5a4080; padding:4px 8px;
    border-radius:4px; font-size:12px;
}}
.dialogue-tag {{
    background:#e0f0e8; color:#2a6040; padding:4px 8px;
    border-radius:4px; font-size:12px;
    border-left:3px solid #4a8a6a;
}}
.sfx-tag {{
    background:#f0e0e0; color:#c03030; padding:4px 8px;
    border-radius:4px; font-size:14px; font-weight:900;
}}
.prompt-tag {{
    color:#999; font-size:11px; margin-top:auto; font-style:italic;
}}
.empty-tag {{ color:#ccc; font-size:13px; text-align:center; }}

/* 底部操作区 */
.action-section {{
    background:#fff; border-radius:10px; padding:24px;
    text-align:center; margin-top:24px;
    box-shadow:0 2px 8px rgba(0,0,0,0.06);
}}
.action-section h3 {{ margin-bottom:12px; }}
.action-note {{ color:#999; font-size:13px; margin-top:10px; }}
.btn {{
    display:inline-block; padding:12px 30px; border-radius:8px;
    font-size:16px; font-weight:700; cursor:pointer; border:none;
    text-decoration:none; margin:4px;
}}
.btn-primary {{ background:#4a8a6a; color:#fff; }}
.btn-primary:hover {{ background:#3a7050; }}
.btn-secondary {{ background:#e8e0d5; color:#6a5030; }}
.json-section {{
    margin-top:24px; text-align:left;
    background:#fafaf8; border-radius:8px; padding:16px;
    font-size:12px; max-height:200px; overflow:auto;
}}
.json-section pre {{ white-space:pre-wrap; word-break:break-all; }}
</style>
</head>
<body>
<div class="container">

    <!-- 封面 -->
    <div class="cover-section">
        <div class="cover-series">小 道 士 下 山 记</div>
        <div class="cover-headline">{headline}</div>
        <div class="cover-title">{title}</div>
        <div class="cover-subtitle">{subtitle}</div>
        <div class="cover-stats">
            <span class="cover-stat">📄 {len(pages)} 页</span>
            <span class="cover-stat">🎬 {total_panels} 格</span>
            <span class="cover-stat">📘 第{chapter_num}章</span>
        </div>
    </div>

    <!-- 页面列表 -->
    {"".join(page_sections)}

    <!-- 操作区 -->
    <div class="action-section">
        <h3>✅ 剧本确认</h3>
        <p style="margin-bottom:12px; color:#666;">检查每页的布局、对话和画面描述，确认无误后回复。</p>
        <p class="action-note">📝 如需修改，直接编辑 JSON 文件然后刷新此页面</p>
    </div>

    <!-- JSON 原文 -->
    <details class="json-section">
        <summary>📋 查看原始 JSON（点击展开）</summary>
        <pre>{json.dumps(chapter, ensure_ascii=False, indent=2)[:5000]}</pre>
    </details>

</div>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    logger.info(f"📋 预览页面: {output_path}")
    return str(output_path)
