"""本地跑小道士下山记漫画 — 一次一章，手动控制"""
import os, sys, json, io
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 加载环境变量
from pathlib import Path
env_file = Path("D:/视频生成工作流/.env")
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())
    print("✅ 环境变量已加载")

# 加载配置
from main import call_llm, parse_json_response
import yaml
config = yaml.safe_load(open("config.yml", encoding="utf-8"))
for key, val in config.get("llm", {}).items():
    if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
        config["llm"][key] = os.environ.get(val[2:-1], "")

manga_config = config.get("manga", {})
max_pages = manga_config.get("max_pages", 16)

# 本地脚本强制开启（不受 config.enabled 影响）
manga_config["enabled"] = True

# 读取章节号
chapter_file = Path("docs/manga_chapter.txt")
if chapter_file.exists():
    chapter_num = int(chapter_file.read_text().strip())
else:
    chapter_num = 1

print(f"\n📘 小道士下山记 — 第{chapter_num}章")
print(f"   最大页数: {max_pages}")
print(f"   生图引擎: CloudBase 混元")
print()

# 1. LLM 生成剧本
print("🤖 调用 DeepSeek 生成漫画剧本...")
from modules.manga_cards import build_manga_chapter_prompt
manga_prompt = build_manga_chapter_prompt(chapter_num, max_pages)
manga_response = call_llm(
    manga_prompt, config,
    system_prompt="你是漫画编剧，创作小道士下山记。只返回JSON格式。",
    max_tokens=16384,
)
manga_chapter = parse_json_response(manga_response)
if isinstance(manga_chapter, list):
    manga_chapter = manga_chapter[0] if manga_chapter else {}

if not manga_chapter or "pages" not in manga_chapter:
    print("❌ LLM 剧本生成失败！")
    sys.exit(1)

pages = manga_chapter.get("pages", [])
total_panels = sum(len(p.get("panels", [])) for p in pages)

print(f"   标题: {manga_chapter.get('title', '?')}")
print(f"   封面大字: {manga_chapter.get('headline', '?')}")
print(f"   页数: {len(pages)}")
print(f"   总格数: {total_panels}")
print()

# 预览剧本
print("📖 剧本预览:")
for i, page in enumerate(pages):
    layout = page.get("layout", "?")
    panels = page.get("panels", [])
    first_text = ""
    for p in panels:
        t = p.get("dialogue") or p.get("narration") or ""
        if t:
            first_text = t[:50]
            break
    print(f"   第{i+1}页 [{layout}·{len(panels)}格] {first_text}...")

# 2. 确认
print(f"\n⏳ 预计生图 {total_panels} 张 × ~15秒 ≈ {total_panels * 15 // 60} 分钟")
ans = input("开始生成？[Y/n] ").strip().lower()
if ans and ans != "y":
    print("已取消。")
    sys.exit(0)

# 3. 生图 + 渲染
print("\n🎨 生成漫画格图 + 渲染页面...")
from modules.manga_cards import render_manga_chapter
manga_paths = render_manga_chapter(
    manga_chapter,
    chapter_num=chapter_num,
    output_dir=manga_config.get("output_dir", "docs/xhs"),
    category=manga_config.get("category", "小道士下山"),
)

print(f"\n✅ 第{chapter_num}章完成！{len(manga_paths)} 张卡片")
for p in manga_paths:
    size_mb = os.path.getsize(p) / 1024 / 1024
    print(f"   {Path(p).name} ({size_mb:.1f} MB)")

print(f"\n📂 输出目录: {Path(manga_paths[0]).parent}")

# 4. 章节号 +1
chapter_file.write_text(str(chapter_num + 1))
print(f"📝 章节号已更新: {chapter_num} → {chapter_num + 1}")
print("   下次运行将生成下一章。")
