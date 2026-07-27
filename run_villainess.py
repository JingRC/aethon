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

    prompt = f"""你是顶尖轻小说/漫画编剧。创作《反派千金今天也在摆烂》第{ch_num}章。

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
- **罗莎莉亚**（主角）：前社畜·林小雨转生。信条：上辈子累死的，这辈子动一下算我输。懒但不蠢。经常用社畜智慧（摸鱼、甩锅、KPI管理）无意中解决宫廷大事
- **艾德里安**（王太子/未婚夫）：高冷→困惑→自我怀疑→"她为什么不理我？？？"
- **塞西莉亚**（原女主）：善良但天然呆。对罗莎莉亚的敌意值：0。困惑值：100。
- **雷恩**（骑士团长）：严肃禁欲系。正在被甜品腐蚀
- **艾莉西亚**（另一反派）：野心家。但每次密谋都被罗莎莉亚的精神状态打败

## 🚫 禁止
- 大段旁白。一页最多一个 narration。用画面和对话推进
- 说教。没有"我明白了"、"人生原来是"
- 温吞水剧情。每一页都要有冲突/反转/笑点/心动

## 🔥 必须
- 对话像真人：毒舌、吐槽、言不由衷
- 罗莎莉亚的每个行动逻辑是"怎么省力怎么来"
- 结果却每次都比努力的人做得更好（因为社畜经验太强了）
- 笑点来自：反派角色的预期 vs 罗莎莉亚的实际行为
- 第1页就要大事件/大疑问/大笑点
- 结尾留钩子——让人骂"怎么在这断了"

## 视觉
- 世界观：{WORLD}
- 华丽宫廷 + 魔法学院 + 日常反差
- 罗莎莉亚永远在睡衣/不修边幅状态 vs 周围人的盛装

## 画面描述
- 罗莎莉亚的 image_prompt 以 "{ROSALIA}" 开头
- 其他角色同理保持一致性
- 每格描述：场景+角色+动作+表情+镜头+光线

## 排版节奏
splash=1格(开篇/高潮/名场面) half=2格(对话交锋) trio=3格(连续镜头)
grid4=4格(叙事) cinema=4格(全景→细节) grid5=5格(混乱)
不连续3页同布局

## 返回 JSON
{{
  "title": "第{ch_num}章 · 吸睛标题",
  "headline": "封面大字 4-8字",
  "subtitle": "有悬念的一句话",
  "hashtags": ["#反派千金摆烂日记","#原创漫画","#乙女游戏","#治愈搞笑"],
  "pages": [
    {{
      "layout": "splash",
      "panels": [{{
        "image_prompt": "{ROSALIA} action scene description...",
        "narration": null,
        "dialogue": "对话 ≤20字",
        "sfx": "啪！",
        "speaker": "left"
      }}]
    }}
  ]
}}
{max_pages} 页 | panels 匹配 layout | narration 一页最多一次 | 优先 dialogue"""

    resp = call_llm(
        prompt, config,
        system_prompt="你是顶尖轻小说/漫画编剧。创造让人上瘾的故事。不讲道理，只要好看。只返回JSON。",
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
