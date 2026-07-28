"""
AI 生图右下角水印去除（混合算法）

1. 中值滤波 → 干净背景参考
2. 检测原图与参考的差异 → 精确定位水印文字
3. 仅替换被检测到水印的像素，保留背景纹理
4. 注入微量噪声避免平滑痕迹

来源：D:\视频生成工作流\workflow\agents\media_agent.py _remove_watermark
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def remove_watermark(image_path: str | Path, region_w: int = 600, region_h: int = 150) -> bool:
    """去除图片右下角水印（原地修改）。返回 True 表示成功。"""
    image_path = Path(image_path)
    if not image_path.exists():
        return False

    try:
        import cv2
        import numpy as np

        # imdecode 避免 Windows Unicode 路径问题
        data = image_path.read_bytes()
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return False

        h, w = img.shape[:2]
        if w < region_w + 20 or h < region_h + 20:
            return False  # 图片太小

        x1 = w - region_w
        y1 = h - region_h
        region = img[y1:h, x1:w].copy()

        # 1. 中值滤波 → 干净背景参考
        clean_ref = cv2.medianBlur(region, 15)

        # 2. 检测差异 → 水印文字
        diff = cv2.absdiff(region, clean_ref)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

        _, bright_text = cv2.threshold(gray_diff, 8, 255, cv2.THRESH_BINARY)
        _, subtle_text = cv2.threshold(gray_diff, 5, 255, cv2.THRESH_BINARY)

        kernel = np.ones((3, 3), np.uint8)
        bright_expanded = cv2.dilate(bright_text, kernel, iterations=3)
        text_mask = cv2.bitwise_and(subtle_text, bright_expanded)
        text_mask = cv2.dilate(text_mask, kernel, iterations=1)

        text_px = (text_mask > 0).sum()
        if text_px < 10:
            return False  # 没检测到水印

        # 3. Alpha 混合替换
        mask_float = text_mask.astype(np.float32) / 255.0
        mask_float = cv2.GaussianBlur(mask_float, (3, 3), 1)
        mask_3ch = np.stack([mask_float] * 3, axis=2)

        region_cleaned = (
            region * (1 - mask_3ch) + clean_ref * mask_3ch
        ).astype(np.uint8)

        # 4. 微量噪声
        rng = np.random.default_rng(abs(hash(image_path.stem)) % (2 ** 31))
        noise = rng.normal(0, 2.5, region_cleaned.shape).astype(np.float32)
        noise_strength = mask_3ch[:, :, 0] * 0.2
        region_final = np.clip(
            region_cleaned.astype(np.float32) + noise * noise_strength[:, :, np.newaxis],
            0, 255,
        ).astype(np.uint8)

        result = img.copy()
        result[y1:h, x1:w] = region_final

        _, buf = cv2.imencode(".png", result)
        image_path.write_bytes(buf.tobytes())
        logger.info(f"   🧹 水印已去除")
        return True

    except ImportError:
        logger.debug("   opencv-python 未安装，跳过水印去除")
        return False
    except Exception as e:
        logger.warning(f"   去水印失败: {e}")
        return False
