# ARXIV-DAILY
> **"Let LLM read papers for you."** > 一个为了应对导师 Push、拯救发际线而写的论文速递机器人。

![Python](https://img.shields.io/badge/Python-3.9%2B-blue) ![DeepSeek](https://img.shields.io/badge/AI-LLM%20-purple) ![License](https://img.shields.io/badge/License-GNU-green)

---一个自动化机器人，每天抓取设定好的关键词的最新论文，利用 **硅基流动 (SiliconFlow)等OpenAI API兼容的** 的 API 生成中文摘要，并更新到 Markdown 文档。同时提供现代化的 **PyQt6 桌面 GUI**，方便交互式浏览和配置。

做这个项目的初衷其实特别简单：
**我经常在组会前被导师问：“最近有什么新论文啊？有没有关注最新的 Gaussian Splatting 进展？”**

说实话，每天手动刷 Arxiv 真的很累，而且摘要全是英文，扫一眼过去很难抓住重点。有时候代码敲嗨了，好几天没看论文，组会就尴尬了。

于是我想：**为什么不让 AI 帮我把这些事做了？**

不过呢做这个的主要原因还是最近学了相关知识，打算练练手。它不仅能每天自动把最新的论文总结好推给我，我还给它做了一个像 VSCode 一样的界面，方便我假装很认真地在“研读”文献 😂。

如果你也面临同样的科研压力，或者只是想找个 Python 练手项目，希望这个小工具能帮到你！

## 功能

- **定时抓取**：每天自动从 arXiv 抓取指定关键词的最新论文（最近 24 小时）。
- **智能过滤**：对 Remote Sensing 类论文，仅保留标题或摘要中包含 "Deep Learning"、"Neural"、"AI" 等关键词的论文。
- **中文摘要**：通过硅基流动的 DeepSeek-V3.2 模型生成结构化的中文总结（创新点、方法、结论）。
- **自动报告**：将结果写入 `reports/YYYY-MM-DD.md`，按日期归档，支持历史记录。
- **GitHub Actions**：每天 UTC 0 点自动运行，提交并推送更新。
- **现代化桌面 GUI**：
  - 三栏可拖动布局（类似 VSCode），左侧历史报告列表，中间 Markdown/LaTeX 渲染预览，右侧 AI 问答助手。
  - 设置对话框：可配置 API Key、BaseURL、模型 ID、自定义提示词、关键词等。
  - 后台多线程刷新，避免界面卡顿。
  - 支持 Markdown 和 LaTeX 公式渲染（包括 AI 助手的回答）。
  - 右侧 AI 助手：可针对选中的论文内容进行问答。
  - 实时日志显示：爬虫和摘要的详细进度日志实时显示在状态栏。

## 项目结构

```
.
├── config.json            # 用户 GUI 配置（自动生成）
├── scraper.py             # arXiv 爬虫与过滤模块
├── summarizer.py          # 硅基流动 API 摘要生成
├── main.py                # CLI 主程序，生成当日报告
├── run_gui.py             # GUI 启动脚本
├── gui_main.py            # 主窗口 UI 和逻辑
├── gui_worker.py          # 后台工作线程（爬虫+摘要）
├── gui_config.py          # 配置文件管理（JSON 读写）
├── gui_markdown.py        # Markdown/LaTeX 渲染引擎
├── gui_chat.py            # 右侧 AI 聊天组件
├── requirements.txt       # Python 依赖
├── README.md              # 本文件
├── reports/               # 历史报告目录（按日期归档）
│   └── 2025-12-12.md
└── .github/workflows/daily.yml  # GitHub Actions 工作流
```

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Vynje/Arxiv-Daily.git
cd Arxiv-Daily
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API 密钥

在环境变量中设置硅基流动的 API 密钥：

```bash
export SILICONFLOW_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

或者通过 GUI 设置（推荐）：启动 GUI 后点击右上角齿轮图标，在设置对话框中填入 API Key。

### 4. 使用 CLI（命令行）

```bash
python3 main.py
```

程序将抓取论文、生成摘要，并在 `reports/YYYY-MM-DD.md` 中生成当日报告。

### 5. 使用 GUI（图形界面）

```bash
python run_gui.py
```

GUI 启动后，你可以：
- 点击左上角「刷新」按钮触发爬虫和摘要生成（后台运行）。
- 左侧栏显示历史报告列表，点击任意日期可预览内容。
- 中间区域渲染 Markdown 和 LaTeX 公式。
- 右侧 AI 助手：选中中间区域的文本，在下方输入问题，点击发送即可获得回答。
- 底部状态栏实时显示爬虫和摘要的进度日志。

## 配置说明

### 默认配置

所有配置均通过 `config.json` 管理。首次启动 GUI 时会自动生成 `config.json`，其中包含默认值。

### GUI 设置对话框

点击工具栏的齿轮图标打开设置对话框，可配置以下项：

- **API Key**：硅基流动的 API 密钥（必填）。
- **BaseURL**：API 基础地址（默认 `https://api.siliconflow.cn/v1`）。
- **Model ID**：模型标识（默认 `deepseek-ai/DeepSeek-V3.2`）。
- **Custom Prompt**：自定义摘要生成提示词（支持多行）。
- **Keywords**：搜索关键词，逗号或换行分隔（例如 `Gaussian Splatting, Remote Sensing`）。

设置将自动保存，下次启动时生效。

## 自动化部署

### GitHub Actions

1. 在仓库的 **Settings > Secrets and variables > Actions** 中添加 `SILICONFLOW_API_KEY`。
2. 工作流将每天 UTC 0 点自动运行，你也可以在 Actions 页面手动触发。

### 自定义运行时间

编辑 `.github/workflows/daily.yml` 中的 `cron` 表达式。

## 示例输出

`reports/2025-12-12.md` 的格式如下：

```markdown
# 每日论文报告 (2025-12-12)

## Gaussian Splatting

### [论文标题](链接)
- **作者**: 作者1, 作者2 等
- **日期**: 2025-12-11
- **摘要**: 原始摘要...
- **中文总结**:
**创新点**：...
**方法**：...
**结论**：...
```

## 注意事项

- 硅基流动 API 有调用频率限制，请合理使用。
- 如果 API 调用失败，程序会跳过该论文并继续处理。
- Remote Sensing 论文过滤规则可在 `scraper.py` 中调整。
- GUI 依赖 PyQt6，确保已安装（通过 requirements.txt 安装）。


