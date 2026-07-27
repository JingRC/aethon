"""本地跑小道士下山记漫画 v3 — 爆款剧本 + HTML 预览 + 断点续跑"""
import os, sys, json, io, time, webbrowser
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path

# ── 加载环境变量 ──
env_file = Path("D:/视频生成工作流/.env")
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())
    print("✅ 环境变量已加载")

# ── 加载配置 ──
from main import call_llm, parse_json_response
import yaml
config = yaml.safe_load(open("config.yml", encoding="utf-8"))
for key, val in config.get("llm", {}).items():
    if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
        config["llm"][key] = os.environ.get(val[2:-1], "")

manga_config = config.get("manga", {})
max_pages = manga_config.get("max_pages", 16)

# ── 读取故事弧 ──
arc_path = Path("docs/manga_story_arc.json")
arc = json.loads(arc_path.read_text(encoding="utf-8"))

# ── 章节号 ──
chapter_file = Path("docs/manga_chapter.txt")
chapter_num = int(chapter_file.read_text().strip()) if chapter_file.exists() else 1

# ── 前情提要 ──
summaries_file = Path("docs/manga_summaries.json")
prev_summaries = json.loads(summaries_file.read_text(encoding="utf-8")) if summaries_file.exists() else {}

# ── 找当前章节故事弧 ──
current_arc_info = None
volume_title = ""
for vol in arc.get("volumes", []):
    for ch in vol.get("chapters", []):
        if ch["num"] == chapter_num:
            current_arc_info = ch
            volume_title = vol["title"]
            break

if not current_arc_info:
    current_arc_info = {"title": f"第{chapter_num}章", "theme": "继续小道士的旅程"}

previous_context = ""
if prev_summaries:
    previous_context = "\n".join(
        f"第{num}章《{info.get('title','')}》：{info.get('summary','')}"
        for num, info in sorted(prev_summaries.items())
    )

print(f"""
╔══════════════════════════════════╗
║  小道士下山记 · 第{chapter_num}章         ║
║  {volume_title}  ║
║  主题：{current_arc_info['title']}     ║
╚══════════════════════════════════╝
""")

# ═══════════════════ 检查已有脚本 ═══════════════════
today_str = time.strftime("%Y-%m-%d")
script_dir = Path(f"docs/manga_scripts/{today_str}")
script_dir.mkdir(parents=True, exist_ok=True)
json_path = script_dir / f"ch{chapter_num:02d}_script.json"

skip_llm = "--skip-llm" in sys.argv or "--resume" in sys.argv
manga_chapter = None

if skip_llm and json_path.exists():
    manga_chapter = json.loads(json_path.read_text(encoding="utf-8"))
    print(f"📂 复用已有剧本 ({len(manga_chapter.get('pages',[]))} 页)")
elif json_path.exists():
    ans = input(f"📂 已有剧本，复用？[Y/n] ").strip().lower()
    if not ans or ans == "y":
        manga_chapter = json.loads(json_path.read_text(encoding="utf-8"))
        print(f"   复用 ({len(manga_chapter.get('pages',[]))} 页)")

# ═══════════════════ LLM 生成剧本 ═══════════════════
if not manga_chapter:
    print("🤖 调用 DeepSeek 生成爆款剧本...")

    from modules.manga_cards import MANGA_CHARACTER as MC

    story_arc_prompt = f"""你是顶尖漫画编剧。为《小道士下山记》创作第{chapter_num}章。

## ⚠️ 绝对不要写的东西
❌ 温馨告别、师父叫弟子来、收拾行李、平静山门
❌ "师父说……""徒儿明白了……"这类模板化对话
❌ 每页都在讲道理——道理要藏在故事里，藏在角色的表情里
❌ 平淡的旁白——旁白要有态度，像在跟读者交头接耳

## ✅ 必须做到
✅ 第1页就要有钩子——让人想问"发生了什么？！"
✅ 每一页结尾制造翻页冲动
✅ 一章内情绪变化 ≥ 3 次（笑→紧张→感动→笑→期待）
✅ 结尾是钩子，不是总结。让读者想立刻看下一章
✅ 对话口语化、有个性。小道士不是复读机

## 系列信息
系列简介：{arc.get('tagline','')}
卷名：{volume_title}
本章标题：{current_arc_info['title']}
本章剧情方向：{current_arc_info['theme']}
页数：{max_pages} 页正文 + 1 封面

## 前情提要
{previous_context if previous_context else "（第1章：故事开始）"}

## 角色（本章按需出场）
- 小道士 明心 ♂15：机灵但不靠谱，逞强但爱哭，背得出一百条道理但每次都用错地方
- 师父 ♂60+：话极少，每句话要么是伏笔要么让你鼻子一酸。经典动作：闭眼喝茶，突然说一句戳穿一切的话
- 阿九 ♀16（第3章起出场）：字灵师，毒舌能打，骂小道士最凶但帮他也最拼
- 沉默剑客 ♂25（第8章起出场）：不说话，跟着蹭饭。不是高冷，是社恐

## 布局节奏
splash(1格)=开篇/高潮/收尾 · half(2格)=交锋 · trio(3格)=连续镜头
grid4(4格)=叙事 · cinema(4格)=大场面 · stack(4格)=主+反应 · grid5(5格)=混乱
不要连续3页同一布局

## 画面描述 image_prompt（英文）
以 "{MC}" 开头，重复角色描述保证一致。描述场景+动作+表情+镜头+光线。格间变化景别。

## 返回 JSON
{{
  "title": "第{chapter_num}章 · 有吸引力的标题",
  "headline": "封面大字 4-8字",
  "subtitle": "有悬念的一句话",
  "hashtags": ["#小道士下山记","#原创漫画","#国风动漫"],
  "pages": [
    {{
      "layout": "splash",
      "panels": [{{
        "image_prompt": "{MC} ...",
        "narration": "旁白（有态度的）",
        "dialogue": "对话",
        "sfx": "啪！",
        "speaker": "left"
      }}]
    }}
  ]
}}
规则：pages 恰好 {max_pages} 个 | panels 长度匹配 layout | 所有字段不能省略"""

    manga_response = call_llm(
        story_arc_prompt, config,
        system_prompt="你是顶尖漫画编剧。创作让人停不下来的故事。只返回JSON。",
        max_tokens=16384,
    )
    print(f"   LLM 返回 {len(manga_response)} 字符")

    manga_chapter = parse_json_response(manga_response)
    if isinstance(manga_chapter, list):
        manga_chapter = manga_chapter[0] if manga_chapter else {}

    if not manga_chapter or "pages" not in manga_chapter:
        print(f"❌ 解析失败！前500字:\n{manga_response[:500]}")
        Path("docs/manga_debug_response.txt").write_text(manga_response, encoding="utf-8")
        print("   原始响应已保存到 docs/manga_debug_response.txt")
        sys.exit(1)

    # 保存 JSON
    json_path.write_text(json.dumps(manga_chapter, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📝 剧本已保存: {json_path}")

pages = manga_chapter.get("pages", [])
total_panels = sum(len(p.get("panels", [])) for p in pages)

print(f"   标题: {manga_chapter.get('title', '?')}")
print(f"   封面大字: {manga_chapter.get('headline', '?')}")
print(f"   页数: {len(pages)} / 格数: {total_panels}")

# ═══════════════════ HTML 预览 ═══════════════════
preview_path = script_dir / f"ch{chapter_num:02d}_preview.html"
from modules.manga_preview import generate_preview_html
generate_preview_html(manga_chapter, chapter_num, preview_path)
print(f"🌐 预览: {preview_path}")
webbrowser.open(preview_path.resolve().as_uri())

# ═══════════════════ 确认 ═══════════════════
print(f"""
┌─────────────────────────────────────┐
│  预览页面已在浏览器中打开            │
│  如需修改：编辑 {json_path.name}     │
│  预计生图 {total_panels} 张 ≈ {total_panels * 15 // 60} 分钟           │
└─────────────────────────────────────┘
""")

ans = input("确认开始生图？[Y/n] ").strip().lower()
if ans and ans != "y":
    print("已取消。下次运行 --resume 可直接进入确认。")
    sys.exit(0)

# ═══════════════════ 生图 + 渲染 ═══════════════════
manga_chapter = json.loads(json_path.read_text(encoding="utf-8"))
print("\n🎨 生成漫画格图 + 渲染页面...")
from modules.manga_cards import render_manga_chapter
manga_paths = render_manga_chapter(
    manga_chapter, chapter_num=chapter_num,
    output_dir=manga_config.get("output_dir", "docs/xhs"),
    category=manga_config.get("category", "小道士下山"),
)

print(f"\n✅ 第{chapter_num}章完成！{len(manga_paths)} 张")
for p in manga_paths:
    print(f"   {Path(p).name} ({os.path.getsize(p)/1024/1024:.1f} MB)")
print(f"\n📂 {Path(manga_paths[0]).parent}")

# ═══════════════════ 保存摘要 ═══════════════════
summary = input("\n📝 一句话摘要（供后续章节参考）：").strip()
if not summary:
    summary = current_arc_info['theme'][:60]
prev_summaries[str(chapter_num)] = {"title": manga_chapter.get("title", ""), "summary": summary}
summaries_file.write_text(json.dumps(prev_summaries, ensure_ascii=False, indent=2), encoding="utf-8")
chapter_file.write_text(str(chapter_num + 1))

print(f"""
╔══════════════════════════════════╗
║  🎉 第{chapter_num}章 完成！→ 第{chapter_num+1}章      ║
║  下次: python run_manga.py      ║
╚══════════════════════════════════╝
""")
