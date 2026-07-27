"""山海经外卖 — 漫画章节生成器"""
import os, sys, json, io, time, webbrowser
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

env_file = Path("D:/视频生成工作流/.env")
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())
    print("✅ 环境已加载")

from main import call_llm, parse_json_response
import yaml
config = yaml.safe_load(open("config.yml", encoding="utf-8"))
for key, val in config.get("llm", {}).items():
    if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
        config["llm"][key] = os.environ.get(val[2:-1], "")

max_pages = 16
arc = json.loads(open("docs/shanhai_story_arc.json", encoding="utf-8").read())

ch_file = Path("docs/shanhai_chapter.txt")
ch_num = int(ch_file.read_text().strip()) if ch_file.exists() else 1

sum_file = Path("docs/shanhai_summaries.json")
prev = json.loads(sum_file.read_text(encoding="utf-8")) if sum_file.exists() else {}

ch_info = None
vol_title = ""
for vol in arc.get("volumes", []):
    for ch in vol.get("chapters", []):
        if ch["num"] == ch_num:
            ch_info = ch
            vol_title = vol["title"]
            break

if not ch_info:
    ch_info = {"title": f"第{ch_num}章", "theme": "继续送餐"}

prev_ctx = ""
if prev:
    prev_ctx = "\n".join(
        f"第{n}章《{i.get('title','')}》：{i.get('summary','')}"
        for n, i in sorted(prev.items())
    )

print(f"""
╔══════════════════════════════════╗
║  山海经外卖 · 第{ch_num}章             ║
║  {vol_title}        ║
║  {ch_info['title']}                ║
╚══════════════════════════════════╝
""")

today = time.strftime("%Y-%m-%d")
script_dir = Path(f"docs/manga_scripts/{today}")
script_dir.mkdir(parents=True, exist_ok=True)
json_path = script_dir / f"shanhai_ch{ch_num:02d}.json"

skip_llm = "--skip-llm" in sys.argv or "--resume" in sys.argv
chapter = None

if skip_llm and json_path.exists():
    chapter = json.loads(open(json_path, encoding="utf-8").read())
    print(f"📂 复用已有剧本 ({len(chapter.get('pages',[]))} 页)")
elif json_path.exists():
    ans = input(f"📂 已有剧本，复用？[Y/n] ").strip().lower()
    if not ans or ans == "y":
        chapter = json.loads(open(json_path, encoding="utf-8").read())

if not chapter:
    print("🤖 DeepSeek 生成剧本...")

    # ── 角色图像描述 ──
    CHEN_MO = (
        "a young Chinese delivery rider, 24 years old, tired but kind eyes, "
        "wearing a yellow Meituan delivery jacket and helmet, slightly messy black hair, "
        "deadpan expression, riding an electric scooter with a delivery box on the back, "
        "realistic anime style, warm muted colors"
    )
    SCENE = (
        "modern Chinese city at dusk, narrow streets and alleyways, "
        "neon signs reflecting on wet pavement, street food stalls, "
        "contrast between ordinary urban scenes and hidden magical doorways"
    )

    prompt = f"""你是漫画编剧。创作《山海经外卖》第{ch_num}章。

## 世界观
{json.dumps(arc.get('world',{}), ensure_ascii=False)}

## 系列简介
{arc.get('tagline','')}
卷：{vol_title}
本章：{ch_info['title']}
剧情方向：{ch_info['theme']}
页数：{max_pages} 页正文 + 1 封面

## 前情
{prev_ctx if prev_ctx else "第1章开始"}

## 角色
{json.dumps(arc.get('characters',{}), ensure_ascii=False)}

## ⚠️ 本章规则

### 第1章特殊规则
- 只出场：陈默 + 穷奇（第一个客户）。其他角色本章不出现
- 核心场景：陈默接单→发现地址诡异→硬着头皮去送→废弃电话亭→门开了→穷奇的世界→对话→离开→手机弹出"穷奇给您打赏50元"
- 不要塞太多信息。读者只需要知道三件事：①陈默的手机能接隐藏订单 ②第一个客户是穷奇 ③小费真的很多
- 穷奇的形象反差：凶兽的外形 + 素食用餐者 + 对香菜有执念 + 脾气暴躁但其实是在戒"吃人"上瘾
- 陈默的反应：从头到尾面无表情不是因为淡定——是因为还没消化。只在最后一格，他看着50元小费，眼睛微微睁大

### 叙事规则（通用）
- 每页最多1个 narration。用画面和对话推动
- 陈默的对话特点：简短、直接、偶尔黑色幽默
- 神兽的对话特点：凶萌、接地气、不像神兽像邻居
- 每章要展示一个山海世界的新角落
- 笑点来自：神兽的日常烦恼 + 陈默的死鱼眼反应
- 结尾留钩子

## 画面
- 陈默 image_prompt 前缀："{CHEN_MO}"
- 场景前缀："{SCENE}"
- 隐藏世界入口的视觉：普通的门/墙/电话亭，打开后是另一个维度的空间
- 穷奇化为人形时是壮汉（虎牙隐约可见），现原形时是虎身双翼

## 排版
splash=1格(开篇高潮) half=2格(对峙) trio=3格(连续) grid4=4格(叙事)
cinema=4格(全景→细节) grid5=5格(混乱)
不连续3页同布局

## 返回JSON
{{
  "title": "第{ch_num}章 · 吸睛标题",
  "headline": "封面大字 4-8字",
  "subtitle": "一句话制造好奇",
  "hashtags": ["#山海经外卖","#原创漫画","#搞笑治愈"],
  "pages": [
    {{
      "layout": "splash",
      "panels": [{{
        "image_prompt": "{CHEN_MO} riding electric scooter at night, phone mounted on handlebar showing a strange delivery order, curious expression, {SCENE}",
        "narration": null,
        "dialogue": "对话 ≤18字",
        "sfx": "叮！",
        "speaker": "left"
      }}]
    }}
  ]
}}
{max_pages} 页 | panels 匹配 layout | 全章 narration ≤3 处 | 每句 dialogue ≤18字"""

    resp = call_llm(
        prompt, config,
        system_prompt="你是漫画编剧。创作好笑、有逻辑、有温度的故事。只返回JSON。",
        max_tokens=16384,
    )
    print(f"   LLM 返回 {len(resp)} 字符")

    chapter = parse_json_response(resp)
    if isinstance(chapter, list):
        chapter = chapter[0] if chapter else {}

    if not chapter or "pages" not in chapter:
        print(f"❌ 解析失败！\n{resp[:500]}")
        Path("docs/shanhai_debug.txt").write_text(resp, encoding="utf-8")
        sys.exit(1)

    json_path.write_text(json.dumps(chapter, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📝 已保存: {json_path}")

pages = chapter.get("pages", [])
total_panels = sum(len(p.get("panels", [])) for p in pages)
print(f"   标题: {chapter.get('title','?')}")
print(f"   封面: {chapter.get('headline','?')}")
print(f"   页数: {len(pages)} / 格数: {total_panels}")

# ── 预览 ──
preview_path = script_dir / f"shanhai_ch{ch_num:02d}.html"
from modules.manga_preview import generate_preview_html
generate_preview_html(chapter, ch_num, preview_path)
print(f"🌐 预览: {preview_path}")
webbrowser.open(preview_path.resolve().as_uri())

print(f"""
┌─────────────────────────────────────┐
│  预览已打开。检查剧本。              │
│  修改: {json_path.name}              │
│  生图: ~{total_panels} 张 ≈ {total_panels*15//60} 分钟          │
└─────────────────────────────────────┘
""")

ans = input("确认生成？[Y/n] ").strip().lower()
if ans and ans != "y":
    print("已取消。--resume 可续跑。")
    sys.exit(0)

# ── 渲染 ──
chapter = json.loads(open(json_path, encoding="utf-8").read())
print("\n🎨 生图+渲染...")
from modules.manga_cards import render_manga_chapter
paths = render_manga_chapter(chapter, chapter_num=ch_num, output_dir="docs/xhs", category="山海经外卖")

print(f"\n✅ 第{ch_num}章完成！{len(paths)} 张")
for p in paths:
    print(f"   {Path(p).name} ({os.path.getsize(p)/1024/1024:.1f} MB)")
print(f"\n📂 {Path(paths[0]).parent}")

s = input("\n📝 摘要：").strip()
if not s: s = ch_info['theme'][:60]
prev[str(ch_num)] = {"title": chapter.get("title",""), "summary": s}
sum_file.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
ch_file.write_text(str(ch_num + 1))
print(f"\n🎉 第{ch_num}章完成 → 第{ch_num+1}章")
