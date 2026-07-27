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

    story_arc_prompt = f"""你是少年漫画编剧。为《小道士下山记》创作第{chapter_num}章。

## 你的唯一目标
让读者一口气翻完16页，然后骂你"怎么在这断了？！"
不需要讲道理。不需要温馨。只需要爽。

## 🚫 绝对禁止
- 旁白框超过每章3个。用画面讲故事，不用文字解释
- "我懂了""师父说过""原来是这样"——删掉
- 大段独白。每格对话 ≤18字
- 磨蹭。关键角色必须在5页内出场

## 🔥 必须做到
- 第1格就砸出一个大事件或大疑问
- 对话像真人说话：嘴硬、吐槽、说一半咽回去
- 笑点来自角色的性格缺陷和意外反应
- 每3页至少一个让人想截屏的格子
- 结尾留一句让人抓狂的台词

## 系列信息
简介：{arc.get('tagline','')}
卷名：{volume_title}
本章：{current_arc_info['title']}
剧情方向：{current_arc_info['theme']}
页数：{max_pages} 正文 + 1 封面

## 前情
{previous_context if previous_context else "第1章：故事开始"}

## 角色
- 明心 ♂15：嘴硬爱哭运气差。但不是废物——他有一种"用最笨的办法做最对的事"的天赋
- 师父 ♂60+：第1章开头就失踪了。只留一张纸条和一堆谜团
- 阿九 ♀16（{chapter_num}>=3出场）：字灵师。毒舌。战力是本作天花板。不知道为什么盯上了小道士
- 剑客 ♂25（{chapter_num}>=8出场）：不说话。出现时已经在队伍里了。没人记得他什么时候开始跟着的

## 排版（不要连续3页同一布局）
splash=1(开篇/高潮) half=2(对话对峙) trio=3(连续) grid4=4(叙事) cinema=4(全景→细节) stack=4(主+反应) grid5=5(混战)

## 每格画面（英文）
以 "{MC}" 开头。描述场景+动作+表情+镜头+光线。

## 返回 JSON
{{
  "title": "第{chapter_num}章 · 吸睛标题",
  "headline": "封面字 4-8字",
  "subtitle": "一句悬念",
  "hashtags": ["#小道士下山记","#原创漫画","#国风动漫"],
  "pages": [
    {{
      "layout": "splash",
      "panels": [{{
        "image_prompt": "{MC} ...",
        "narration": null,
        "dialogue": "对话 ≤18字",
        "sfx": "啪！",
        "speaker": "left"
      }}]
    }}
  ]
}}
{max_pages} 页 | panels 数量匹配 layout | narration 一页最多用一次 | 优先用 dialogue 不是 narration"""

    manga_response = call_llm(
        story_arc_prompt, config,
        system_prompt="你是少年漫画编剧。不需要讲道理，只需要让读者翻到最后一页骂你怎么断了。只返回JSON。",
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
