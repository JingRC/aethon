"""本地跑小道士下山记漫画 — HTML 预览确认 → 生图渲染"""
import os, sys, json, io, time
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
else:
    print("⚠️ 未找到 .env，图片生成可能失败")

# ── 加载配置 ──
from main import call_llm, parse_json_response
import yaml
config = yaml.safe_load(open("config.yml", encoding="utf-8"))
for key, val in config.get("llm", {}).items():
    if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
        config["llm"][key] = os.environ.get(val[2:-1], "")

manga_config = config.get("manga", {})
max_pages = manga_config.get("max_pages", 16)
# 本地强制开启
manga_config["enabled"] = True

# ── 读取故事弧 ──
arc_path = Path("docs/manga_story_arc.json")
if not arc_path.exists():
    print("❌ 未找到 docs/manga_story_arc.json，请先创建故事大纲")
    sys.exit(1)
arc = json.loads(arc_path.read_text(encoding="utf-8"))

# ── 读取章节号 ──
chapter_file = Path("docs/manga_chapter.txt")
if chapter_file.exists():
    chapter_num = int(chapter_file.read_text().strip())
else:
    chapter_num = 1

# ── 读取已完成章节摘要 ──
summaries_file = Path("docs/manga_summaries.json")
prev_summaries = {}
if summaries_file.exists():
    prev_summaries = json.loads(summaries_file.read_text(encoding="utf-8"))

# 找到当前章节的故事弧信息
current_arc_info = None
volume_title = ""
for vol in arc.get("volumes", []):
    for ch in vol.get("chapters", []):
        if ch["num"] == chapter_num:
            current_arc_info = ch
            volume_title = vol["title"]
            break
    if current_arc_info:
        break

if not current_arc_info:
    print(f"⚠️ 故事弧中未定义第{chapter_num}章，使用默认主题")
    current_arc_info = {"title": f"第{chapter_num}章", "theme": "继续小道士的旅程"}

# 构建前情提要
previous_context = ""
if prev_summaries:
    previous_context = "\n".join(
        f"第{num}章《{info.get('title','')}》：{info.get('summary','')}"
        for num, info in sorted(prev_summaries.items())
    )

print(f"""
╔══════════════════════════════════╗
║    小道士下山记 · 第{chapter_num}章      ║
║    {volume_title}                        ║
║    主题：{current_arc_info['title']}          ║
╚══════════════════════════════════╝
""")

# ═══════════════════════════════════════
# 1. LLM 生成剧本（带故事弧上下文）
# ═══════════════════════════════════════
print("🤖 调用 DeepSeek 生成剧本...")

from modules.manga_cards import MANGA_CHARACTER as MC

# 构建带上下文的增强 prompt
story_arc_prompt = f"""你是一位漫画编剧，为连载漫画《小道士下山记》创作第{chapter_num}章。

## 系列信息
卷名：{volume_title}
本章标题：{current_arc_info['title']}
本章主题/方向：{current_arc_info['theme']}
正文页数：{max_pages} 页（不包括封面）

## 前情提要
{previous_context if previous_context else "（这是第1章，没有前情）"}

## 角色设定
### 小道士（主角）
- 15岁，圆圆的脸，大眼睛，表情丰富
- 穿灰色道袍，背着小布包，布鞋
- 性格：好奇、单纯、善良、有点笨拙、很勇敢
- 从小在山上长大，对山下世界一无所知

### 常驻角色
- 师父：山上的老道士，话少但每句都很有分量
- 阿花：（第3章起）山下村庄的女孩，小道士的第一个人类朋友

## 本章创作要点
- 严格围绕上面的主题创作
- 每页 10-35 字的简短对话或旁白
- 布局根据剧情节奏变化：开篇 splash → 展开用 grid4/trio/half → 高潮用 cinema/stack → 结尾用 splash 或网格收尾
- 对话全中文，小道士说话天真单纯但不傻
- 可以有拟声词（sfx）：啪！/ 呼—— / 哗啦 / 吱呀 / 咕噜噜
- 本章可以作为独立故事阅读，但也要和整体连贯

## 布局选择指南
| 布局 | 格数 | 何时使用 |
|------|------|----------|
| splash | 1 | 开篇/收尾/情绪高潮/大场景 |
| half | 2 | 对话场景/对比 |
| trio | 3 | 连续动作/时间推移 |
| grid4 | 4 | 标准叙事推进 |
| cinema | 4 | 全景→细节 |
| stack | 4 | 主画面+反应 |
| grid5 | 5 | 快节奏/忙乱感 |

## 每格图像描述
- 英文撰写，以 "{MC}" 开头
- 描述场景、动作、表情、镜头角度、光线氛围
- 不同格之间要有景别变化（远景→中景→特写）
- 对话和旁白分配到具体面板

## 返回 JSON（只返回 JSON，不要 markdown 代码块）

{{
  "title": "第{chapter_num}章 · {current_arc_info['title']}（8-15字）",
  "headline": "封面大字 4-8字",
  "subtitle": "一句话简介",
  "hashtags": ["#小道士下山记", "#原创漫画", "#治愈系", "#国风动漫"],
  "pages": [
    {{
      "layout": "splash",
      "panels": [
        {{
          "image_prompt": "{MC} standing at...",
          "narration": "旁白文字",
          "dialogue": null,
          "sfx": null,
          "speaker": "left"
        }}
      ]
    }},
    ...
  ]
}}

重要规则：
- pages 数组必须恰好 {max_pages} 个元素
- 每个 page 的 panels 数组长度必须与 layout 声明一致
- 不要遗漏任何字段
- 总共输出 {max_pages} 个页面对象"""

manga_response = call_llm(
    story_arc_prompt, config,
    system_prompt="你是漫画编剧，创作小道士下山记。只返回JSON格式。",
    max_tokens=16384,
)
print(f"   LLM 返回 {len(manga_response)} 字符")

manga_chapter = parse_json_response(manga_response)
if isinstance(manga_chapter, list):
    manga_chapter = manga_chapter[0] if manga_chapter else {}

if not manga_chapter or "pages" not in manga_chapter:
    print(f"❌ LLM 剧本解析失败！")
    print(f"   返回类型: {type(manga_chapter)}")
    print(f"   前500字: {manga_response[:500]}")
    # 保存原始响应用于调试
    Path("docs/manga_debug_response.txt").write_text(manga_response, encoding="utf-8")
    print(f"   原始响应已保存到 docs/manga_debug_response.txt")
    sys.exit(1)

pages = manga_chapter.get("pages", [])
total_panels = sum(len(p.get("panels", [])) for p in pages)

print(f"   标题: {manga_chapter.get('title', '?')}")
print(f"   封面: {manga_chapter.get('headline', '?')}")
print(f"   页数: {len(pages)} / 格数: {total_panels}")

# ═══════════════════════════════════════
# 2. 保存 JSON + 生成 HTML 预览
# ═══════════════════════════════════════
today_str = time.strftime("%Y-%m-%d")
script_dir = Path(f"docs/manga_scripts/{today_str}")
script_dir.mkdir(parents=True, exist_ok=True)

json_path = script_dir / f"ch{chapter_num:02d}_script.json"
json_path.write_text(json.dumps(manga_chapter, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n📝 剧本 JSON: {json_path}")

from modules.manga_preview import generate_preview_html
preview_path = script_dir / f"ch{chapter_num:02d}_preview.html"
generate_preview_html(manga_chapter, chapter_num, preview_path)

# 打开浏览器
print(f"🌐 打开预览: {preview_path}")
webbrowser.open(preview_path.resolve().as_uri())

# ═══════════════════════════════════════
# 3. 等待确认
# ═══════════════════════════════════════
print(f"""
┌─────────────────────────────────────┐
│  预览页面已在浏览器中打开            │
│  检查剧本质量和连贯性                │
│                                     │
│  如需修改：编辑 {json_path.name}     │
│  然后刷新浏览器页面                  │
│                                     │
│  预计生图 {total_panels} 张 × ~15秒 ≈ {total_panels * 15 // 60} 分钟          │
└─────────────────────────────────────┘
""")

ans = input("确认无误，开始生成漫画？[Y/n] ").strip().lower()
if ans and ans != "y":
    print("已取消。下次运行将重新生成本章。")
    sys.exit(0)

# ═══════════════════════════════════════
# 4. 生图 + 渲染
# ═══════════════════════════════════════
# 重新加载（用户可能编辑了 JSON）
if json_path.exists():
    manga_chapter = json.loads(json_path.read_text(encoding="utf-8"))

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

# ═══════════════════════════════════════
# 5. 保存章节摘要（供下一章用）
# ═══════════════════════════════════════
chapter_summary = input("\n📝 输入本章一句话摘要（供后续章节参考）：").strip()
if not chapter_summary:
    chapter_summary = f"小道士{current_arc_info['title']}——{current_arc_info['theme'][:50]}"

prev_summaries[str(chapter_num)] = {
    "title": manga_chapter.get("title", ""),
    "summary": chapter_summary,
}
summaries_file.write_text(json.dumps(prev_summaries, ensure_ascii=False, indent=2), encoding="utf-8")

# 章节号 +1
chapter_file.write_text(str(chapter_num + 1))

print(f"""
╔══════════════════════════════════╗
║  🎉 第{chapter_num}章 完成！              ║
║  章节号 → {chapter_num + 1}                      ║
║  下次运行: python run_manga.py  ║
╚══════════════════════════════════╝
""")
