# GUI 设计文档

## 整体布局

使用 `QMainWindow` 作为主窗口，包含以下部分：

1. **中央部件**：一个 `QSplitter`（水平方向）包含三个面板（左、中、右）。
2. **顶部工具栏**：位于中央部件上方，包含刷新按钮和设置按钮。
3. **底部状态栏**：显示进度条和状态消息。

## 组件详情

### 1. 顶部工具栏 (QToolBar)
- 左侧：项目标题 "ARXIV-DAILY"
- 右侧：
  - **刷新按钮** (QPushButton with icon)：触发后台任务（爬虫 + 摘要生成）
  - **设置按钮** (QPushButton with icon)：打开设置对话框

### 2. 左侧栏 (QWidget)
- 垂直布局
  - 日期选择器 (QDateEdit) 或标签显示当前选中日期
  - **历史报告列表** (QListWidget)：显示按日期排序的报告文件（从 `reports/` 目录读取）
  - 点击列表项时，在中间栏加载对应的 Markdown 文件。

### 3. 中间栏 (QWidget)
- 垂直布局
  - 标题标签 (QLabel) 显示当前报告日期
  - **内容显示区域** (QTextBrowser 或自定义 Markdown 渲染器)：渲染 Markdown 和 LaTeX
  - 支持文本选择（用于右侧 AI 提问）

### 4. 右侧栏 (QWidget)
- 垂直布局
  - **AI 聊天区域**：
    - 顶部：显示选中的文本（从中间栏划词引用）
    - 中间：聊天历史 (QTextBrowser)
    - 底部：输入框 (QLineEdit) 和发送按钮 (QPushButton)
  - 功能：用户可以在中间栏选择文本，点击“引用”按钮将其插入到聊天输入框，然后输入问题，发送给 AI（使用相同的硅基流动 API）。

### 5. 底部状态栏 (QStatusBar)
- 左侧：永久性状态消息（例如“就绪”）
- 中间：进度条 (QProgressBar) 在后台任务运行时显示
- 右侧：临时消息（例如“正在爬取...”）

## 交互流程

### 刷新操作
1. 用户点击刷新按钮。
2. GUI 禁用刷新按钮，显示进度条，状态消息更新。
3. 启动后台线程执行 `scraper.scrape_all()` 和 `summarizer.batch_summarize()`。
4. 完成后，将结果保存为 `reports/YYYY-MM-DD.md` 并更新 `Daily_Report.md`。
5. 更新左侧历史报告列表，选中最新日期。
6. 在中间栏显示新报告。

### 设置对话框
- 模态对话框 (QDialog)
- 包含四个输入框：
  1. API Key
  2. BaseURL
  3. 模型 ID
  4. 自定义提示词
- 保存按钮：将配置写入 `config.py` 或单独的 JSON 配置文件（建议使用 JSON 以便于 GUI 管理）。
- 取消按钮：关闭对话框。

### 划词提问
1. 用户在中间栏选择文本。
2. 右侧栏顶部显示“已选择：<文本>”并提供一个“引用”按钮。
3. 点击“引用”将选中的文本插入到聊天输入框。
4. 用户输入问题，点击发送。
5. 调用 AI API（使用当前配置的模型）并显示回复。

## 技术选型

- **GUI 框架**：PyQt6
- **多线程**：QThread + 信号/槽
- **配置存储**：JSON 文件 (`config.json`)，与 `config.py` 并存或替换。
- **Markdown 渲染**：使用 `QTextBrowser` 的 HTML 渲染能力，通过 `markdown2` 或 `markdown` 库转换为 HTML。LaTeX 使用 `matplotlib` 渲染为图片嵌入。
- **AI 聊天**：使用与摘要相同的 OpenAI 兼容 API，但使用不同的提示词。

## Markdown/LaTeX 渲染设计

### 目标
- 在 QTextBrowser 中渲染 Markdown 格式（标题、列表、链接、粗体、斜体等）。
- 支持内联 LaTeX 公式（`$...$`）和块级公式（`$$...$$`）。
- 保持轻量级，无需安装完整的 LaTeX 系统。

### 方案
1. **Markdown 到 HTML 转换**：使用 Python `markdown` 库（支持扩展）将 Markdown 文本转换为 HTML。
2. **LaTeX 处理**：使用 `matplotlib.mathtext` 将 LaTeX 公式渲染为 PNG 图像，然后替换为 `<img>` 标签。
   - 优点：无需外部依赖（除了 matplotlib）。
   - 缺点：可能不支持所有 LaTeX 命令，但足以满足大多数数学公式。
3. **实现步骤**：
   - 编写函数 `render_markdown_with_latex(text: str) -> str`，返回 HTML 字符串。
   - 使用正则表达式检测 `$...$` 和 `$$...$$` 块。
   - 对于每个公式，使用 `matplotlib.mathtext.math_to_image` 生成图像，保存到临时文件，并生成 base64 数据 URL 或相对路径。
   - 将图像嵌入 HTML 中。
   - 将最终的 HTML 设置到 `QTextBrowser` 中。

### 依赖项
- `markdown` (>=3.5)
- `matplotlib` (>=3.7)
- `Pillow` (用于图像处理)

### 性能考虑
- 渲染多个公式可能会产生大量临时文件。考虑使用内存中的字节流和 base64 编码以避免文件 I/O。
- 缓存已渲染的公式以提高重复加载的速度。

### 备选方案
- 使用 `python-markdown-math` 扩展将 LaTeX 转换为 MathML，但 QTextBrowser 可能不支持 MathML。
- 使用 `sympy` 的 `latex2mathml` 并依赖 Qt 的 MathML 支持（如果可用）。需要测试。

## 文件结构

```
.
├── gui_main.py              # 主窗口
├── gui_worker.py            # 后台工作线程
├── gui_config.py            # 配置管理
├── gui_markdown.py          # Markdown/LaTeX 渲染器
├── gui_chat.py              # AI 聊天逻辑
├── reports/                 # 历史报告目录
├── config.json              # GUI 配置文件（可选）
└── requirements.txt         # 添加 PyQt6, markdown, matplotlib 等
```

## AI 聊天功能设计

### 目标
- 允许用户针对每日摘要中的内容进行提问。
- 支持划词引用，将选中的文本作为上下文提供给 AI。
- 使用与摘要生成相同的 OpenAI 兼容 API（硅基流动），但使用不同的提示词。

### UI 组件
1. **选中文本显示区** (QLabel)
   - 位于右侧栏顶部，显示“已选择：<文本>”。
   - 提供一个“引用”按钮，点击后将选中文本插入输入框。
2. **聊天历史显示区** (QTextBrowser)
   - 显示用户和 AI 的对话历史，支持 Markdown 渲染。
3. **输入区域** (QHBoxLayout)
   - 输入框 (QLineEdit)：用于输入问题。
   - 发送按钮 (QPushButton)：发送消息。
   - 清空按钮 (QPushButton)：清空聊天历史。

### 交互流程
1. 用户在中间栏选择文本（通过鼠标拖选）。
2. 中间栏的 `selectionChanged` 信号触发，将选中文本传递给右侧栏。
3. 右侧栏更新选中文本显示区，并启用“引用”按钮。
4. 用户点击“引用”按钮，将选中文本插入输入框（格式如“关于以下内容：{选中文本}，我的问题是：”）。
5. 用户编辑输入框，添加自己的问题。
6. 点击发送按钮，将消息添加到聊天历史，并调用 AI API。
7. 在等待 API 响应期间，显示加载指示器。
8. 收到响应后，将 AI 回复添加到聊天历史。

### 技术实现
#### 消息格式
- 系统提示词：定义 AI 的角色（例如“你是一个研究助手，帮助用户理解 Arxiv 论文摘要。”）。
- 用户消息：包含引用文本和用户问题。
- AI 回复：纯文本或 Markdown。

#### API 调用
- 使用 `openai` 库（已存在于项目中）或 `requests` 直接调用。
- 配置从 `config.json` 读取（API Key, BaseURL, 模型 ID）。
- 异步调用，避免阻塞 UI 线程（使用 QThread 或 `asyncio` + `QTimer`）。

#### 多线程处理
- 聊天 API 调用应在后台线程中执行，防止界面卡顿。
- 使用 `QThread` 和信号/槽来传递请求和接收响应。

#### 历史管理
- 聊天历史保存在内存中（列表），每次启动 GUI 时清空。
- 可考虑将聊天历史保存到文件（可选功能）。

### 错误处理
- 网络错误：显示错误消息在聊天历史中。
- API 密钥错误：提示用户检查配置。

### 依赖项
- `openai` (已存在)
- `requests` (已存在)

### 下一步
1. 实现 `gui_chat.py` 中的 `ChatWidget` 类。
2. 集成到主窗口的右侧栏。
3. 测试 API 连接。

## 下一步

1. 确定配置管理方案（JSON vs 直接修改 config.py）。
2. 设计多线程后台任务的具体信号。
3. 选择 Markdown/LaTeX 渲染库。
4. 开始实现。
