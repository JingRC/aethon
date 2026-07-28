"""山海经外卖 — 漫画章节生成器 v2"""
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
    for ch in vol.get("chapters_detail", vol.get("chapters", [])):
        if ch["num"] == ch_num:
            ch_info = ch
            vol_title = vol["title"]
            break

if not ch_info:
    ch_info = {"title": f"第{ch_num}章", "desc": "继续送餐", "theme": "继续送餐"}

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

    CHEN_MO = (
        "a young Chinese delivery rider, 24 years old, tired but kind eyes, "
        "wearing a yellow Meituan delivery jacket and helmet, slightly messy black hair, "
        "deadpan expression, riding an electric scooter with a delivery box, "
        "realistic anime style, warm muted colors"
    )
    SCENE = (
        "modern Chinese city streets at dusk, narrow alleyways with neon signs, "
        "wet pavement reflecting streetlights, ordinary urban setting with subtle "
        "hints of hidden magical doorways in the background"
    )

    # Chapter-specific rules
    if ch_num == 1:
        ch_rules = """### 第1章 · 开篇高速
- 只出场：陈默 + 穷奇。其他角色不出现
- 节奏：第1格就接单，第2页看到穷奇原型（虎身双翼），第4页完成初次对峙
- 穷奇在废弃电话亭里现原形等外卖。陈默的反应：不是尖叫。是\"……好的。麻辣拌要不要加醋。\"
- 穷奇被淡定的人类整不会了：\"你……不怕我？\"陈默：\"怕。但你已经下单了。先确认收货。\"
- 结尾钩子：手机弹出\"穷奇给您打赏50元\" + 系统消息\"山海专送第1单完成。本分区共有37位客户。\"
- 不解释世界观。让世界通过陈默的眼睛展开。读者不需要知道所有规则——只需要知道：①手机能接隐藏订单 ②穷奇是凶兽但吃素 ③小费真的很多"""
    elif ch_num == 2:
        ch_rules = """### 第2章 · 快节奏冲突
- 穷奇打了三星。理由荒谬：\"包装盒没摆正\"
- 陈默冲到武馆。穷奇以为他要打架——结果陈默把外卖袋拍桌上：\"免单。改五星。\"
- 穷奇愣住。不是不敢打——是从来没人敢跟穷奇还价
- 两人交锋：穷奇说\"有本事打一架\"，陈默说\"我没本事。但我可以永远不接你的单。\"
- 结尾：穷奇改了五星。附加评价：\"这个人类不怎么样。但他没跑。还行。\""""
    elif ch_num == 3:
        ch_rules = """### 第3章 · 重量级客户
- 饕餮首次出场。五十人份订单。陈默跑五趟。每趟饕餮都在吃上一趟的东西
- 陈默以为是一群人拼单。到了发现只有一个两百斤的胖子。和五十个空碗
- 饕餮憨厚老实：\"不好意思啊小哥，我就是……饿得快。\"陈默沉默三秒。在备注里加三字：\"优先送\"
- 结尾钩子：次日饕餮又下单了。这次六十人份。备注：\"昨天没吃饱。\"陈默看着手机。揉了揉太阳穴"""
    elif 4 <= ch_num <= 7:
        ch_rules = """### 第4-7章 · 世界展开
- 引入九尾狐、伏羲废品站、应龙茶馆
- 每章必须有一个新的神兽彩蛋（相柳奶茶、毕方烧烤、天狗月饼、女娲黏土等）
- 节奏比前三章稍缓，但每章结尾必须有钩子
- 逐步揭示陈默的家庭背景和母亲病情"""
    else:
        ch_rules = """### 第8-17章 · 主线推进
- 猎兽人威胁逐渐升级
- 每章推动主线的同时保持单元剧趣味
- 最后一章收尾要有完结感+对第二部的期待"""

    prompt = f"""你是漫画编剧。创作《山海经外卖》第{ch_num}章。

## 世界观
{json.dumps(arc.get('world',{}), ensure_ascii=False)}

## 系列简介
{arc.get('tagline','')}
卷：{vol_title}
本章：{ch_info.get('title','')}
剧情方向：{ch_info.get('desc', ch_info.get('theme',''))}
页数：{max_pages} 页正文 + 1 封面

## 前情
{prev_ctx if prev_ctx else "第1章开始"}

## 角色
{json.dumps(arc.get('characters',{}), ensure_ascii=False)}

## ⚠️ 本章规则

{ch_rules}

### 叙事规则（通用）
- 每页 narration ≤1 个。用画面和对话推动故事
- 陈默说话：极度简短。\"好的。\"\"嗯。\"\"行。\"偶尔爆冷幽默
- 神兽说话：凶萌接地气，不像神兽像邻居
- 笑点公式：神兽的离谱需求 + 陈默死鱼眼 + 照做了 + 更离谱
- 每章展示一个山海世界新角落或新神兽
- 结尾留钩子——下一章开篇就是答案

## 画面
- 陈默前缀："{CHEN_MO}"
- 场景前缀："{SCENE}"
- 隐藏世界入口：普通物体（墙/电话亭/树）打开后是另一个维度
- 穷奇原型：虎身双翼。人形：壮汉虎牙。饕餮人形：微笑胖子。九尾狐人形：优雅美艳

## 排版
splash(1格)=开篇/高潮 half(2格)=对峙 trio(3格)=连续 grid4(4格)=叙事
cinema(4格)=全景 grid5(5格)=混乱 不连续3页同布局

## 返回JSON
{{
  "title": "第{ch_num}章 · 吸睛标题",
  "headline": "封面大字 4-8字",
  "subtitle": "一句话制造好奇",
  "hashtags": ["#山海经外卖","#原创漫画","#搞笑治愈","#国风奇幻"],
  "pages": [
    {{
      "layout": "splash",
      "panels": [{{
        "image_prompt": "{CHEN_MO} riding electric scooter, phone screen showing strange order, night city streets, {SCENE}",
        "narration": null,
        "dialogue": "对话 ≤18字",
        "sfx": "叮！",
        "speaker": "left"
      }}]
    }}
  ]
}}
{max_pages} 页 | panels 匹配 layout | narration ≤3 处全章 | 每句 ≤18字"""

    resp = call_llm(
        prompt, config,
        system_prompt="你是漫画编剧。创作好笑、有逻辑、有钩子的故事。只返回JSON。",
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

chapter = json.loads(open(json_path, encoding="utf-8").read())
print("\n🎨 生图+渲染...")
from modules.manga_cards import render_manga_chapter
paths = render_manga_chapter(chapter, chapter_num=ch_num, output_dir="docs/xhs", category="山海经外卖")

print(f"\n✅ 第{ch_num}章完成！{len(paths)} 张")
for p in paths:
    print(f"   {Path(p).name} ({os.path.getsize(p)/1024/1024:.1f} MB)")
print(f"\n📂 {Path(paths[0]).parent}")

s = input("\n📝 摘要：").strip()
if not s: s = ch_info.get('desc', ch_info.get('theme', ''))[:60]
prev[str(ch_num)] = {"title": chapter.get("title",""), "summary": s}
sum_file.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
ch_file.write_text(str(ch_num + 1))
print(f"\n🎉 第{ch_num}章完成 → 第{ch_num+1}章")
