"""
图片获取模块 — 接口盒子（百度图片搜索）+ 本地缓存

用法:
    from modules.image_fetcher import fetch_images_for_stories
    paths = fetch_images_for_stories(stories, api_id, api_key)
    # → {0: Path('cache/xxx.jpg'), 1: Path('cache/yyy.jpg'), ...}
"""

import hashlib
import json
import logging
import time
from pathlib import Path

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

API_URL = "https://cn.apihz.cn/api/img/apihzimgbaidu.php"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "docs" / "xhs" / ".image_cache"
INDEX_FILE = CACHE_DIR / "index.json"

# 下载超时与重试
DOWNLOAD_TIMEOUT = 20
MAX_RETRIES = 2


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> dict:
    """加载缓存索引。"""
    _ensure_cache_dir()
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_index(idx: dict) -> None:
    """保存缓存索引。"""
    _ensure_cache_dir()
    INDEX_FILE.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_key(story: dict) -> str:
    """根据故事标题 + 朝代生成唯一缓存键。"""
    raw = f"{story.get('dynasty', '')}_{story.get('title', '')}_{story.get('category', '')}"
    return hashlib.md5(raw.encode()).hexdigest()[:14]


def _build_queries(story: dict) -> list[str]:
    """为故事构建 3 条搜索词（优先级从高到低）。

    接口盒子要求 keywords ≤ 10 个汉字。
    """
    title = (story.get("title") or "").strip()
    dynasty = (story.get("dynasty") or "").strip()
    keywords = story.get("keywords", [])

    queries = []

    # Q1: 朝代 + 关键词（最精准）
    if keywords:
        kw = keywords[0]
        q = f"{dynasty}{kw}" if dynasty else kw
        if len(q) <= 10:
            queries.append(q)

    # Q2: 标题 + 朝代 + 古画
    q = f"{dynasty}{title}古画" if dynasty else f"{title}古画"
    if len(q) > 10:
        q = f"{title[:4]}古画"
    queries.append(q[:10])

    # Q3: 朝代兜底（朝代代表性文物）
    if dynasty:
        queries.append(f"{dynasty}文物")

    return queries


def _search_baidu_images(query: str, api_id: str, api_key: str, limit: int = 5) -> list[str]:
    """搜索百度图片，返回图片 URL 列表。"""
    try:
        r = httpx.get(API_URL, params={
            "id": api_id,
            "key": api_key,
            "words": query[:10],
            "page": 1,
            "limit": limit,
            "type": 1,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()

        if data.get("code") != 200:
            logger.debug(f"   API 异常 ({query}): {data.get('msg', '')}")
            return []

        results = data.get("res", [])
        if isinstance(results, list):
            return [u for u in results if isinstance(u, str) and u.startswith("http")]
        return []
    except Exception as e:
        logger.debug(f"   搜索失败 ({query}): {e}")
        return []


def _download_image(url: str, dest: Path) -> bool:
    """下载图片并缩放到 1200px 宽，保存为 JPEG。"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = httpx.get(url, timeout=DOWNLOAD_TIMEOUT, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://image.baidu.com/",
            })
            r.raise_for_status()

            if len(r.content) < 1024:
                logger.debug(f"   图片太小 ({len(r.content)}B), 跳过")
                return False

            # 临时保存
            tmp = dest.with_suffix(".tmp")
            tmp.write_bytes(r.content)

            # 缩放
            try:
                img = Image.open(tmp)
                w, h = img.size
                if w > 1200:
                    ratio = 1200 / w
                    img = img.resize((1200, int(h * ratio)), Image.LANCZOS)
                img = img.convert("RGB")
                img.save(dest, "JPEG", quality=85)
                tmp.unlink(missing_ok=True)
            except Exception:
                # 不是有效图片，直接保存原始文件
                tmp.rename(dest)

            logger.debug(f"   下载成功: {len(r.content)/1024:.0f}KB → {dest.name}")
            return True

        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(1)
            else:
                logger.debug(f"   下载失败: {e}")
    return False


def fetch_images_for_stories(stories: list[dict],
                             api_id: str,
                             api_key: str,
                             force: bool = False) -> dict[int, Path]:
    """为故事列表获取图片，返回 {story_index: local_path}。

    Args:
        stories: 故事 dict 列表
        api_id: 接口盒子用户 ID
        api_key: 接口盒子通讯密钥
        force: True = 强制重新搜索（忽略缓存）

    Returns:
        {0: Path('cache/abc.jpg'), 1: Path('cache/def.jpg'), ...}
        只包含成功获取到图片的故事索引
    """
    index = {} if force else _load_index()
    results: dict[int, Path] = {}
    new_items = 0

    logger.info(f"🖼️  获取故事图片 (缓存 {len(index)} 条)...")

    for i, story in enumerate(stories):
        ck = _cache_key(story)
        title = story.get("title", "?")
        dynasty = story.get("dynasty", "")

        # 1. 查缓存
        if ck in index:
            cached_path = CACHE_DIR / index[ck]
            if cached_path.exists():
                results[i] = cached_path
                logger.debug(f"   [{i+1}] {dynasty}·{title} ← 缓存")
                continue

        # 2. 构建查询链
        queries = _build_queries(story)
        logger.debug(f"   [{i+1}] {dynasty}·{title} → 查询: {queries}")

        # 3. 搜索（优先级依次尝试）
        image_urls: list[str] = []
        for q in queries:
            urls = _search_baidu_images(q, api_id, api_key)
            if urls:
                image_urls = urls
                logger.debug(f"      命中 \"{q}\": {len(urls)} 张")
                break

        if not image_urls:
            logger.warning(f"   [{i+1}] {dynasty}·{title} ❌ 无搜索结果")
            continue

        # 4. 下载第一张有效图
        dest = CACHE_DIR / f"{ck}.jpg"
        ok = False
        for url in image_urls:
            if _download_image(url, dest):
                ok = True
                break

        if ok:
            index[ck] = dest.name
            results[i] = dest
            new_items += 1
            logger.info(f"   [{i+1}] {dynasty}·{title} ✅ {dest.name}")
        else:
            logger.warning(f"   [{i+1}] {dynasty}·{title} ❌ 下载失败")

        # 5. 节流（避免 API 限频）
        time.sleep(0.3)

    # 保存索引
    if new_items > 0:
        _save_index(index)

    logger.info(f"🖼️  完成: {len(results)}/{len(stories)} 张 (新增 {new_items})")
    return results


def clear_cache() -> int:
    """清空缓存（返回删除的文件数）。"""
    if not CACHE_DIR.exists():
        return 0
    count = 0
    for f in CACHE_DIR.iterdir():
        if f.is_file():
            f.unlink()
            count += 1
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    # 快速测试
    stories = [
        {"title": "一鸣惊人", "dynasty": "战国", "category": "成语典故", "keywords": ["楚庄王", "春秋五霸"]},
        {"title": "卧薪尝胆", "dynasty": "春秋", "category": "成语典故", "keywords": ["勾践", "夫差", "西施"]},
        {"title": "破釜沉舟", "dynasty": "秦", "category": "成语典故", "keywords": ["项羽", "巨鹿之战"]},
        {"title": "纸上谈兵", "dynasty": "战国", "category": "成语典故", "keywords": ["赵括", "长平之战", "白起"]},
        {"title": "完璧归赵", "dynasty": "战国", "category": "成语典故", "keywords": ["蔺相如", "和氏璧"]},
        {"title": "负荆请罪", "dynasty": "战国", "category": "成语典故", "keywords": ["廉颇", "蔺相如"]},
        {"title": "指鹿为马", "dynasty": "秦", "category": "成语典故", "keywords": ["赵高", "秦二世"]},
        {"title": "四面楚歌", "dynasty": "汉", "category": "成语典故", "keywords": ["项羽", "垓下", "虞姬"]},
        {"title": "暗度陈仓", "dynasty": "汉", "category": "成语典故", "keywords": ["韩信", "章邯", "陈仓"]},
        {"title": "背水一战", "dynasty": "汉", "category": "成语典故", "keywords": ["韩信", "井陉口"]},
    ]

    import os
    api_id = os.environ.get("APIHZ_ID", "10018440")
    api_key = os.environ.get("APIHZ_KEY", "9ed0c4ef737e15671d7cf343268b9e5c")

    results = fetch_images_for_stories(stories, api_id, api_key)
    print(f"\n✅ {len(results)}/10 成功")
    for idx, path in results.items():
        s = stories[idx]
        print(f"  [{idx}] {s['dynasty']}·{s['title']} → {path.name} ({path.stat().st_size/1024:.0f}KB)")
