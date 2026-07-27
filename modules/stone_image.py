"""
石头禅修 — AI 图像生成模块

调用 CloudBase 云函数 ai-proxy（混元生图，10万张免费额度），
失败自动 fallback 到 SiliconFlow / Cloudflare / Pollinations。
生成图片以 MD5(prompt) 缓存到 .image_cache/。
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "docs" / "xhs" / ".image_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
INDEX_PATH = CACHE_DIR / "stone_index.json"

# ── API 配置（从环境变量读取，兼容 GitHub Actions Secrets）──
CLOUDBASE_ENV = os.environ.get("CLOUDBASE_ENV", "")
CLOUDBASE_API_KEY = os.environ.get("CLOUDBASE_API_KEY", "")

# Fallback APIs
SILICONFLOW_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
CLOUDFLARE_ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
POLLINATIONS_KEY = os.environ.get("POLLINATIONS_API_KEY", "")
MODELSCOPE_TOKEN = os.environ.get("MODELSCOPE_API_TOKEN", "")


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _load_index() -> dict:
    if INDEX_PATH.exists():
        try:
            return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_index(idx: dict) -> None:
    INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


# ═══════════════════════════════════════════════════════════
# Primary: CloudBase 云函数（混元生图）
# ═══════════════════════════════════════════════════════════

def _generate_cloudbase(prompt: str, seed: int = None, size: str = "1024x1024") -> str | None:
    """调用 CloudBase 云函数 ai-proxy 生图，返回图片本地路径或 None。"""
    if not CLOUDBASE_ENV or not CLOUDBASE_API_KEY:
        logger.debug("CloudBase 未配置，跳过")
        return None

    url = f"https://{CLOUDBASE_ENV}.api.tcloudbasegateway.com/v1/functions/ai-proxy/invoke"
    payload = {"prompt": prompt, "size": size}
    if seed is not None:
        payload["seed"] = seed

    try:
        r = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {CLOUDBASE_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=180,
        )
        data = r.json()
        if data.get("success") and data.get("image_url"):
            img_url = data["image_url"]
            logger.info(f"   CloudBase ✓ ({r.elapsed.total_seconds():.1f}s)")
            # 下载图片
            ir = requests.get(img_url, timeout=60)
            if ir.status_code == 200:
                cache_key = _md5(prompt)
                ext = ".png"
                content_type = ir.headers.get("content-type", "")
                if "jpeg" in content_type or "jpg" in content_type:
                    ext = ".jpg"
                elif "webp" in content_type:
                    ext = ".webp"
                cache_path = CACHE_DIR / f"stone_{cache_key}{ext}"
                cache_path.write_bytes(ir.content)
                return str(cache_path)
            else:
                logger.warning(f"   CloudBase 图片下载失败: HTTP {ir.status_code}")
        else:
            logger.warning(f"   CloudBase 返回失败: {data.get('error', 'unknown')[:100]}")
    except requests.Timeout:
        logger.warning("   CloudBase 超时")
    except Exception as e:
        logger.warning(f"   CloudBase 异常: {e}")
    return None


# ═══════════════════════════════════════════════════════════
# Fallback 1: SiliconFlow（100张/天）
# ═══════════════════════════════════════════════════════════

def _generate_siliconflow(prompt: str, seed: int = None) -> str | None:
    """SiliconFlow FLUX.1-schnell，OpenAI 兼容接口。"""
    if not SILICONFLOW_KEY:
        return None
    try:
        r = requests.post(
            "https://api.siliconflow.cn/v1/images/generations",
            json={
                "model": "black-forest-labs/FLUX.1-schnell",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                **({"seed": seed} if seed else {}),
            },
            headers={
                "Authorization": f"Bearer {SILICONFLOW_KEY}",
                "Content-Type": "application/json",
            },
            timeout=120,
        )
        data = r.json()
        img_url = data.get("data", [{}])[0].get("url", "")
        if img_url:
            logger.info(f"   SiliconFlow ✓ ({r.elapsed.total_seconds():.1f}s)")
            ir = requests.get(img_url, timeout=60)
            if ir.status_code == 200:
                cache_key = _md5(prompt)
                cache_path = CACHE_DIR / f"stone_{cache_key}.png"
                cache_path.write_bytes(ir.content)
                return str(cache_path)
    except Exception as e:
        logger.warning(f"   SiliconFlow 异常: {e}")
    return None


# ═══════════════════════════════════════════════════════════
# Fallback 2: Cloudflare Workers AI（900张/天）
# ═══════════════════════════════════════════════════════════

def _generate_cloudflare(prompt: str, seed: int = None) -> str | None:
    """Cloudflare Workers AI Flux Schnell。"""
    if not CLOUDFLARE_ACCOUNT or not CLOUDFLARE_TOKEN:
        return None
    try:
        r = requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT}/ai/run/"
            f"@cf/black-forest-labs/flux-schnell",
            json={"prompt": prompt, **({"seed": seed} if seed else {})},
            headers={"Authorization": f"Bearer {CLOUDFLARE_TOKEN}"},
            timeout=120,
        )
        if r.status_code == 200:
            logger.info(f"   Cloudflare ✓ ({r.elapsed.total_seconds():.1f}s)")
            cache_key = _md5(prompt)
            cache_path = CACHE_DIR / f"stone_{cache_key}.png"
            cache_path.write_bytes(r.content)
            return str(cache_path)
    except Exception as e:
        logger.warning(f"   Cloudflare 异常: {e}")
    return None


# ═══════════════════════════════════════════════════════════
# Fallback 3: Pollinations.ai（无限速率）
# ═══════════════════════════════════════════════════════════

def _generate_pollinations(prompt: str, seed: int = None) -> str | None:
    """Pollinations.ai，完全免费。"""
    if not POLLINATIONS_KEY:
        return None
    try:
        import urllib.parse
        encoded = urllib.parse.quote(prompt)
        seed_param = f"&seed={seed}" if seed else ""
        img_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true{seed_param}"
        r = requests.get(img_url, timeout=120)
        if r.status_code == 200 and len(r.content) > 1000:
            logger.info(f"   Pollinations ✓ ({r.elapsed.total_seconds():.1f}s)")
            cache_key = _md5(prompt)
            cache_path = CACHE_DIR / f"stone_{cache_key}.png"
            cache_path.write_bytes(r.content)
            return str(cache_path)
    except Exception as e:
        logger.warning(f"   Pollinations 异常: {e}")
    return None


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def generate_stone_images(prompts: list[dict], story_seed: int = 42) -> dict[int, str]:
    """
    批量生成石头绘本图片。

    Args:
        prompts: [{"index": 0, "prompt": "...", "text": "故事文字"}, ...]
        story_seed: 种子，同一故事复用保持风格一致

    Returns:
        {index: local_path}  图片路径映射
    """
    cache = _load_index()
    results: dict[int, str] = {}
    total = len(prompts)
    fallback_order = [
        ("CloudBase", _generate_cloudbase),
        ("SiliconFlow", _generate_siliconflow),
        ("Cloudflare", _generate_cloudflare),
        ("Pollinations", _generate_pollinations),
    ]

    for p in prompts:
        idx = p["index"]
        prompt_text = p["prompt"]
        cache_key = _md5(prompt_text)

        # 检查缓存
        if cache_key in cache:
            cached_path = cache[cache_key]
            if os.path.exists(cached_path):
                logger.info(f"   [{idx+1}/{total}] 缓存命中")
                results[idx] = cached_path
                continue

        # 尝试各 API 生图
        for api_name, api_func in fallback_order:
            image_seed = (story_seed + idx * 7) % 4294967295  # 每个场景不同种子
            path = api_func(prompt_text, seed=image_seed)
            if path:
                cache[cache_key] = path
                results[idx] = path
                break

        if idx not in results:
            logger.error(f"   [{idx+1}/{total}] 所有 API 均失败: {prompt_text[:60]}...")

    _save_index(cache)
    return results
