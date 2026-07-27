"""反派千金今天也在摆烂 — 漫画章节生成器"""
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

# ── 读取故事弧 ──
arc = json.loads(open("docs/villainess_story_arc.json", encoding="utf-8").read())

# ── 章节号 ──
ch_file = Path("docs/villainess_chapter.txt")
ch_num = int(ch_file.read_text().strip()) if ch_file.exists() else 1

# ── 前情 ──
sum_file = Path("docs/villainess_summaries.json")
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
    ch_info = {"title": f"第{ch_num}章", "theme": "继续摆烂"}

prev_ctx = ""
if prev:
    prev_ctx = "\n".join(
        f"第{n}章《{i.get('title','')}》：{i.get('summary','')}"
        for n, i in sorted(prev.items())
    )

print(f"""
╔══════════════════════════════════╗
║  反派千金今天也在摆烂 · 第{ch_num}章  ║
║  {vol_title}      ║
║  {ch_info['title']}                ║
╚══════════════════════════════════╝
""")

# ── 复用检查 ──
today = time.strftime("%Y-%m-%d")
script_dir = Path(f"docs/manga_scripts/{today}")
script_dir.mkdir(parents=True, exist_ok=True)
json_path = script_dir / f"villainess_ch{ch_num:02d}.json"

skip_llm = "--skip-llm" in sys.argv or "--resume" in sys.argv
chapter = None

if skip_llm and json_path.exists():
    chapter = json.loads(open(json_path, encoding="utf-8").read())
    print(f"📂 复用已有剧本 ({len(chapter.get('pages',[]))} 页)")
elif json_path.exists():
    ans = input(f"📂 已有剧本，复用？[Y/n] ").strip().lower()
    if not ans or ans == "y":
        chapter = json.loads(open(json_path, encoding="utf-8").read())

# ═══════════════════ LLM ═══════════════════
if not chapter:
    print("🤖 DeepSeek 生成爆款剧本...")

    # ── 角色图像描述 ──
    ROSALIA = (
        "a beautiful young noblewoman with disheveled silver-white hair loosely tied, "
        "wearing an elegant but wrinkled nightgown or casual dress, half-lidded lazy eyes, "
        "always holding snacks or tea, anime manga style, soft cel shading, "
        "European fantasy rococo aesthetic, warm candlelit interiors"
    )
    CEDRIC = (
        "a handsome crown prince with golden hair and blue eyes, wearing royal white uniform "
        "with gold epaulettes, stern expression but blushing easily, anime style"
    )
    CECILIA = (
        "a sweet girl with honey-brown hair in braids, kind green eyes, "
        "simple academy uniform, anime style, shoujo manga aesthetic"
    )
    WORLD = "European fantasy academy setting, grand marble halls, rose gardens, crystal chandeliers, magical floating candles, otome game aesthetic"

    prompt = f"""你是顶尖轻小说/漫画编剧。为《反派千金今天也在摆烂》创作第{ch_num}章。

## 世界观
{json.dumps(arc.get('world',{}), ensure_ascii=False)}
系列：{arc.get('tagline','')}
本章剧情：{ch_info['theme']}
页数：{max_pages} 页正文 + 1 封面

## 前情
{prev_ctx if prev_ctx else "第1章"}

## ⚠️ 本章绝对规则

### 只出场两个角色（除路人）
- 罗莎莉亚（主角）
- 艾德里安（王太子/未婚夫）
- 其他人本章不出现。女仆路人可以有一两格。

### 只发生在一个场景
花园下午茶。从头到尾就这一个场景。不要切来切去。

### 叙事节奏（16页分配）
- 1-2页：她醒来→发现自己是恶役千金→撕计划书（快！不要闪回！）
- 3-4页：穿睡衣去厨房叫甜品→来到花园（建立世界+人设）
- 5-6页：艾德里安闯入，怒气冲冲，却看到不梳头的她在吃蛋糕（核心反转）
- 7-10页：两人的对峙。他质问。她请吃蛋糕。他说不。肚子叫了。他吃了。
- 11-12页：他们吃蛋糕聊天的尴尬沉默。她提出"退婚不用急，先吃东西"
- 13-14页：艾德里安离开时脑子一团乱。他的侍从问他怎么了。"她给我吃了块蛋糕。"
- 15页：罗莎莉亚独自在花园。打了个哈欠。"第一天，没死。还行。"她看不见的系统面板弹出：艾德里安好感度 0→15。系统标注：？？？
- 16页：第二天早上，敲门声。艾德里安站在门口。"昨天的蛋糕……还有吗。"本章完。

### 禁止
- 前世闪回超过1格。用一句话带过就行
- 塞西莉亚、雷恩、卢西安本章不出场
- 系统面板只在最后一页出现一次
- 视角不跳来跳去。全程罗莎莉亚视角。

## 角色性格
- 罗莎莉亚：不是傻白甜。是"社畜老油条"。嘴甜心冷。对权力没兴趣但对食物有执念。经典反应：'哦。' '然后呢？' '那挺好的。' '别打扰我吃东西。'
- 艾德里安：不是霸总。是"高冷但社恐"的王太子。从小被教育要威严，其实不知道怎么跟人正常说话。罗莎莉亚的不按套路来让他崩溃——不是愤怒，是困惑。

## 画面
- 罗莎莉亚：欧式华丽闺房+睡衣+银发散乱+永远在吃东西。image_prompt 前缀："{ROSALIA}"
- 艾德里安：金发蓝眼+白色金饰军装+永远皱眉但会脸红。image_prompt 前缀："{CEDRIC}"
- 世界观背景："{WORLD}"

## 排版
splash=1格(开篇/高潮/结尾) half=2格(对峙) trio=3格(连续镜头)
grid4=4格(叙事) cinema=4格(全景→细节) grid5=5格(混乱)
不连续3页同布局

## 返回JSON
{{
  "title": "第{ch_num}章 · 今天开始做废人",
  "headline": "开始摆烂",
  "subtitle": "撕了计划书，叫了蛋糕，然后王子来了。",
  "hashtags": ["#反派千金摆烂日记","#原创漫画","#乙女游戏","#治愈搞笑"],
  "pages": [
    {{
      "layout": "splash",
      "panels": [{{
        "image_prompt": "{ROSALIA} waking up in luxurious bed, tearing up a document labeled 'Villainess Plan', triumphant grin, morning sunlight through curtains",
        "narration": null,
        "dialogue": "上辈子加班死。这辈子——不干了。",
        "sfx": "嘶啦！",
        "speaker": "left"
      }}]
    }}
  ]
}}
{max_pages} 页正文 | panels 匹配布局 | 全章 narration ≤3 处 | 每句 dialogue ≤20字"""

    resp = call_llm(
        prompt, config,
        system_prompt="你是漫画编剧。本章只出场两个角色、一个场景。对话简洁。不讲道理。只返回JSON。",
        max_tokens=16384,
    )
    print(f"   LLM 返回 {len(resp)} 字符")

    chapter = parse_json_response(resp)
    if isinstance(chapter, list):
        chapter = chapter[0] if chapter else {}

    if not chapter or "pages" not in chapter:
        print(f"❌ 解析失败！\n{resp[:500]}")
        Path("docs/villainess_debug.txt").write_text(resp, encoding="utf-8")
        sys.exit(1)

    json_path.write_text(json.dumps(chapter, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📝 已保存: {json_path}")

pages = chapter.get("pages", [])
total_panels = sum(len(p.get("panels", [])) for p in pages)
print(f"   标题: {chapter.get('title','?')}")
print(f"   封面: {chapter.get('headline','?')}")
print(f"   页数: {len(pages)} / 格数: {total_panels}")

# ═══════════════════ 预览 ═══════════════════
preview_path = script_dir / f"villainess_ch{ch_num:02d}.html"
from modules.manga_preview import generate_preview_html
generate_preview_html(chapter, ch_num, preview_path)
print(f"🌐 预览: {preview_path}")
webbrowser.open(preview_path.resolve().as_uri())

print(f"""
┌─────────────────────────────────────┐
│  预览已打开。检查剧本质量。          │
│  修改: {json_path.name}              │
│  生图: ~{total_panels} 张 ≈ {total_panels*15//60} 分钟              │
└─────────────────────────────────────┘
""")

ans = input("确认生成漫画？[Y/n] ").strip().lower()
if ans and ans != "y":
    print("已取消。--resume 可续跑。")
    sys.exit(0)

# ═══════════════════ 渲染 ═══════════════════
chapter = json.loads(open(json_path, encoding="utf-8").read())
print("\n🎨 生图 + 渲染...")

from modules.manga_cards import render_manga_chapter
paths = render_manga_chapter(
    chapter, chapter_num=ch_num,
    output_dir="docs/xhs",
    category="反派千金",
)

print(f"\n✅ 第{ch_num}章完成！{len(paths)} 张")
for p in paths:
    print(f"   {Path(p).name} ({os.path.getsize(p)/1024/1024:.1f} MB)")
print(f"\n📂 {Path(paths[0]).parent}")

# ═══════════════════ 保存 ═══════════════════
s = input("\n📝 一句话摘要：").strip()
if not s: s = ch_info['theme'][:60]
prev[str(ch_num)] = {"title": chapter.get("title",""), "summary": s}
sum_file.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
ch_file.write_text(str(ch_num + 1))
print(f"\n🎉 第{ch_num}章完成 → 第{ch_num+1}章")
