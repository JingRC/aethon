# 🔥 Aethon — Daily AI Intelligence

> **AI 快讯 · 洞察科技前沿** &nbsp;|&nbsp; **古代故事 · 品味千年智慧**

每天自动生成并推送一封精致的日报邮件，包含两大板块：
- 🤖 **10 条 AI 快讯** — 多源聚合（HuggingFace / TechCrunch / 36Kr / The Verge / GitHub Trending），LLM 智能筛选评分
- 🏯 **10 则中国古代故事典故** — LLM 每日精选，涵盖成语典故/历史故事/诸子寓言/诗词故事

---

## ✨ 特性

| 功能 | 说明 |
|------|------|
| 📰 **多源聚合** | RSS (6+ 源) + GitHub Trending，自动抓取 |
| 🤖 **AI 智能筛选** | DeepSeek/GPT/Claude/Gemini 多模型支持，筛选+评分+摘要 |
| 🏯 **典故生成** | LLM 每日轮换 8 大主题，自动生成 10 则中国古代故事 |
| 📧 **邮件推送** | 精美 HTML 邮件，每天自动发送到邮箱 |
| 🌐 **静态站点** | 自动部署 GitHub Pages，可在线浏览历史日报 |
| 💰 **零成本** | GitHub Actions + DeepSeek 免费额度，完全不用服务器 |
| 🌗 **暗黑模式** | HTML 邮件/站点自适应系统主题 |

---

## 🚀 快速开始（3 步）

### 1. Fork 本仓库

点击 GitHub 页面右上角 **Fork** 按钮。

### 2. 配置 Secrets

在 Fork 后的仓库 → **Settings → Secrets and variables → Actions**，添加以下 Secrets：

| Secret 名称 | 说明 |
|-------------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（[申请地址](https://platform.deepseek.com/api_keys)） |
| `GMAIL_USER` | 你的 Gmail 地址（如 `xxx@gmail.com`） |
| `GMAIL_APP_PASSWORD` | Gmail 应用专用密码（[生成方法](https://support.google.com/accounts/answer/185833)） |
| `RECIPIENT_EMAIL` | 接收日报的邮箱 |

> 💡 如果不想用邮件推送，可以只配 `DEEPSEEK_API_KEY`，日报会发布到 GitHub Pages。

### 3. 启用 GitHub Actions

进入仓库 **Actions** 标签页，启用 Workflow，然后手动触发一次 `Aethon` → **Run workflow**。

---

## ⚙️ 自定义配置

编辑 `config.yml` 可调整：

```yaml
ai_news:
  count: 10           # 每日AI快讯条数
  sources:
    rss: [...]        # RSS 数据源列表（可增减）

ancient_stories:
  count: 10           # 每日故事则数
  categories: [...]   # 故事主题（可增减）

email:
  enabled: true       # 是否启用邮件推送
  sender_email: "${GMAIL_USER}"

schedule:
  hour: 8             # 北京时间发送时间
```

---

## 💰 成本估算

| LLM | 每日费用 | 月费用 |
|-----|---------|--------|
| **DeepSeek-V3** | ¥0.03-0.08 | ¥1-2.5 |
| **Gemini 2.0 Flash** | 免费 | 免费 |
| **GPT-4o mini** | $0.02-0.05 | $0.6-1.5 |
| **Claude Haiku** | $0.03-0.06 | $1-2 |

> DeepSeek 性价比最高，每天 20 条内容生成仅需几分钱。

---

## 📂 项目结构

```
.
├── main.py                     # 主程序入口
├── config.yml                  # 配置文件
├── requirements.txt            # Python 依赖
├── modules/
│   ├── ai_news.py              # AI 快讯：RSS抓取 + LLM筛选
│   ├── ancient_stories.py      # 古代故事：LLM 生成
│   └── email_sender.py         # Email 推送
├── templates/
│   └── daily_report.html       # HTML 邮件模板
├── docs/                       # 日报输出（HTML/MD/JSON）
└── .github/workflows/
    └── daily.yml               # GitHub Actions 定时任务
```

---

## 📬 效果预览

### Email 邮件预览

日报邮件包含：
- 🎨 渐变色头部（紫色→棕色，呼应双主题）
- 🤖 AI 快讯板块：编号 + 标题 + 来源 + 星级评分 + 摘要
- 🏯 古代故事板块：编号 + 标题 + 朝代标签 + 故事内容 + 寓意框

### 在线站点

日报同步部署到 `https://<你的用户名>.github.io/<仓库名>/`，可在线浏览。

---

## 🙏 致谢

本项目灵感来源于：
- [Jimmuji/ai-daily-digest](https://github.com/Jimmuji/ai-daily-digest) — AI 日报架构
- [Yifannnnnnnnw/ai-dispatch](https://github.com/Yifannnnnnnnw/ai-dispatch) — 多板块邮件日报设计
- [chinese-xinhua](https://github.com/pwxcoo/chinese-xinhua) — 成语数据库
