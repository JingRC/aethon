"""
石头禅修 — AI 图像生成模块

调用 CloudBase 云函数 ai-proxy（混元生图，10万张免费额度），
失败自动 fallback 到 SiliconFlow / Cloudflare / Pollinations。
生成图片以 MD5(prompt+seed) 缓存到 .image_cache/。
支持并行生图（ThreadPoolExecutor），大幅缩短流水线耗时。
"""

import hashlib
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "docs" / "xhs" / ".image_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
INDEX_PATH = CACHE_DIR / "stone_index.json"

# ── 并行生图配置 ──
MAX_WORKERS = int(os.environ.get("STONE_IMAGE_WORKERS", "4"))

# ── 缓存线程锁 ──
_cache_lock = threading.Lock()

# ── API 配置（从环境变量读取，兼容 GitHub Actions Secrets）──
CLOUDBASE_ENV = os.environ.get("CLOUDBASE_ENV", "")
CLOUDBASE_API_KEY = os.environ.get("CLOUDBASE_API_KEY", "")

# Fallback APIs
SILICONFLOW_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
CLOUDFLARE_ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
POLLINATIONS_KEY = os.environ.get("POLLINATIONS_API_KEY", "")


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _cache_key(prompt: str, seed: int) -> str:
    """缓存 key = MD5(prompt + seed)，避免同 prompt 不同 seed 碰撞。"""
    return _md5(f"{prompt}|{seed}")


def _load_index() -> dict:
    with _cache_lock:
        if INDEX_PATH.exists():
            try:
                return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}


def _save_index(idx: dict) -> None:
    with _cache_lock:
        INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


def _validate_image(path: Path) -> bool:
    """校验图片文件头 magic bytes，过滤错误占位图。"""
    try:
        if path.stat().st_size < 2048:
            return False
        header = path.read_bytes()[:16]
        # PNG: 89 50 4E 47
        if header[:4] == b'\x89PNG':
            return True
        # JPEG: FF D8 FF
        if header[:2] == b'\xff\xd8':
            return True
        # WebP: RIFF....WEBP
        if header[:4] == b'RIFF' and len(header) >= 12 and header[8:12] == b'WEBP':
            return True
        # BMP
        if header[:2] == b'BM':
            return True
        return False
    except OSError:
        return False


# ═══════════════════════════════════════════════════════════
# Primary: CloudBase 云函数（混元生图）
# ═══════════════════════════════════════════════════════════

CLOUDBASE_TIMEOUT = int(os.environ.get("CLOUDBASE_TIMEOUT", "300"))  # 默认 5 min
CLOUDBASE_RETRIES = 1  # 首次失败后重试 1 次


def _generate_cloudbase(prompt: str, seed: int = None, size: str = "1024x1024") -> dict | None:
    """调用微信小程序云函数 ai-image 生图（混元 3.0，10万张免费额度）。

    Returns:
        {"path": str, "source": "cloudbase"} 或 None
    """
    if not CLOUDBASE_ENV or not CLOUDBASE_API_KEY:
        logger.debug("CloudBase 未配置，跳过")
        return None

    url = f"https://{CLOUDBASE_ENV}.api.tcloudbasegateway.com/v1/functions/ai-image/invoke"
    payload: dict = {
        "prompt": prompt,
        "size": size,
        "revise": False,       # 关闭改写，保持英文 prompt 的角色一致性
        "thinking": False,
    }
    if seed is not None:
        payload["seed"] = seed

    last_error = None
    for attempt in range(1 + CLOUDBASE_RETRIES):
        try:
            r = requests.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {CLOUDBASE_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=CLOUDBASE_TIMEOUT,
            )
            data = r.json()

            if data.get("success") and data.get("image_url"):
                img_url = data["image_url"]
                retry_tag = " [retry]" if attempt > 0 else ""
                logger.info(f"   CloudBase混元 ✓ ({r.elapsed.total_seconds():.1f}s){retry_tag}")

                ir = requests.get(img_url, timeout=60)
                if ir.status_code == 200:
                    cache_key = _cache_key(prompt, seed or 0)
                    ext = ".png"
                    content_type = ir.headers.get("content-type", "")
                    if "jpeg" in content_type or "jpg" in content_type:
                        ext = ".jpg"
                    elif "webp" in content_type:
                        ext = ".webp"
                    cache_path = CACHE_DIR / f"stone_{cache_key}{ext}"
                    cache_path.write_bytes(ir.content)

                    if _validate_image(cache_path):
                        return {"path": str(cache_path), "source": "cloudbase"}
                    else:
                        logger.warning("   CloudBase 图片校验失败（文件头异常）")
                        cache_path.unlink(missing_ok=True)
                        return None
                else:
                    logger.warning(f"   CloudBase 图片下载失败: HTTP {ir.status_code}")
            else:
                err = data.get("error", data.get("message", "unknown"))[:150]
                logger.warning(f"   CloudBase 返回失败{retry_tag if attempt > 0 else ''}: {err}")
                last_error = err
        except requests.Timeout:
            logger.warning(f"   CloudBase 超时 ({CLOUDBASE_TIMEOUT}s){retry_tag if attempt > 0 else ''}")
            last_error = "timeout"
        except requests.RequestException as e:
            logger.warning(f"   CloudBase 网络异常: {e}{retry_tag if attempt > 0 else ''}")
            last_error = str(e)
        except Exception as e:
            logger.warning(f"   CloudBase 异常: {e}")
            last_error = str(e)

        if attempt < CLOUDBASE_RETRIES:
            time.sleep(3)

    logger.error(f"   CloudBase 最终失败 ({1 + CLOUDBASE_RETRIES} 次尝试): {last_error}")
    return None


# ═══════════════════════════════════════════════════════════
# Fallback 1: SiliconFlow（100张/天）
# ═══════════════════════════════════════════════════════════

def _generate_siliconflow(prompt: str, seed: int = None) -> dict | None:
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
                cache_key = _cache_key(prompt, seed or 0)
                cache_path = CACHE_DIR / f"stone_{cache_key}.png"
                cache_path.write_bytes(ir.content)
                if _validate_image(cache_path):
                    return {"path": str(cache_path), "source": "siliconflow"}
                cache_path.unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"   SiliconFlow 异常: {e}")
    return None


# ═══════════════════════════════════════════════════════════
# Fallback 2: Cloudflare Workers AI（900张/天）
# ═══════════════════════════════════════════════════════════

def _generate_cloudflare(prompt: str, seed: int = None) -> dict | None:
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
            cache_key = _cache_key(prompt, seed or 0)
            cache_path = CACHE_DIR / f"stone_{cache_key}.png"
            cache_path.write_bytes(r.content)
            if _validate_image(cache_path):
                return {"path": str(cache_path), "source": "cloudflare"}
            cache_path.unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"   Cloudflare 异常: {e}")
    return None


# ═══════════════════════════════════════════════════════════
# Fallback 3: Pollinations.ai（免费无限，无需 API Key）
# ═══════════════════════════════════════════════════════════

def _generate_pollinations(prompt: str, seed: int = None) -> dict | None:
    """Pollinations.ai，免费无限，POST 避免 URL 长度限制。"""
    try:
        payload = {
            "prompt": prompt,
            "width": 1024,
            "height": 1024,
            "nologo": True,
            "model": "flux",
        }
        if seed is not None:
            payload["seed"] = seed

        # POST（更稳定，无 URL 长度限制）
        r = requests.post(
            "https://image.pollinations.ai/prompt",
            json=payload,
            timeout=120,
        )
        if r.status_code == 200 and len(r.content) > 5000:
            logger.info(f"   Pollinations ✓ ({r.elapsed.total_seconds():.1f}s)")
            cache_key = _cache_key(prompt, seed or 0)
            cache_path = CACHE_DIR / f"stone_{cache_key}.png"
            cache_path.write_bytes(r.content)
            if _validate_image(cache_path):
                return {"path": str(cache_path), "source": "pollinations"}
            cache_path.unlink(missing_ok=True)
            return None

        # 回退 GET
        import urllib.parse
        encoded = urllib.parse.quote(prompt[:400])
        seed_param = f"&seed={seed}" if seed else ""
        img_url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1024&height=1024&nologo=true{seed_param}"
        )
        r2 = requests.get(img_url, timeout=120)
        if r2.status_code == 200 and len(r2.content) > 5000:
            logger.info(f"   Pollinations(GET) ✓ ({r2.elapsed.total_seconds():.1f}s)")
            cache_key = _cache_key(prompt, seed or 0)
            cache_path = CACHE_DIR / f"stone_{cache_key}.png"
            cache_path.write_bytes(r2.content)
            if _validate_image(cache_path):
                return {"path": str(cache_path), "source": "pollinations"}
            cache_path.unlink(missing_ok=True)
            return None

        logger.warning(f"   Pollinations 返回异常: POST={r.status_code}, GET={r2.status_code}")
    except Exception as e:
        logger.warning(f"   Pollinations 异常: {e}")
    return None


# ═══════════════════════════════════════════════════════════
# Fallback 链定义（按质量排序）
# ═══════════════════════════════════════════════════════════

FALLBACK_CHAIN = [
    ("CloudBase", _generate_cloudbase),       # 混元 3.0，质量最好
    ("SiliconFlow", _generate_siliconflow),   # FLUX.1-schnell
    ("Cloudflare", _generate_cloudflare),     # FLUX Schnell
    ("Pollinations", _generate_pollinations), # 质量最不稳定，放最后
]

# CloudBase 混元不带水印，免去处理
WATERMARK_FREE_SOURCES = {"cloudbase"}


def _generate_one(
    prompt: str,
    seed: int,
    page_index: int,
    total: int,
    cache: dict,
) -> tuple[int, str | None]:
    """
    单页生图（线程安全，供 ThreadPoolExecutor 调用）。

    依次尝试 FALLBACK_CHAIN 中的 API，首个成功即返回。

    Returns:
        (page_index, local_path_or_None)
    """
    ck = _cache_key(prompt, seed)

    # ── 缓存命中 ──
    if ck in cache and os.path.exists(cache[ck]):
        logger.info(f"   [{page_index+1}/{total}] 缓存命中")
        return (page_index, cache[ck])

    # ── 遍历 API 链 ──
    for api_name, api_func in FALLBACK_CHAIN:
        result = api_func(prompt, seed=seed)
        if result:
            path = result["path"]
            source = result.get("source", "")

            # 非混元来源可能需要去水印
            if source.lower() not in WATERMARK_FREE_SOURCES:
                try:
                    from modules.watermark_remover import remove_watermark
                    remove_watermark(path)
                except Exception:
                    pass

            return (page_index, path)

    logger.error(f"   [{page_index+1}/{total}] 所有 API 均失败: {prompt[:80]}...")
    return (page_index, None)


def _make_seed(story_seed: int, idx: int) -> int:
    """基于故事种子 + 页索引生成分散的图片种子。

    使用 Knuth 乘法哈希（黄金比例倒数 2654435761），
    确保相邻页种子差异大，避免生成结果趋同。
    """
    return (story_seed ^ (idx * 2654435761)) % 4294967295


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def generate_stone_images(prompts: list[dict], story_seed: int = 42) -> dict[int, str]:
    """
    批量生成石头绘本图片（并行）。

    Args:
        prompts: [{"index": 0, "prompt": "...", "text": "故事文字"}, ...]
        story_seed: 种子，同一故事复用保持风格一致

    Returns:
        {index: local_path}  图片路径映射
    """
    cache = _load_index()
    results: dict[int, str] = {}
    total = len(prompts)

    if total == 0:
        return results

    # ── 预计算每页的 seed 和 cache_key ──
    page_meta: dict[int, tuple[str, int, str]] = {}
    # page_index -> (prompt, seed, cache_key)

    for p in prompts:
        idx = p["index"]
        prompt_text = p["prompt"]
        seed = _make_seed(story_seed, idx)
        ck = _cache_key(prompt_text, seed)
        page_meta[idx] = (prompt_text, seed, ck)

    # ── 缓存命中检查 ──
    uncached: list[int] = []
    for idx, (prompt_text, seed, ck) in page_meta.items():
        if ck in cache and os.path.exists(cache[ck]):
            logger.info(f"   [{idx+1}/{total}] 缓存命中 ✓")
            results[idx] = cache[ck]
        else:
            uncached.append(idx)

    if not uncached:
        logger.info(f"   全部命中缓存 ({total}/{total})")
        return results

    logger.info(f"🖼️  并行生图: {len(uncached)}/{total} 张 (max_workers={MAX_WORKERS})")

    # ── 并行生成（手动管理线程池，防止死锁）──
    executor = ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(uncached)))
    try:
        futures = {}
        for idx in uncached:
            prompt_text, seed, ck = page_meta[idx]
            future = executor.submit(
                _generate_one,
                prompt=prompt_text,
                seed=seed,
                page_index=idx,
                total=total,
                cache=cache,
            )
            futures[future] = (idx, ck)

        for future in as_completed(futures):
            idx, ck = futures[future]
            try:
                pg_idx, path = future.result()
                if path:
                    cache[ck] = path
                    results[pg_idx] = path
                else:
                    logger.error(f"   第 {pg_idx+1} 页生图失败")
            except Exception as e:
                logger.error(f"   并行任务异常 (idx={idx}): {e}")

    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    _save_index(cache)
    logger.info(f"   完成: {len(results)}/{total} 张")
    return results
