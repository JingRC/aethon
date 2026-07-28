"""山海经外卖 — 漫画章节生成器 v3"""
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

# Find chapter info
ch_info = {"title": f"第{ch_num}章", "desc": "继续送餐"}
vol_title = ""
for vol in arc.get("volumes", []):
    for ch in vol.get("chapters_detail", vol.get("chapters", [])):
        if ch["num"] == ch_num:
            ch_info = ch
            vol_title = vol["title"]
            break

prev_ctx = ""
if prev:
    prev_ctx = "\n".join(f"第{n}章：{i.get('summary','')}" for n, i in sorted(prev.items()))

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
elif json_path.exists():
    ans = input(f"已有剧本，复用？[Y/n] ").strip().lower()
    if not ans or ans == "y":
        chapter = json.loads(open(json_path, encoding="utf-8").read())

if not chapter:
    print("🤖 DeepSeek 生成剧本...")

    CHEN = "a young Chinese delivery rider, 24, tired eyes, yellow Meituan jacket, deadpan expression, realistic anime style"
    SCENE = "modern Chinese city at night, neon-lit alleyways, wet pavement, hidden magical doorways"

    # Chapter-specific beat sheets
    if ch_num == 1:
        beat = """第1章16页节奏表：
1-2页：雨夜。陈默接单。订单详情特写：收货地址=废弃电话亭第三格。客户=穷奇。订单=素食麻辣拌，变态辣。备注=敢放香菜老子吃了你。（划掉）揍你。
3-4页：找到电话亭。门拉开——不是电话亭内部，是另一个空间。虎身双翼的巨兽蜷在里面等外卖。
5-6页：穷奇冲出来。陈默没跑。穷奇：你不怕？陈默：怕。但你已经下单了。先确认收货。
7-8页：穷奇吃麻辣拌。变人形。坐在电话亭门口。陈默站在旁边等确认收货。两人沉默。穷奇：你为什么不尖叫。陈默：累了。
9-10页：穷奇：你是第一个看到我不跑的人类。陈默：你是第一个给我50元小费的客户。穷奇愣住。然后大笑。
11-12页：离开前陈默问：你住的地方只有你能进？穷奇指向电话亭——门上浮现四个字：山海入口。穷奇：你们人类也有能看见的。很少。你是一个。
13-14页：回程路上。手机弹出「山海专送App」——退不掉。删不了。永久在线。37客户头像：虎蛇鸟龙猪……
15-16页：叮。新订单。收货人：饕餮。内容：五十人份。备注：快。饿。四个字。陈默揉了揉太阳穴。骑入雨夜。"""
    elif ch_num == 2:
        beat = """第2章16页节奏表：穷奇上次打了三星评价——因为包装盒没摆正。陈默冲到武馆。把外卖袋拍桌上：免单。改五星。穷奇愣住。不是不敢打——是从来没人敢跟穷奇讨价还价。两人对峙→陈默：我可以永远不接你的单→穷奇：……你赢了→改五星。附言：这个人类不怎么样。但他没跑。还行。结尾：系统提示「穷奇已成为您的固定客户」。"""
    elif ch_num == 3:
        beat = """第3章16页节奏表：饕餮首单——五十人份。陈默跑五趟。每趟饕餮都在吃上一趟的。陈默以为一群人拼单。到了发现只有一个两百斤的胖子。五十个空碗。饕餮憨厚：不好意思啊小哥，我就是饿得快。陈默沉默三秒。在备注栏手写：此客户第一单优先送。结尾钩子：次日饕餮又下单了。六十人份。备注：昨天没吃饱。"""
    elif 4 <= ch_num <= 7:
        beat = f"""第{ch_num}章：引入新角色/新规则。每章必须有一个新神兽彩蛋。节奏比前三章稍缓但结尾必须有钩子。剧情方向：{ch_info.get('desc','')}"""
    else:
        beat = f"""第{ch_num}章：主线推进。推动猎兽人剧情的同时保持单元剧趣味。剧情方向：{ch_info.get('desc','')}"""

    prompt = f"""漫画编剧。创作《山海经外卖》第{ch_num}章。{max_pages}页正文+1封面。只返回JSON。

世界：2026年，隐藏世界与人类世界重叠。山海异兽化人生活千年。异兽化人后法力弱，不能传送不能变食物——会点外卖。隐藏入口藏城市角落。外卖平台有隐藏分区「山海专送」。陈默手机Bug让他能接隐藏订单。
前情：{prev_ctx if prev_ctx else "第1章"}

## 剧本节奏（严格遵循）
{beat}

## 角色性格
穷奇（凶兽/格斗教练）：暴躁嘴臭护短。戒了吃人。对香菜有病态执着。每句话都在骂人但动作很温柔。
陈默（外卖骑手）：话少到极致。口头禅\"好的\"\"嗯\"\"行\"。不是冷漠——是社恐+累了。每个离谱反应都用死鱼眼回应。

## 必须做到
1. 陈默每句≤12字。穷奇每句≤20字。narration全章≤3处。
2. 笑点来自：穷奇暴躁+陈默面瘫=穷奇更暴躁
3. 结尾留钩子——让人想立刻翻下一章
4. {max_pages}页正文，不能少

## 画面
陈默：\"{CHEN}\" | 场景：\"{SCENE}\" | 穷奇原型虎身双翼，人形壮汉虎牙 | 隐藏入口打开后是异维空间

## JSON
{{"title":"第{ch_num}章标题","headline":"封面4-8字","subtitle":"好奇钩子","hashtags":["#山海经外卖"],"pages":[{{"layout":"splash","panels":[{{"image_prompt":"{CHEN} ...","narration":null,"dialogue":"≤18字","sfx":"叮","speaker":"left"}}]}}]}}
{max_pages}页 | panels=layout对应数 | 不连续3页同布局"""

    resp = call_llm(prompt, config,
        system_prompt="漫画编剧。故事好笑有钩子。只返回JSON。",
        max_tokens=16384)
    print(f"   LLM返回{len(resp)}字符")

    chapter = parse_json_response(resp)
    if isinstance(chapter, list): chapter = chapter[0] if chapter else {}
    if not chapter or "pages" not in chapter:
        print(f"❌ 解析失败\n{resp[:500]}")
        Path("docs/shanhai_debug.txt").write_text(resp, encoding="utf-8")
        sys.exit(1)
    json_path.write_text(json.dumps(chapter, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📝 已保存:{json_path}")

pages = chapter.get("pages", [])
total_panels = sum(len(p.get("panels", [])) for p in pages)
print(f"   标题:{chapter.get('title','?')}  页数:{len(pages)}/{max_pages}  格数:{total_panels}")
if len(pages) < max_pages: print(f"   ⚠️ 只有{len(pages)}页！应该{max_pages}页")

preview = script_dir / f"shanhai_ch{ch_num:02d}.html"
from modules.manga_preview import generate_preview_html
generate_preview_html(chapter, ch_num, preview)
print(f"🌐 预览:{preview}")
webbrowser.open(preview.resolve().as_uri())

print(f"\n预计生图{total_panels}张≈{total_panels*15//60}分钟")
ans = input("确认生成？[Y/n] ").strip().lower()
if ans and ans != "y": print("取消。--resume续跑"); sys.exit(0)

chapter = json.loads(open(json_path, encoding="utf-8").read())
print("\n🎨 生图+渲染...")
from modules.manga_cards import render_manga_chapter
paths = render_manga_chapter(chapter, chapter_num=ch_num, output_dir="docs/xhs", category="山海经外卖")

print(f"\n✅ 第{ch_num}章完成 {len(paths)}张")
for p in paths: print(f"   {Path(p).name} ({os.path.getsize(p)/1024/1024:.1f}MB)")
print(f"\n📂 {Path(paths[0]).parent}")

s = input("\n摘要：").strip()
if not s: s = ch_info.get('desc','')[:60]
prev[str(ch_num)] = {"title": chapter.get("title",""), "summary": s}
sum_file.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
ch_file.write_text(str(ch_num + 1))
print(f"\n🎉 第{ch_num}章→{ch_num+1}")
