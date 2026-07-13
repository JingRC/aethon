"""
Xiaohongshu image card renderer v2 — HTML → PNG via headless Chrome

Design system: "Dark Editorial" — Swiss typography, magazine-quality
- 1080×1440 cards (XHS optimal 3:4)
- Deep dark background + electric cyan accent
- Massive type contrast, minimal decoration
- SVG noise texture for analog print feel
"""

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from string import Template

from jinja2 import Template as JinjaTemplate

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────
CARD_W = 1080
CARD_H = 1440

# ── Color system: "Dark Editorial" ────────────────────────
CSS = """
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    width: ${width}px; height: ${height}px;
    background: ${bg};
    font-family: 'Noto Sans SC', 'Microsoft YaHei', 'PingFang SC', sans-serif;
    color: ${text};
    overflow: hidden;
    position: relative;
  }
  /* ── SVG noise texture overlay ── */
  body::after {
    content: '';
    position: absolute; inset: 0; z-index: 999;
    pointer-events: none;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
    background-repeat: repeat;
  }
  .container { padding: 72px 64px; position: relative; z-index: 1; height: 100%; display: flex; flex-direction: column; }
  .top-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 48px; }
  .number { font-size: 120px; font-weight: 900; line-height: 1; color: ${accent}; letter-spacing: -4px; }
  .badges { display: flex; gap: 16px; align-items: center; }
  .badge { padding: 10px 24px; border-radius: 100px; font-size: 24px; font-weight: 600; letter-spacing: 1px; }
  .badge-score { background: ${accent}22; color: ${accent}; }
  .badge-source { background: ${surface}; color: ${text_muted}; }
  .divider { width: ${divider_w}px; height: 3px; background: ${accent}; opacity: 0.6; margin: 40px 0; }
  .title { font-size: ${title_size}px; font-weight: 900; line-height: 1.15; color: ${text}; letter-spacing: -0.5px; }
  .summary { font-size: 30px; font-weight: 400; line-height: 1.6; color: ${text_muted}; flex: 1; }
  .insight-box { background: ${surface}; border-left: 4px solid ${accent}; padding: 32px 40px; border-radius: 0 12px 12px 0; margin: 32px 0; }
  .insight-label { font-size: 24px; font-weight: 700; color: ${accent}; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 12px; }
  .insight-text { font-size: 28px; font-weight: 400; line-height: 1.5; color: ${text}; }
  .footer { display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding-top: 40px; border-top: 1px solid ${divider}; }
  .footer-source { font-size: 22px; color: ${text_muted}; font-weight: 300; }
  .footer-brand { font-size: 20px; color: ${text_muted}; font-weight: 300; opacity: 0.5; letter-spacing: 2px; }

  /* ── Cover card styles ── */
  .cover-center { text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; }
  .cover-icon { font-size: 100px; margin-bottom: 40px; }
  .cover-title { font-size: 72px; font-weight: 900; color: ${text}; letter-spacing: -1px; margin-bottom: 24px; }
  .cover-subtitle { font-size: 36px; font-weight: 300; color: ${text_muted}; margin-bottom: 60px; }
  .cover-divider { width: 120px; height: 3px; background: ${accent}; margin-bottom: 60px; }
  .cover-stat { font-size: 56px; font-weight: 900; color: ${accent}; }
  .cover-stat-label { font-size: 28px; font-weight: 300; color: ${text_muted}; margin-top: 12px; }
  .cover-accent-dot { width: 12px; height: 12px; border-radius: 50%; background: ${accent}; display: inline-block; margin: 0 16px; }
  .cover-grid { display: flex; gap: 80px; margin-top: 40px; }
  .cover-grid-item { text-align: center; }

  /* ── Last card: compact summary ── */
  .summary-list { display: flex; flex-direction: column; gap: 20px; flex: 1; }
  .summary-item { display: flex; gap: 20px; align-items: flex-start; padding: 20px 0; border-bottom: 1px solid ${divider}; }
  .summary-num { font-size: 28px; font-weight: 900; color: ${accent}; min-width: 40px; }
  .summary-title { font-size: 26px; font-weight: 600; color: ${text}; line-height: 1.4; }
  .summary-source { font-size: 20px; color: ${text_muted}; margin-top: 6px; }

  /* ── AI news image placeholder ── */
  .img-placeholder {
    width: 100%; height: 280px;
    background: ${surface};
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 48px; margin-bottom: 40px;
    position: relative; overflow: hidden;
  }
  .img-placeholder::before {
    content: '';
    position: absolute; inset: 0;
    background: linear-gradient(135deg, ${accent}15 0%, transparent 50%, ${accent}08 100%);
  }
  .img-icon { position: relative; z-index: 1; }
</style>
"""

# ── Chrome finder ─────────────────────────────────────────

def _find_chrome() -> str:
    """Find a headless-capable Chrome/Chromium binary."""
    # Prefer GOOGLE_CHROME_BIN env var (CI override)
    env_chrome = os.environ.get("GOOGLE_CHROME_BIN", "")
    if env_chrome and os.path.exists(env_chrome):
        return env_chrome

    candidates = [
        # GitHub Actions ubuntu-latest
        "google-chrome",
        "google-chrome-stable",
        "chromium-browser",
        "chromium",
        # Windows
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for c in candidates:
        if shutil.which(c) or os.path.exists(c):
            return c
    # Fallback
    return "google-chrome"


# ── HTML → PNG renderer ───────────────────────────────────

def render_html_to_png(html: str, png_path: str,
                       width: int = CARD_W, height: int = CARD_H) -> str:
    """Render an HTML string to a PNG file via headless Chrome."""
    # Write HTML to temp file (Chrome needs a file:// URL for reliable rendering)
    html_path = Path(png_path).with_suffix(".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    chrome = _find_chrome()
    abs_html = html_path.resolve().as_uri()
    abs_png = Path(png_path).resolve()

    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        f"--window-size={width},{height}",
        "--force-device-scale-factor=2",   # retina quality (2x)
        f"--screenshot={abs_png}",
        abs_html,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30,
                       env={**os.environ, "DISPLAY": ":99"})
    except subprocess.CalledProcessError as e:
        logger.error(f"Chrome stderr: {e.stderr.decode() if e.stderr else ''}")
        raise

    # Clean up temp HTML
    try:
        os.remove(html_path)
    except OSError:
        pass

    # Verify output
    if not os.path.exists(str(abs_png)) or os.path.getsize(str(abs_png)) < 100:
        raise RuntimeError(f"Chrome did not produce valid output at {abs_png}")

    return str(abs_png)


# ── Design tokens ─────────────────────────────────────────

def _design_tokens() -> dict:
    return {
        "bg": "#0D0D0D",
        "surface": "#1A1A1C",
        "text": "#EAE8E3",
        "text_muted": "#7A7A72",
        "accent": "#00C8FF",
        "accent2": "#FF3B5C",
        "divider": "#2A2A2C",
        "divider_w": 90,
        "title_size": 54,
        "width": CARD_W,
        "height": CARD_H,
    }


# ── Card builders ─────────────────────────────────────────

def _build_cover_html(date_str: str, count: int) -> str:
    t = _design_tokens()
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{CSS}</head><body>
<div class="container cover-center">
  <div class="cover-icon">📡</div>
  <div class="cover-title">今日 AI 快讯</div>
  <div class="cover-subtitle">{date_str}</div>
  <div class="cover-divider"></div>
  <div class="cover-grid">
    <div class="cover-grid-item">
      <div class="cover-stat">{count}</div>
      <div class="cover-stat-label">条精选快讯</div>
    </div>
    <div class="cover-grid-item">
      <div class="cover-stat">10</div>
      <div class="cover-stat-label">个数据源聚合</div>
    </div>
    <div class="cover-grid-item">
      <div class="cover-stat">✶✶✶✶✶</div>
      <div class="cover-stat-label">LLM 精选 + 评分</div>
    </div>
  </div>
</div>
</body></html>"""


def _build_news_card_html(item: dict, index: int, total: int) -> str:
    t = _design_tokens()
    title = item.get("title", "")
    source = item.get("source", "")
    score = int(item.get("score", 3))
    stars = "★" * score + "☆" * (5 - score)
    summary = item.get("summary_zh", "")
    insight = item.get("insight_zh", item.get("summary_zh", ""))[:150]
    news_url = item.get("url", "")
    # XHS doesn't allow clickable links; use text form
    url_text = ""
    if news_url:
        # Extract domain for cleaner display
        from urllib.parse import urlparse
        try:
            domain = urlparse(news_url).netloc
            url_text = f"原文 {domain}"
        except Exception:
            url_text = f"原文见 {news_url[:60]}"

    # Pick a relevant emoji based on source
    source_emojis = {
        "TechCrunch": "🚀", "The Verge": "📡", "GitHub": "💻",
        "HuggingFace": "🤗", "arXiv": "📄", "36氪": "🔥",
        "ifanr": "📱", "GitHub Trending": "⭐",
    }
    emoji = source_emojis.get(source, "📌")

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{CSS}</head><body>
<div class="container">
  <div class="top-bar">
    <div class="number">{index:02d}</div>
    <div class="badges">
      <span class="badge badge-score">{stars}</span>
      <span class="badge badge-source">{emoji} {source}</span>
    </div>
  </div>
  <div class="divider"></div>
  <div class="title">{title}</div>
  <div class="divider" style="width:60px;"></div>
  <div class="summary">{summary}</div>
  <div class="insight-box">
    <div class="insight-label">⟡ 关键洞察</div>
    <div class="insight-text">{insight}</div>
  </div>
  <div class="footer">
    <div class="footer-source">{url_text}</div>
    <div class="footer-brand">每日双拼日报</div>
  </div>
</div>
</body></html>"""


def _build_summary_card_html(ai_news: list[dict], date_str: str) -> str:
    """Last card: quick overview of all 10 items."""
    t = _design_tokens()
    items_html = ""
    for i, item in enumerate(ai_news[:10], 1):
        score = "★" * int(item.get("score", 3))
        items_html += f"""<div class="summary-item">
  <div class="summary-num">{i:02d}</div>
  <div>
    <div class="summary-title">{item.get('title','')}  {score}</div>
    <div class="summary-source">{item.get('source','')}</div>
  </div>
</div>"""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">{CSS}</head><body>
<div class="container">
  <div class="cover-icon" style="font-size:60px;margin-bottom:24px;">📋</div>
  <div class="cover-title" style="font-size:48px;">今日快讯一览</div>
  <div class="cover-subtitle" style="font-size:24px;margin-bottom:30px;">{date_str}</div>
  <div class="divider"></div>
  <div class="summary-list">{items_html}</div>
  <div class="footer" style="margin-top:auto;padding-top:30px;">
    <div class="footer-source">数据来源：HuggingFace · TechCrunch · The Verge · 36Kr · GitHub · arXiv</div>
    <div class="footer-brand">每日双拼日报</div>
  </div>
</div>
</body></html>"""


# ── Public API ────────────────────────────────────────────

def render_xhs_cards(ai_news: list[dict],
                     output_dir: str = "docs/xhs",
                     max_news: int = 10) -> list[str]:
    """
    Render XHS image cards for AI news items.

    Cards produced:
      1. Cover card
      2..N+1.  One card per news item (up to max_news)
      Last.    Summary overview card

    Returns list of saved PNG file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    today_cn = datetime.now().strftime("%Y年%m月%d日")
    date_file = datetime.now().strftime("%Y%m%d")
    paths = []
    selected = ai_news[:max_news]
    total = 2 + len(selected)  # cover + N news cards + summary
    card_num = 0

    logger.info(f"[XHS Renderer] Starting: {total} cards (1080x1440, Dark Editorial)")

    # 1. Cover card
    card_num += 1
    html = _build_cover_html(today_cn, len(selected))
    png = out / f"{date_file}_01_cover.png"
    render_html_to_png(html, str(png))
    paths.append(str(png))
    logger.info(f"  [{card_num}/{total}] Cover card -> {png.name}")

    # 2. News cards (one per item)
    for i, item in enumerate(selected):
        card_num += 1
        html = _build_news_card_html(item, i + 1, len(selected))
        png = out / f"{date_file}_{card_num:02d}_news_{i+1:02d}.png"
        render_html_to_png(html, str(png))
        paths.append(str(png))
        logger.info(f"  [{card_num}/{total}] '{item.get('title','')[:40]}...' -> {png.name}")

    # 3. Summary overview card
    card_num += 1
    html = _build_summary_card_html(selected, today_cn)
    png = out / f"{date_file}_{card_num:02d}_summary.png"
    render_html_to_png(html, str(png))
    paths.append(str(png))
    logger.info(f"  [{card_num}/{total}] Summary card -> {png.name}")

    logger.info(f"[XHS Renderer] Done: {len(paths)} cards -> {out}/")
    return paths
