"""
小红书半自动发布脚本 — Playwright 浏览器自动化

用法：
    python modules/xhs_publish.py                     # 自动找最新日期
    python modules/xhs_publish.py --date 2026-07-17   # 指定日期
    python modules/xhs_publish.py --debug             # 调试模式（保存页面HTML）

流程：
  1. 读取 manifest.json → 2. 打开浏览器 → 3. 上传图片/填标题/正文/标签
  4. 等待用户审核 → 手动点击发布
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

XHS_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/imgNote"
PROFILE_DIR_NAME = ".aethon-xhs-profile"
MAX_IMAGES = 12
DEBUG_DIR = Path(__file__).resolve().parent.parent / ".xhs-debug"


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _get_profile_dir() -> Path:
    return _get_project_root() / PROFILE_DIR_NAME


# ── manifest ──────────────────────────────────────────


def find_latest_manifest(docs_dir: Path = None) -> Path | None:
    if docs_dir is None:
        docs_dir = _get_project_root() / "docs" / "xhs"
    manifests = sorted(docs_dir.glob("*/**/manifest.json"), reverse=True)
    return manifests[0] if manifests else None


def load_manifest(manifest_path: Path) -> dict:
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_cards(manifest: dict) -> list[Path]:
    project_root = _get_project_root()
    cards = manifest.get("cards", [])
    cover = None
    summary = None
    news_cards: list[Path] = []

    for card_path_str in cards:
        card_path = project_root / card_path_str
        if not card_path.exists():
            logger.warning(f"⚠️  跳过不存在的文件: {card_path}")
            continue
        filename = card_path.name
        if "cover" in filename.lower():
            cover = card_path
        elif "summary" in filename.lower():
            summary = card_path
        else:
            news_cards.append(card_path)

    result: list[Path] = []
    if cover:
        result.append(cover)
    result.extend(news_cards)
    if summary:
        result.append(summary)

    logger.info(f"📷 共 {len(result)} 张卡片")
    return result


# ── 调试工具 ──────────────────────────────────────────


def _dump_page_info(page, label: str = "page"):
    """保存页面 HTML 和所有 input/textarea 元素信息到文件。"""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%H%M%S")

    # 保存完整 HTML
    html_path = DEBUG_DIR / f"{label}_{timestamp}.html"
    html_path.write_text(page.content(), encoding="utf-8")
    logger.info(f"🔍 页面 HTML 已保存: {html_path}")

    # 提取所有可交互元素信息
    info = page.evaluate("""() => {
        const elements = [];
        // 遍历所有元素，不限制数量
        const all = document.querySelectorAll('input, textarea, [contenteditable="true"], button, [role="textbox"], [role="button"], select, label');
        all.forEach((el, i) => {
            const rect = el.getBoundingClientRect();
            elements.push({
                idx: i,
                tag: el.tagName,
                type: el.type || '',
                placeholder: el.placeholder || '',
                class: (el.className || '').toString().substring(0, 100),
                id: el.id || '',
                name: el.name || '',
                text: (el.textContent || '').substring(0, 80).replace(/\\s+/g, ' '),
                aria: el.getAttribute('aria-label') || '',
                role: el.getAttribute('role') || '',
                contenteditable: el.getAttribute('contenteditable') || '',
                accept: el.getAttribute('accept') || '',
                value: (el.value || '').substring(0, 40),
                visible: rect.width > 0 && rect.height > 0,
                pos: `${Math.round(rect.x)},${Math.round(rect.y)} ${Math.round(rect.width)}x${Math.round(rect.height)}`
            });
        });
        return elements;
    }""")

    info_path = DEBUG_DIR / f"{label}_{timestamp}.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"🔍 页面元素信息已保存: {info_path}")

    # 打印摘要（所有元素）
    for el in info:
        logger.info(
            f"   [{el['idx']}] <{el['tag']}> type={el['type']} "
            f"placeholder=\"{el['placeholder']}\" "
            f"class=\"{el['class'][:60]}\" id=\"{el['id']}\" "
            f"pos={el['pos']} vis={el['visible']}"
        )


# ── 浏览器自动化（增强版选择器） ──────────────────────


def _wait_page_ready(page, timeout: int = 15):
    """等待 SPA 页面完全渲染。"""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout * 1000)
    except Exception:
        pass
    time.sleep(3)  # 额外等待 React 渲染


def _find_file_input(page):
    """
    用 JS 在页面中定位文件上传 input。
    小红书通常有一个隐藏的 <input type="file" accept="image/*"> ，
    可能出现在顶层或 shadow DOM 中。
    """
    # 策略1：直接找所有 file input（包括隐藏的）
    file_inputs = page.locator('input[type="file"]')
    count = file_inputs.count()
    logger.info(f"🔍 找到 {count} 个 file input")

    if count > 0:
        # 优先选 accept 含 image 的
        for i in range(count):
            inp = file_inputs.nth(i)
            accept = inp.get_attribute("accept") or ""
            if "image" in accept:
                logger.info(f"   选中第 {i} 个 (accept={accept})")
                return inp
        # 都没有就选第一个
        logger.info(f"   使用第 0 个")
        return file_inputs.first

    # 策略2：检查 iframe
    frames = page.frames
    logger.info(f"🔍 页面有 {len(frames)} 个 frame")
    for frame in frames:
        fi = frame.locator('input[type="file"]')
        if fi.count() > 0:
            logger.info(f"   在 iframe 中找到 file input")
            return fi.first

    return None


def _upload_images(page, image_paths: list[Path]) -> bool:
    """上传图片。"""
    file_input = _find_file_input(page)
    if not file_input:
        logger.error("❌ 找不到图片上传控件")
        return False

    abs_paths = [str(p.resolve()) for p in image_paths]
    logger.info(f"📤 正在上传 {len(abs_paths)} 张图片...")
    for i, p in enumerate(abs_paths, 1):
        logger.info(f"   {i}/{len(abs_paths)}: {Path(p).name}")

    try:
        file_input.set_input_files(abs_paths)
        logger.info("✅ 图片上传完成")
        return True
    except Exception as e:
        logger.error(f"❌ 图片上传失败: {e}")
        return False


def _fill_title(page, title: str) -> bool:
    """填写标题。用 JS 找所有可见 input/textarea，选最像标题的那个。"""
    result = page.evaluate("""(titleText) => {
        // 找到所有可见文本输入元素
        const inputs = document.querySelectorAll(
            'input[type="text"], input:not([type]), textarea, [contenteditable="true"], [role="textbox"]'
        );
        for (const el of inputs) {
            const rect = el.getBoundingClientRect();
            if (rect.width < 50 || rect.height < 20) continue;
            const ph = (el.placeholder || '').toLowerCase();
            const cls = (el.className || '').toString().toLowerCase();
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            // 标题特征：placeholder/aria 含"标题"，或位置靠上
            if (ph.includes('标题') || aria.includes('标题') || cls.includes('title')) {
                el.focus();
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    el.value = '';
                } else {
                    el.textContent = '';
                }
                document.execCommand('insertText', false, titleText.substring(0, 20));
                return {found: true, tag: el.tagName, placeholder: el.placeholder || '', method: 'match'};
            }
        }
        // 回退：选第一个可见输入框
        for (const el of inputs) {
            const rect = el.getBoundingClientRect();
            if (rect.width < 200 || rect.height < 20) continue;
            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                el.focus(); el.value = '';
            }
            document.execCommand('insertText', false, titleText.substring(0, 20));
            return {found: true, tag: el.tagName, placeholder: el.placeholder || '', method: 'fallback'};
        }
        return {found: false};
    }""", title)

    if result.get("found"):
        logger.info(f"✅ 标题已填写 (tag={result['tag']} method={result['method']})")
        return True
    else:
        logger.warning("⚠️  找不到标题输入框")
        return False


def _fill_body(page, body: str) -> bool:
    """填写正文。小红书正文区通常是一个 contenteditable div。"""
    result = page.evaluate("""(bodyText) => {
        // 优先找 contenteditable
        const editors = document.querySelectorAll('[contenteditable="true"]');
        for (const el of editors) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 200 && rect.height > 60) {
                el.focus();
                el.textContent = '';
                document.execCommand('insertText', false, bodyText);
                return {found: true, tag: 'contenteditable', w: rect.width, h: rect.height};
            }
        }
        // 回退：找大的 textarea
        const textareas = document.querySelectorAll('textarea');
        for (const el of textareas) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 200 && rect.height > 60) {
                el.focus(); el.value = '';
                document.execCommand('insertText', false, bodyText);
                return {found: true, tag: 'textarea', w: rect.width, h: rect.height};
            }
        }
        // 再回退：找可见的大 div
        const divs = document.querySelectorAll('[role="textbox"], div[class*="editor"], div[class*="content"]');
        for (const el of divs) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 200 && rect.height > 60) {
                el.focus();
                document.execCommand('insertText', false, bodyText);
                return {found: true, tag: el.tagName, w: rect.width, h: rect.height};
            }
        }
        return {found: false};
    }""", body[:800])

    if result.get("found"):
        logger.info(f"✅ 正文已填写 ({result['tag']} {result['w']}x{result['h']})")
        return True
    else:
        logger.warning("⚠️  找不到正文输入区")
        return False


def _fill_hashtags(page, hashtags: list[str]) -> bool:
    """添加话题标签。找到标签输入框，逐个输入+回车。"""
    result = page.evaluate("""(tags) => {
        const inputs = document.querySelectorAll('input[type="text"], input:not([type])');
        let tagInput = null;
        for (const el of inputs) {
            const ph = (el.placeholder || '').toLowerCase();
            const cls = (el.className || '').toString().toLowerCase();
            if (ph.includes('话题') || ph.includes('标签') || ph.includes('tag') ||
                cls.includes('tag') || cls.includes('topic')) {
                tagInput = el;
                break;
            }
        }
        // 回退：找输入框里最靠下的那个（标签通常在正文下面）
        if (!tagInput) {
            let maxY = 0;
            for (const el of inputs) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 100 && rect.y > maxY && rect.y < 800) {
                    maxY = rect.y;
                    tagInput = el;
                }
            }
        }
        if (!tagInput) return {found: false};
        return {found: true, placeholder: tagInput.placeholder || '', y: tagInput.getBoundingClientRect().y};
    }""", hashtags)

    if not result.get("found"):
        logger.warning("⚠️  找不到标签输入框")
        return False

    # JS 找到了，现在用 Playwright 操作
    # 找个 placeholder 匹配的 input
    tag_input = None
    for sel in [
        'input[placeholder*="话题"]',
        'input[placeholder*="标签"]',
        'input[placeholder*="tag"]',
        'input[placeholder*="Tag"]',
    ]:
        el = page.locator(sel).first
        if el.count() > 0:
            tag_input = el
            break

    if not tag_input:
        # 回退：用 JS 定位的坐标点一下
        y = result.get("y", 500)
        page.mouse.click(600, y)
        time.sleep(0.5)
        tag_input = page.locator("input:focus").first
        if tag_input.count() == 0:
            tag_input = page.locator("input").last

    added = 0
    for tag in hashtags:
        tag = tag.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = f"#{tag}"
        try:
            tag_input.click()
            time.sleep(0.2)
            tag_input.fill("")
            tag_input.type(tag, delay=20)
            time.sleep(0.3)
            page.keyboard.press("Enter")
            time.sleep(0.4)
            added += 1
            logger.info(f"   🏷️  {tag}")
        except Exception as e:
            logger.warning(f"   ⚠️  {tag} 失败: {e}")

    if added:
        logger.info(f"✅ 已添加 {added} 个标签")
    return added > 0


def _wait_for_user_ready(page, debug: bool = False) -> bool:
    """等用户在浏览器中登录并就绪，按回车继续。"""
    print()
    print("=" * 60)
    print("  🔐 请在浏览器中完成登录")
    print("  登录成功后页面会自动跳到发布页")
    if debug:
        print("  （调试模式：登录后脚本将抓取页面结构并退出）")
    print()
    print("  👉 准备好了在终端按 Enter 继续...")
    print("=" * 60)
    print()
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        return False
    logger.info("✅ 用户确认就绪")
    return True


# ── 主入口 ────────────────────────────────────────────


def publish_xhs(
    date: str = None,
    category: str = None,
    headless: bool = False,
    debug: bool = False,
    profile_dir: Path = None,
) -> bool:
    project_root = _get_project_root()

    # ── 1. manifest ──
    manifest_path: Path | None = None
    if date:
        candidate = project_root / "docs" / "xhs" / date
        if category:
            candidate = candidate / category
        if candidate.exists():
            manifest_path = candidate / "manifest.json" if (candidate / "manifest.json").exists() else None
        if not manifest_path:
            matches = list((project_root / "docs" / "xhs" / date).glob("**/manifest.json"))
            manifest_path = matches[0] if matches else None
    else:
        manifest_path = find_latest_manifest()

    if not manifest_path:
        logger.error("❌ 找不到 manifest.json，请先运行 main.py")
        return False

    logger.info(f"📋 读取: {manifest_path}")
    manifest = load_manifest(manifest_path)

    title = manifest.get("title", "")
    body = manifest.get("body", "")
    hashtags = manifest.get("hashtags", [])

    logger.info(f"   标题: {title}")
    logger.info(f"   正文: {body[:60]}...")
    logger.info(f"   标签: {', '.join(hashtags)}")

    # ── 2. 图片 ──
    image_paths = select_cards(manifest)
    if not image_paths:
        logger.error("❌ 没有可用的卡片图片")
        return False

    # ── 3. 浏览器 ──
    profile_dir = profile_dir or _get_profile_dir()
    profile_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("❌ 需要: pip install playwright && playwright install chromium")
        return False

    logger.info(f"🌐 启动浏览器...")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
        )
        page = context.new_page()

        # ── 4. 打开创作者平台 ──
        page.goto("https://creator.xiaohongshu.com", wait_until="domcontentloaded", timeout=30000)

        # ── 5. 等待用户登录 ──
        _wait_for_user_ready(page, debug=debug)

        # ── 6. 导航到发布页，切换到「上传图文」tab ──
        logger.info("🔄 进入发布页...")

        # 直接导航到图片笔记发布页
        try:
            page.goto(XHS_PUBLISH_URL, wait_until="domcontentloaded", timeout=15000)
        except Exception as e:
            logger.warning(f"   导航异常（可忽略）: {e}")

        # 等待 SPA 渲染完成
        _wait_page_ready(page)

        # 小红书发布页默认选中「上传视频」，必须切换到「上传图文」
        # 才会渲染图片上传 input + 标题/正文/标签输入框
        # 注意：页面有两套 tab（无障碍隐藏副本 left:-9999px），用 JS 点击可见的那个
        try:
            clicked = page.evaluate("""() => {
                const tabs = document.querySelectorAll('.creator-tab');
                for (const tab of tabs) {
                    const span = tab.querySelector('.title');
                    if (span && span.textContent.trim() === '上传图文') {
                        const rect = tab.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && rect.x >= 0) {
                            tab.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            if clicked:
                time.sleep(2)
                logger.info("   ✅ 已切换到「上传图文」")
            else:
                logger.warning("   ⚠️  未找到可点击的「上传图文」tab")
        except Exception as e:
            logger.warning(f"   ⚠️  切换标签失败: {e}")

        # 等待图文上传 UI 渲染（图片 file input、标题、正文、标签等）
        _wait_page_ready(page)

        # ── 7. 调试 ──
        if debug:
            _dump_page_info(page, "loaded")
            logger.info("🔍 调试信息已保存到 .xhs-debug/，退出")
            context.close()
            return True

        # ── 8. 上传图片 ──
        if not _upload_images(page, image_paths):
            logger.warning("⚠️  图片自动上传失败，请手动上传")
        time.sleep(4)  # 等待上传完成 + 缩略图渲染

        # ── 9. 填写标题 ──
        _fill_title(page, title)
        time.sleep(0.5)

        # ── 10. 填写正文 ──
        _fill_body(page, body)
        time.sleep(0.5)

        # ── 11. 添加标签 ──
        _fill_hashtags(page, hashtags)
        time.sleep(0.5)

        # ── 12. 提示 ──
        print()
        print("=" * 60)
        print("  ✅ 小红书发布内容已全部填好！")
        print()
        print(f"  📌 标题: {title}")
        print(f"  📝 正文: {len(body)} 字")
        print(f"  🏷️  标签: {', '.join(hashtags)}")
        print(f"  🖼️  图片: {len(image_paths)} 张")
        print()
        print("  👆 请仔细审核内容，确认无误后点击「发布」按钮")
        print("  ⚠️  关闭浏览器窗口即可退出脚本")
        print("=" * 60)
        print()

        logger.info("⏳ 浏览器保持打开，等待你审核发布...")
        try:
            page.wait_for_event("close", timeout=600)
        except Exception:
            pass
        finally:
            context.close()

    return True


# ── CLI ───────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="小红书半自动发布")
    parser.add_argument("--date", "-d", help="日期 YYYY-MM-DD")
    parser.add_argument("--category", "-c", help="分类目录名")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--debug", action="store_true", help="调试模式：保存页面 HTML 到 .xhs-debug/")
    parser.add_argument("--profile-dir", help="浏览器 profile 目录")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    profile_dir = Path(args.profile_dir) if args.profile_dir else None

    success = publish_xhs(
        date=args.date,
        category=args.category,
        headless=args.headless,
        debug=args.debug,
        profile_dir=profile_dir,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
