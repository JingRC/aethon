"""山海经外卖 漫画生成器 v4 — 一键重写整合所有修复"""
import os, sys, json, io, time, webbrowser
sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

# ── 环境 ──
env_file = Path("D:/视频生成工作流/.env")
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())
    print("OK 环境已加载")

from main import call_llm, parse_json_response
import yaml
config = yaml.safe_load(open("config.yml", encoding="utf-8"))
for k, v in config.get("llm", {}).items():
    if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
        config["llm"][k] = os.environ.get(v[2:-1], "")

max_pages = 16
arc = json.loads(open("docs/shanhai_story_arc.json", encoding="utf-8").read())

# ── 章节号 ──
ch_file = Path("docs/shanhai_chapter.txt")
ch_num = int(ch_file.read_text().strip()) if ch_file.exists() else 1
if "--reset" in sys.argv:
    i = sys.argv.index("--reset")
    if i + 1 < len(sys.argv):
        ch_num = int(sys.argv[i + 1])
        ch_file.write_text(str(ch_num))
        print(f"已重置到第{ch_num}章")
        sys.exit(0)

sum_file = Path("docs/shanhai_summaries.json")
prev = json.loads(sum_file.read_text(encoding="utf-8")) if sum_file.exists() else {}

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
║  山海经外卖 第{ch_num}章  {ch_info['title']}  ║
║  回退: python run_shanhai.py --reset N  ║
╚══════════════════════════════════╝
""")

today = time.strftime("%Y-%m-%d")
script_dir = Path(f"docs/manga_scripts/{today}")
script_dir.mkdir(parents=True, exist_ok=True)
json_path = script_dir / f"shanhai_ch{ch_num:02d}.json"

skip_llm = "--resume" in sys.argv
chapter = None
if skip_llm and json_path.exists():
    chapter = json.loads(open(json_path, encoding="utf-8").read())
elif json_path.exists():
    a = input(f"已有剧本 复用? [Y/n] ").strip().lower()
    if not a or a == "y":
        chapter = json.loads(open(json_path, encoding="utf-8").read())

if not chapter:
    print("DeepSeek 生成剧本...")

    CHEN = "a young Chinese delivery rider, 24, tired eyes, yellow Meituan jacket, deadpan expression, realistic anime style"
    SCENE = "modern Chinese city at night, neon-lit alleyways, wet pavement, hidden magical doorways"

    if ch_num == 1:
        beat = """第1章16页节奏表：
1-2页：暴雨夜。陈默接到怪单——地址废弃电话亭第三格，客户穷奇，素食麻辣拌变态辣，备注：敢放香菜老子吃了你（划掉）揍你。
3-4页：找到电话亭。门拉开——不是电话亭里面，是另一个空间。虎身双翼的巨兽蜷在里面等外卖。
5-6页：穷奇冲出来。陈默没跑。穷奇：你不怕？陈默：怕。但已下单。先确认收货。穷奇整不会了。
7-8页：穷奇吃面变人形。坐电话亭门口。陈默站旁边等确认。沉默。穷奇：你为什么不尖叫。陈默：累了。
9-10页：穷奇：你是第一个看到我不跑的人类。陈默：你是第一个给我50元小费的客户。穷奇愣住然后大笑。
11-12页：离开前。穷奇指向电话亭门——浮现四个字：山海入口。穷奇：你们人类也有能看见的。很少。你是一个。陈默看了一会儿。走了。
13-14页：回程暴雨。手机弹出山海专送App——退不掉删不了。37个非人客户头像：虎蛇鸟龙猪。
15-16页：叮。新订单。收货人：饕餮。五十人份。备注：快。饿。陈默揉太阳穴。骑入暴雨。"""
    elif ch_num == 2:
        beat = """第2章16页节奏表：
1-2页：回顾：穷奇给了三星评价——因为包装盒没摆正。陈默看着评价。放下手机。出门。
3-5页：骑到穷奇武馆。把外卖袋拍桌上。穷奇正要骂人。陈默：免单。改五星。穷奇：你他妈说啥？陈默：……（指手机）
6-8页：穷奇暴怒：操！老子打差评怎么了！从来没人敢跟老子还价！陈默：那我拒你单。永远。穷奇僵住了。
9-11页：两人对峙。穷奇：你就不怕老子揍你？陈默：怕。但平台规定。你可以揍我。但以后没外卖了。穷奇脸上的表情从愤怒→纠结→崩溃。
12-13页：穷奇：……你赢了。操。拿起手机改五星。附言：这个人类脑子有病。但他没跑。还行。
14-15页：陈默转身离开。叮——系统提示：穷奇已成为固定客户。陈默嘴角动了一下（这个表情他只做过三次）。
16页：新单。饕餮。一百人份。备注：快。真饿了。这次四个字。陈默揉太阳穴。骑走。"""
    elif ch_num == 3:
        beat = """第3章16页节奏表：
1-2页：饕餮首单——不是五十人份，是一百人份。陈默看了三次屏幕确认。路线远得离谱。但小费显示：150元。
3-5页：第一趟送到——废弃商场地下。饕餮人形：两百斤的胖子，笑呵呵。陈默放下二十人份。饕餮：谢谢小哥！陈默没走——还有四趟。
6-9页：跑五趟。每趟饕餮都在吃上一趟的。陈默以为一群人拼单。第五趟发现只有他一个。一百个空碗。陈默沉默。饕餮：不好意思啊我就是饿得快。
10-12页：饕餮边吃边聊：我活了九千年。头两千年饿过来的。后来发现人类发明了外卖。这是我活过最好的时代。陈默看着他的手——在发抖。不是胖。是饿太久的后遗症。
13-14页：陈默在饕餮备注里加三字：优先送。饕餮看到。眼眶红了。然后继续吃。
15-16页：次日饕餮又下单。一百二十人份。备注变了：不着急。你慢慢送。陈默看着备注。骑入晨光。"""
    else:
        beat = f"第{ch_num}章：{ch_info.get('desc','')} 16页。结尾必须有钩子。"

    prompt = f"""{beat}

穷奇=暴躁嘴臭吃素香菜死敌。陈默=面瘫社恐 "……"就算一句完整的话。

漫画对话铁律（专业编剧教程）：
1. 每格≤1说话人 ≤2对话框。对话不是列表不是选项。
2. 角色说角色的话——穷奇骂骂咧咧像工地大叔。陈默几乎不说话。让角色自己开口。
3. 不直说情绪——不说"我很生气"说"操"或摔碗。用动作+潜台词。
4. 每句对话必须做功——要么推剧情要么展性格要么改关系。废话删掉。
5. 口语化——不说"此次考试失利深感愧疚"说"考砸了丢死人了"。
6. SFX中文（啪轰嗡咚咔唰）。narration全章≤2。dialogue和narration必须中文。image_prompt才是唯一用英文的。

坏例子（不要写）：
  dialogue:"怕。但已下单。先确认收货。" ← 三句挤一个气泡 像清单
  dialogue:"你小费50" ← 翻译软件不像人话
好例子（应该写）：
  格1 dialogue:"……"  ← 陈默没说话 只是把手机举到穷奇面前
  格2 dialogue:"你他妈给了五十？！" ← 穷奇看到小费的反应
  格3 dialogue:"嗯。" ← 陈默

{max_pages}页。结尾钩子。不连3页同布局。
陈默画面:{CHEN}  场景:{SCENE}
JSON:{{"title":"","headline":"4-8字","subtitle":"","hashtags":["#山海经外卖"],"pages":[{{"layout":"splash","panels":[{{"image_prompt":"{CHEN} ...","narration":null,"dialogue":"中文","sfx":"啪","speaker":"left"}}]}}]}}"""

    resp = call_llm(prompt, config,
        system_prompt="你是漫画编剧。为山海经外卖创作剧本。故事好笑有钩子。只返回JSON。",
        max_tokens=16384)
    print(f"   LLM返回{len(resp)}字符")

    chapter = parse_json_response(resp)
    if isinstance(chapter, list): chapter = chapter[0] if chapter else {}
    if not chapter or "pages" not in chapter:
        print(f"解析失败\n{resp[:500]}")
        Path("docs/shanhai_debug.txt").write_text(resp, encoding="utf-8")
        sys.exit(1)
    json_path.write_text(json.dumps(chapter, ensure_ascii=False, indent=2), encoding="utf-8")

pages = chapter.get("pages", [])
panels = sum(len(p.get("panels", [])) for p in pages)
print(f"   标题:{chapter.get('title','?')}  页数:{len(pages)}/{max_pages}  格数:{panels}")
if len(pages) < max_pages: print(f"   !! 只有{len(pages)}页 应该{max_pages}页")

pv = script_dir / f"shanhai_ch{ch_num:02d}.html"
from modules.manga_preview import generate_preview_html
generate_preview_html(chapter, ch_num, pv)
print(f"预览:{pv}")
webbrowser.open(pv.resolve().as_uri())

print(f"\n预计生图{panels}张≈{panels*15//60}分钟")
a = input("确认生成? [Y/n] ").strip().lower()
if a and a != "y": print("取消 --resume续跑"); sys.exit(0)

chapter = json.loads(open(json_path, encoding="utf-8").read())
print("\n生图+渲染...")
from modules.manga_cards import render_manga_chapter
paths = render_manga_chapter(chapter, chapter_num=ch_num, output_dir="docs/xhs", category="山海经外卖")

print(f"\n第{ch_num}章完成 {len(paths)}张")
for p in paths: print(f"   {Path(p).name} ({os.path.getsize(p)/1024/1024:.1f}MB)")
print(f"\n{Path(paths[0]).parent}")

a = input("\n保存本章并继续? [Y/n] ").strip().lower()
if a and a != "y":
    print("已跳过。下次运行仍为本章。")
else:
    s = input("摘要(回车跳过):").strip()
    if not s: s = ch_info.get('desc','')[:60]
    prev[str(ch_num)] = {"title": chapter.get("title",""), "summary": s}
    sum_file.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
    ch_file.write_text(str(ch_num + 1))
    print(f"已保存 -> 第{ch_num+1}章")
