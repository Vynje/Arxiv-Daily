"""
ARXIV-DAILY 图形用户界面主窗口。
"""
import os
import sys
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QToolBar, QStatusBar, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QTextBrowser, QDialog, QLineEdit, QFormLayout,
    QDialogButtonBox, QMessageBox, QProgressBar, QFrame, QSizePolicy,
    QPlainTextEdit, QSpinBox, QComboBox, QTimeEdit, QDateEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QSize, QTime, QDate
from PyQt6.QtGui import QIcon, QFont, QAction, QTextCursor, QTextCharFormat, QBrush, QColor

# 自定义模块
import config
import gui_markdown
import gui_chat
import gui_worker


class SettingsDialog(QDialog):
    """全局设置对话框，仅配置 BaseURL、API Key 和模型 ID。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("全局设置")
        self.setModal(True)
        self.resize(500, 200)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setMinimumWidth(400)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setMinimumWidth(400)
        self.model_id_edit = QLineEdit()
        self.model_id_edit.setMinimumWidth(400)

        layout.addRow("API Key:", self.api_key_edit)
        layout.addRow("Base URL:", self.base_url_edit)
        layout.addRow("模型 ID:", self.model_id_edit)

        # 提示词（多行文本）
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setMinimumWidth(400)
        self.prompt_edit.setMinimumHeight(120)
        layout.addRow("AI 摘要提示词:", self.prompt_edit)

        # 从当前配置加载值
        self.load_current_config()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def load_current_config(self):
        """从 config 加载当前配置并填充到输入框。"""
        cfg = config.load_config()
        self.api_key_edit.setText(cfg.get("API_KEY", ""))
        self.base_url_edit.setText(cfg.get("BASE_URL", ""))
        self.model_id_edit.setText(cfg.get("MODEL_ID", ""))
        self.prompt_edit.setPlainText(cfg.get("SYSTEM_PROMPT", ""))

    def save_config(self):
        """将输入框的值保存到配置文件。"""
        cfg = {
            "API_KEY": self.api_key_edit.text().strip(),
            "BASE_URL": self.base_url_edit.text().strip(),
            "MODEL_ID": self.model_id_edit.text().strip(),
            "SYSTEM_PROMPT": self.prompt_edit.toPlainText().strip(),
        }
        config.save_config(cfg)

class SearchSettingsDialog(QDialog):
    """检索设置对话框，用于配置时间范围、关键词、附加关键词、黑名单关键词。"""

    def __init__(self, prefix: str, title: str, parent=None):
        """
        :param prefix: 配置键前缀，例如 'DAILY_PUSH_' 或 'USER_SEARCH_'
        :param title: 对话框标题
        """
        super().__init__(parent)
        self.prefix = prefix
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(600, 500)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        is_daily_push = (self.prefix == "DAILY_PUSH_")

        if self.prefix == "USER_SEARCH_":
            # 日期范围选择
            self.start_date_edit = QDateEdit()
            self.start_date_edit.setCalendarPopup(True)
            self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
            self.start_date_edit.setMinimumWidth(200)
            self.end_date_edit = QDateEdit()
            self.end_date_edit.setCalendarPopup(True)
            self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
            self.end_date_edit.setMinimumWidth(200)
            layout.addRow("开始日期:", self.start_date_edit)
            layout.addRow("结束日期:", self.end_date_edit)
            self.filter_days_spin = None
        elif not is_daily_push:
            # 检索时间范围（天数）仅用于非每日推送（其他前缀，如全局？实际上只有DAILY_PUSH_和USER_SEARCH_）
            self.filter_days_spin = QSpinBox()
            self.filter_days_spin.setRange(1, 365)
            self.filter_days_spin.setValue(7)
            self.filter_days_spin.setSuffix(" 天")
            self.filter_days_spin.setMinimumWidth(200)
            layout.addRow("检索时间范围（天数）:", self.filter_days_spin)
        else:
            # 每日推送：隐藏检索时间范围，使用固定值（1天）
            self.filter_days_spin = None
            # 时区选择
            self.timezone_combo = QComboBox()
            self.timezone_combo.addItems([
                "Asia/Shanghai",
                "UTC",
                "America/New_York",
                "Europe/London",
                "Asia/Tokyo",
                "Australia/Sydney",
                "America/Los_Angeles",
                "Europe/Paris",
                "Asia/Singapore",
                "Asia/Hong_Kong"
            ])
            self.timezone_combo.setMinimumWidth(200)
            layout.addRow("时区:", self.timezone_combo)
            # 每日自动推送时间
            self.daily_time_edit = QTimeEdit()
            self.daily_time_edit.setDisplayFormat("HH:mm")
            self.daily_time_edit.setMinimumWidth(200)
            layout.addRow("每日自动推送时间:", self.daily_time_edit)

        # 检索关键词（用户检索不需要，因为关键词来自搜索框）
        if self.prefix != "USER_SEARCH_":
            self.keywords_edit = QPlainTextEdit()
            self.keywords_edit.setPlaceholderText(
                "每行一个关键词，或用逗号分隔。例如：\nGaussian Splatting\nRemote Sensing"
            )
            self.keywords_edit.setMinimumHeight(80)
            self.keywords_edit.setMinimumWidth(500)
            layout.addRow("检索关键词:", self.keywords_edit)
        else:
            self.keywords_edit = None

        # 附加关键词
        self.additional_keywords_edit = QPlainTextEdit()
        self.additional_keywords_edit.setPlaceholderText(
            "每行一个关键词，或用逗号分隔。用于附加过滤。默认：\nDeep Learning, Neural, AI, Machine Learning, Artificial Intelligence"
        )
        self.additional_keywords_edit.setMinimumHeight(80)
        self.additional_keywords_edit.setMinimumWidth(500)
        layout.addRow("附加关键词:", self.additional_keywords_edit)

        # 黑名单关键词
        self.blacklist_edit = QPlainTextEdit()
        self.blacklist_edit.setPlaceholderText(
            "每行一个关键词，或用逗号分隔。留空表示不过滤。例如：\nSurvey\nReview"
        )
        self.blacklist_edit.setMinimumHeight(80)
        self.blacklist_edit.setMinimumWidth(500)
        layout.addRow("黑名单关键词:", self.blacklist_edit)

        # 从当前配置加载值
        self.load_current_config()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def load_current_config(self):
        """从 config 加载当前配置并填充到输入框。"""
        cfg = config.load_config()
        is_daily_push = (self.prefix == "DAILY_PUSH_")

        if self.prefix == "USER_SEARCH_":
            # 日期范围
            start_date_key = self.prefix + "START_DATE"
            end_date_key = self.prefix + "END_DATE"
            start_date_str = cfg.get(start_date_key)
            end_date_str = cfg.get(end_date_key)
            # 默认值：今天-7天 到 今天
            today = QDate.currentDate()
            default_start = today.addDays(-7)
            default_end = today
            if start_date_str:
                start_date = QDate.fromString(start_date_str, "yyyy-MM-dd")
                if start_date.isValid():
                    self.start_date_edit.setDate(start_date)
                else:
                    self.start_date_edit.setDate(default_start)
            else:
                self.start_date_edit.setDate(default_start)
            if end_date_str:
                end_date = QDate.fromString(end_date_str, "yyyy-MM-dd")
                if end_date.isValid():
                    self.end_date_edit.setDate(end_date)
                else:
                    self.end_date_edit.setDate(default_end)
            else:
                self.end_date_edit.setDate(default_end)
        elif not is_daily_push:
            # 时间范围（天数）
            filter_days_key = self.prefix + "FILTER_DAYS"
            self.filter_days_spin.setValue(cfg.get(filter_days_key, 7))
        else:
            # 时区
            timezone_key = self.prefix + "TIMEZONE"
            timezone = cfg.get(timezone_key, "Asia/Shanghai")
            index = self.timezone_combo.findText(timezone)
            if index >= 0:
                self.timezone_combo.setCurrentIndex(index)
            else:
                self.timezone_combo.setCurrentText(timezone)
            # 每日推送时间
            time_key = self.prefix + "TIME"
            time_str = cfg.get(time_key, "09:00")
            try:
                time_obj = QTime.fromString(time_str, "HH:mm")
                if not time_obj.isValid():
                    time_obj = QTime(9, 0)
            except Exception:
                time_obj = QTime(9, 0)
            self.daily_time_edit.setTime(time_obj)

        # 关键词（用户检索不需要，因为关键词来自搜索框）
        if self.keywords_edit is not None:
            keywords_key = self.prefix + "KEYWORDS"
            keywords = cfg.get(keywords_key, [])
            if isinstance(keywords, list):
                self.keywords_edit.setPlainText(", ".join(keywords))
            else:
                self.keywords_edit.setPlainText(str(keywords))
        # 附加关键词
        additional_keywords_key = self.prefix + "ADDITIONAL_KEYWORDS"
        additional_keywords = cfg.get(additional_keywords_key, [])
        if isinstance(additional_keywords, list):
            self.additional_keywords_edit.setPlainText(", ".join(additional_keywords))
        else:
            self.additional_keywords_edit.setPlainText(str(additional_keywords))
        # 黑名单关键词
        blacklist_key = self.prefix + "BLACKLIST_KEYWORDS"
        blacklist = cfg.get(blacklist_key, [])
        if isinstance(blacklist, list):
            self.blacklist_edit.setPlainText(", ".join(blacklist))
        else:
            self.blacklist_edit.setPlainText(str(blacklist))

    def save_config(self):
        """将输入框的值保存到配置文件。"""
        is_daily_push = (self.prefix == "DAILY_PUSH_")

        # 解析关键词文本
        keywords = []
        if self.keywords_edit is not None:
            keywords_text = self.keywords_edit.toPlainText().strip()
            if keywords_text:
                lines = keywords_text.splitlines()
                for line in lines:
                    parts = line.split(",")
                    for part in parts:
                        stripped = part.strip()
                        if stripped:
                            keywords.append(stripped)

        # 解析附加关键词
        additional_keywords_text = self.additional_keywords_edit.toPlainText().strip()
        additional_keywords = []
        if additional_keywords_text:
            lines = additional_keywords_text.splitlines()
            for line in lines:
                parts = line.split(",")
                for part in parts:
                    stripped = part.strip()
                    if stripped:
                        additional_keywords.append(stripped)

        # 解析黑名单关键词
        blacklist_text = self.blacklist_edit.toPlainText().strip()
        blacklist = []
        if blacklist_text:
            lines = blacklist_text.splitlines()
            for line in lines:
                parts = line.split(",")
                for part in parts:
                    stripped = part.strip()
                    if stripped:
                        blacklist.append(stripped)

        cfg_updates = {
            self.prefix + "KEYWORDS": keywords,
            self.prefix + "ADDITIONAL_KEYWORDS": additional_keywords,
            self.prefix + "BLACKLIST_KEYWORDS": blacklist,
        }

        if self.prefix == "USER_SEARCH_":
            # 保存日期范围
            cfg_updates[self.prefix + "START_DATE"] = self.start_date_edit.date().toString("yyyy-MM-dd")
            cfg_updates[self.prefix + "END_DATE"] = self.end_date_edit.date().toString("yyyy-MM-dd")
            # 不需要 FILTER_DAYS
            cfg_updates[self.prefix + "FILTER_DAYS"] = 1  # 占位符，但不会被使用
        elif not is_daily_push:
            cfg_updates[self.prefix + "FILTER_DAYS"] = self.filter_days_spin.value()
        else:
            # 每日推送：固定 FILTER_DAYS 为 1（不显示）
            cfg_updates[self.prefix + "FILTER_DAYS"] = 1
            cfg_updates[self.prefix + "TIMEZONE"] = self.timezone_combo.currentText()
            time_str = self.daily_time_edit.time().toString("HH:mm")
            cfg_updates[self.prefix + "TIME"] = time_str

        config.save_config(cfg_updates)


class MainWindow(QMainWindow):
    """主窗口，包含三栏布局和所有交互。"""

    # 信号：用于从中栏向右侧栏传递选中的文本
    text_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARXIV-DAILY")
        self.resize(1400, 900)

        # 状态变量
        self.current_report_path: Optional[str] = None
        self.refresh_worker: Optional[gui_worker.RefreshWorker] = None
        self.user_search_worker: Optional[gui_worker.UserSearchWorker] = None
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
        self.user_search_papers: List[Dict[str, Any]] = []

        # 创建 UI
        self.setup_ui()
        self.setup_connections()
        self.load_history_list()

        # 初始化时加载最新的报告（如果有）
        self.load_latest_report()

    def setup_ui(self):
        """创建所有 UI 组件和布局。"""
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局（垂直）
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 顶部工具栏
        self.create_toolbar()
        main_layout.addWidget(self.toolbar)

        # 2. 主分割器（左、中、右）
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter, stretch=1)

        # 左侧栏：历史列表
        self.left_panel = self.create_left_panel()
        self.main_splitter.addWidget(self.left_panel)

        # 中间栏：预览区
        self.middle_panel = self.create_middle_panel()
        self.main_splitter.addWidget(self.middle_panel)

        # 右侧栏：AI 聊天
        self.right_panel = self.create_right_panel()
        self.main_splitter.addWidget(self.right_panel)

        # 设置分割器初始比例
        self.main_splitter.setSizes([250, 600, 550])

        # 3. 底部状态栏
        self.create_status_bar()
        main_layout.addWidget(self.status_bar)

    def create_toolbar(self):
        """创建顶部工具栏。"""
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(24, 24))

        # 刷新按钮（保留但不显示在工具栏，因为每日推送已有刷新按钮）
        self.refresh_action = QAction("刷新", self)
        self.refresh_action.setToolTip("重新爬取并生成最新报告")
        self.refresh_action.triggered.connect(self.on_refresh_clicked)
        # 不添加到工具栏，仅用于启用/禁用状态管理
        # self.toolbar.addAction(self.refresh_action)

        # 全局设置按钮
        self.settings_action = QAction("全局设置", self)
        self.settings_action.setToolTip("配置 API、提示词等全局参数")
        self.settings_action.triggered.connect(self.on_settings_clicked)
        self.toolbar.addAction(self.settings_action)

        # 使全局设置按钮字体更大
        btn = self.toolbar.widgetForAction(self.settings_action)
        if btn:
            font = btn.font()
            font.setPointSize(14)
            btn.setFont(font)

        self.toolbar.addSeparator()

        # 标题标签（包含GitHub链接）
        title_label = QLabel("ARXIV-DAILY<br/><small>本项目地址：<a href='https://github.com/Vynje/Arxiv-Daily'>https://github.com/Vynje/Arxiv-Daily</a></small>")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setOpenExternalLinks(True)
        self.toolbar.addWidget(title_label)

        # 占位弹簧
        self.toolbar.addWidget(QLabel(""))  # 占位
        self.toolbar.addSeparator()

        # 日期显示
        self.date_label = QLabel(datetime.date.today().isoformat())
        self.toolbar.addWidget(self.date_label)

    def create_daily_push_panel(self) -> QWidget:
        """创建每日推送内容面板（上方）。"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题行（包含刷新按钮和设置按钮）
        title_layout = QHBoxLayout()
        title = QLabel("每日推送")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_layout.addWidget(title)
        title_layout.addStretch()
        self.daily_refresh_button = QPushButton("刷新")
        self.daily_refresh_button.setFixedSize(60, 30)
        self.daily_refresh_button.clicked.connect(self.on_refresh_clicked)
        title_layout.addWidget(self.daily_refresh_button)
        self.daily_settings_button = QPushButton("设置")
        self.daily_settings_button.setFixedSize(60, 30)
        title_layout.addWidget(self.daily_settings_button)
        layout.addLayout(title_layout)

        # 日期标签
        date_label = QLabel(datetime.date.today().strftime("%Y.%m.%d"))
        date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(date_label)

        # 列表控件
        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        layout.addWidget(self.history_list, stretch=1)

        # 按钮行
        button_layout = QHBoxLayout()
        self.load_button = QPushButton("加载选中")
        self.delete_button = QPushButton("删除")
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.delete_button)
        layout.addLayout(button_layout)

        return panel

    def create_user_search_panel(self) -> QWidget:
        """创建用户检索内容面板（下方）。"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题行（包含设置按钮）
        title_layout = QHBoxLayout()
        title = QLabel("用户检索")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_layout.addWidget(title)
        title_layout.addStretch()
        self.user_search_settings_button = QPushButton("设置")
        self.user_search_settings_button.setFixedSize(60, 30)
        title_layout.addWidget(self.user_search_settings_button)
        layout.addLayout(title_layout)

        # 搜索输入行（类似谷歌搜索样式）
        search_layout = QHBoxLayout()
        self.user_search_input = QPlainTextEdit()
        self.user_search_input.setObjectName("user_search_input")
        self.user_search_input.setPlaceholderText("输入检索关键词，点击设置可进行高级自定义")
        self.user_search_input.setMaximumBlockCount(3)  # 限制最多三行
        self.user_search_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        # 设置合适的高度
        font_metrics = self.user_search_input.fontMetrics()
        line_height = font_metrics.lineSpacing()
        self.user_search_input.setFixedHeight(line_height * 3 + 10)
        search_layout.addWidget(self.user_search_input, stretch=1)

        self.user_search_button = QPushButton("开始检索")
        self.user_search_button.setObjectName("user_search_button")
        self.user_search_button.setFixedSize(100, 30)
        search_layout.addWidget(self.user_search_button)
        layout.addLayout(search_layout)

        # 用户检索文档列表
        list_label = QLabel("历史文档")
        list_label_font = QFont()
        list_label_font.setBold(True)
        list_label_font.setPointSize(12)
        list_label.setFont(list_label_font)
        layout.addWidget(list_label)

        self.user_search_list = QListWidget()
        self.user_search_list.setObjectName("user_search_list")
        self.user_search_list.setAlternatingRowColors(True)
        layout.addWidget(self.user_search_list, stretch=1)

        # 按钮行（可选：生成摘要按钮已集成到检索流程中，但保留一个手动按钮）
        button_layout = QHBoxLayout()
        self.summarize_button = QPushButton("手动生成摘要")
        button_layout.addWidget(self.summarize_button)
        layout.addLayout(button_layout)

        return panel

    def create_left_panel(self) -> QWidget:
        """创建左侧面板，使用垂直分割器分为上下两部分。"""
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(6)
        splitter.setChildrenCollapsible(False)

        # 上方每日推送面板
        daily_panel = self.create_daily_push_panel()
        splitter.addWidget(daily_panel)

        # 下方用户检索面板
        user_panel = self.create_user_search_panel()
        splitter.addWidget(user_panel)

        # 设置初始分割比例（例如 60% 每日推送，40% 用户检索）
        splitter.setSizes([int(splitter.height() * 0.6), int(splitter.height() * 0.4)])

        return splitter

    def create_middle_panel(self) -> QWidget:
        """创建中间预览面板。"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        title = QLabel("报告预览")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 预览浏览器（支持 Markdown 渲染）
        self.preview_browser = QTextBrowser()
        self.preview_browser.setOpenExternalLinks(True)
        self.preview_browser.setReadOnly(True)
        self.preview_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #fefefe;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.preview_browser, stretch=1)

        # 选中文本提示
        self.selection_label = QLabel("选中文本后，可点击右侧栏“使用引用”按钮")
        self.selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selection_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.selection_label)

        return panel

    def create_right_panel(self) -> QWidget:
        """创建右侧 AI 聊天面板。"""
        # 使用我们之前写的 ChatWidget
        panel = gui_chat.ChatWidget()
        return panel

    def create_status_bar(self):
        """创建底部状态栏，包含进度条和状态消息。"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # 状态标签（支持自动换行，显示多行日志）
        self.status_label = QLabel("就绪")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(40)  # 增加高度以显示两行
        self.status_bar.addWidget(self.status_label, stretch=1)

    def setup_connections(self):
        """连接信号和槽。"""
        # 左侧列表
        self.history_list.itemClicked.connect(self.on_history_item_clicked)
        self.load_button.clicked.connect(self.load_selected_report)
        self.delete_button.clicked.connect(self.delete_selected_report)

        # 中间预览区的文本选中
        self.preview_browser.selectionChanged.connect(self.on_text_selected)

        # 自定义信号：文本选中传递给右侧栏
        self.text_selected.connect(self.right_panel.set_quote)

        # 每日推送设置按钮
        self.daily_settings_button.clicked.connect(self.on_daily_settings_clicked)
        # 用户检索设置按钮
        self.user_search_settings_button.clicked.connect(self.on_user_search_settings_clicked)

        # 用户检索功能按钮
        self.user_search_button.clicked.connect(self.on_search_clicked)
        self.summarize_button.clicked.connect(self.on_summarize_clicked)
        # 用户检索文档列表点击预览
        self.user_search_list.itemClicked.connect(self.on_user_search_item_clicked)

    def load_history_list(self):
        """加载 reports 目录下的历史报告文件到列表。"""
        self.history_list.clear()
        if not self.reports_dir.exists():
            return

        files = sorted(self.reports_dir.glob("*.md"), reverse=True)
        for f in files:
            date_str = f.stem
            try:
                # 尝试解析日期
                dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                display = dt.strftime("%Y.%m.%d")
            except ValueError:
                display = date_str
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            self.history_list.addItem(item)

    def load_latest_report(self):
        """加载最新的报告（reports/YYYY-MM-DD.md）。"""
        if not self.reports_dir.exists():
            return
        files = sorted(self.reports_dir.glob("*.md"), reverse=True)
        if files:
            latest_path = files[0]  # 最新的文件
            self.display_report(str(latest_path))
            self.current_report_path = str(latest_path)

    def on_history_item_clicked(self, item):
        """点击历史列表项时预览报告。"""
        path = item.data(Qt.ItemDataRole.UserRole)
        self.display_report(path)

    def load_selected_report(self):
        """加载选中的报告到预览区。"""
        items = self.history_list.selectedItems()
        if not items:
            QMessageBox.information(self, "提示", "请先选择一个报告")
            return
        path = items[0].data(Qt.ItemDataRole.UserRole)
        self.display_report(path)

    def delete_selected_report(self):
        """删除选中的报告文件。"""
        items = self.history_list.selectedItems()
        if not items:
            return
        path = items[0].data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除报告 {Path(path).name} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(path)
                self.load_history_list()
                self.status_label.setText(f"已删除 {Path(path).name}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {e}")

    def display_report(self, filepath: str):
        """读取 Markdown 文件并渲染到预览区。"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self.preview_browser.setPlainText(f"无法读取文件: {e}")
            return

        # 使用 Markdown 渲染器转换为 HTML
        html = gui_markdown.render_markdown(content)
        self.preview_browser.setHtml(html)
        self.current_report_path = filepath
        self.status_label.setText(f"已加载 {Path(filepath).name}")

    def on_text_selected(self):
        """当用户在预览区选中文本时，将文本发送到右侧栏。"""
        cursor = self.preview_browser.textCursor()
        selected = cursor.selectedText().strip()
        if selected:
            self.text_selected.emit(selected)
            self.selection_label.setText(f"已选中: {selected[:50]}...")
        else:
            self.selection_label.setText("选中文本后，可点击右侧栏“使用引用”按钮")

    def on_refresh_clicked(self):
        """点击刷新按钮，启动后台任务。"""
        if self.refresh_worker and self.refresh_worker.isRunning():
            QMessageBox.information(self, "提示", "已有任务正在运行，请稍候")
            return

        # 禁用刷新按钮
        self.refresh_action.setEnabled(False)
        self.status_label.setText("开始爬取和生成摘要...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # 创建工作线程
        self.refresh_worker = gui_worker.RefreshWorker()
        self.refresh_worker.progress.connect(self.on_worker_progress)
        self.refresh_worker.progress_percent.connect(self.on_worker_percent)
        self.refresh_worker.finished.connect(self.on_worker_finished)
        self.refresh_worker.error.connect(self.on_worker_error)
        self.refresh_worker.start()

    def on_worker_progress(self, message: str):
        """接收工作线程的进度消息。"""
        self.status_label.setText(message)

    def on_worker_percent(self, percent: int):
        """接收工作线程的百分比进度。"""
        self.progress_bar.setValue(percent)

    def on_worker_finished(self, report_path: str):
        """后台任务完成。"""
        self.refresh_action.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("任务完成")

        if report_path:
            # 重新加载历史列表
            self.load_history_list()
            # 显示新生成的报告
            self.display_report(report_path)
            QMessageBox.information(self, "完成", "报告已生成并保存。")
        else:
            # 检查是否存在今天的报告文件
            today = datetime.date.today().isoformat()
            today_report = self.reports_dir / f"{today}.md"
            if today_report.exists():
                reply = QMessageBox.question(
                    self,
                    "未找到新论文",
                    "未找到新论文，是否重新生成今天的报告（覆盖现有报告）？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    # 将现有文件视为报告路径
                    report_path = str(today_report)
                    self.load_history_list()
                    self.display_report(report_path)
                    QMessageBox.information(self, "完成", "报告已重新生成。")
                else:
                    QMessageBox.information(self, "完成", "未找到新论文，报告未更新。")
            else:
                QMessageBox.information(self, "完成", "未找到新论文，报告未更新。")

    def on_worker_error(self, error_msg: str):
        """后台任务出错。"""
        self.refresh_action.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("任务出错")
        QMessageBox.critical(self, "后台任务错误", error_msg)

    def on_daily_settings_clicked(self):
        """点击每日推送的设置按钮。"""
        dialog = SearchSettingsDialog("DAILY_PUSH_", "每日推送设置", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.save_config()
            self.status_label.setText("每日推送配置已保存")

    def on_user_search_settings_clicked(self):
        """点击用户检索的设置按钮。"""
        dialog = SearchSettingsDialog("USER_SEARCH_", "用户检索设置", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.save_config()
            self.status_label.setText("用户检索配置已保存")

    @pyqtSlot(str)
    def on_user_search_progress(self, message):
        """处理用户检索进度消息。"""
        self.status_label.setText(message)

    @pyqtSlot(int)
    def on_user_search_progress_percent(self, percent):
        """处理用户检索进度百分比（可选）。"""
        # 如果需要，可以更新进度条，目前仅记录
        pass

    @pyqtSlot(list, str)
    def on_user_search_finished(self, papers, report_path):
        """用户检索任务完成。"""
        self.user_search_papers = papers
        # 更新文档列表
        if report_path:
            filename = Path(report_path).name
            item = QListWidgetItem(filename)
            item.setData(Qt.ItemDataRole.UserRole, report_path)
            self.user_search_list.addItem(item)
            self.user_search_list.scrollToBottom()
            self.status_label.setText(f"检索完成，已生成文档 {filename}")
            QMessageBox.information(self, "完成", f"已生成摘要文档：{filename}")
        else:
            self.status_label.setText("检索完成，无结果")
            QMessageBox.information(self, "结果", "未找到符合条件的论文。")
        # 清理 worker
        if self.user_search_worker:
            self.user_search_worker.quit()
            self.user_search_worker.wait()
            self.user_search_worker = None
        # 重新启用按钮
        self.user_search_button.setEnabled(True)

    @pyqtSlot(str)
    def on_user_search_error(self, error_msg):
        """用户检索任务出错。"""
        self.status_label.setText("检索失败")
        QMessageBox.critical(self, "错误", f"检索过程中出错:\n{error_msg}")
        # 清理 worker
        if self.user_search_worker:
            self.user_search_worker.quit()
            self.user_search_worker.wait()
            self.user_search_worker = None
        # 重新启用按钮
        self.user_search_button.setEnabled(True)

    def on_search_clicked(self):
        """点击开始检索按钮，启动后台线程执行用户检索并自动生成摘要文档。"""
        keywords_text = self.user_search_input.toPlainText().strip()
        if not keywords_text:
            QMessageBox.warning(self, "警告", "请输入关键词")
            return

        # 将换行符替换为逗号，然后按逗号分割
        import re
        # 将任何空白字符（包括换行、空格、制表符）序列替换为逗号
        normalized = re.sub(r'\s+', ',', keywords_text)
        keywords = [k.strip() for k in normalized.split(",") if k.strip()]
        if not keywords:
            QMessageBox.warning(self, "警告", "关键词无效")
            return

        # 获取配置中的日期范围
        cfg = config.load_config()
        start_date = cfg.get("USER_SEARCH_START_DATE")
        end_date = cfg.get("USER_SEARCH_END_DATE")
        filter_days = cfg.get("USER_SEARCH_FILTER_DAYS", cfg.get("FILTER_DAYS", 1))

        # 如果已有 worker 正在运行，先停止
        if self.user_search_worker and self.user_search_worker.isRunning():
            self.user_search_worker.quit()
            self.user_search_worker.wait()

        # 创建新的 worker，传递日期范围（如果存在）
        self.user_search_worker = gui_worker.UserSearchWorker(keywords, filter_days,
                                                               start_date=start_date,
                                                               end_date=end_date)
        # 连接信号
        self.user_search_worker.progress.connect(self.on_user_search_progress)
        self.user_search_worker.progress_percent.connect(self.on_user_search_progress_percent)
        self.user_search_worker.finished.connect(self.on_user_search_finished)
        self.user_search_worker.error.connect(self.on_user_search_error)
        # 禁用按钮，防止重复点击
        self.user_search_button.setEnabled(False)
        # 启动线程
        self.user_search_worker.start()
        self.status_label.setText(f"正在后台检索关键词: {', '.join(keywords)}...")

    def on_summarize_clicked(self):
        """手动为当前用户检索结果重新生成摘要（如果存在）。"""
        if not self.user_search_papers:
            QMessageBox.warning(self, "警告", "暂无检索结果，请先执行检索")
            return

        import summarizer
        import report_generator
        from pathlib import Path
        import datetime

        self.status_label.setText("正在重新生成摘要...")
        QApplication.processEvents()

        try:
            cfg = config.load_config()
            # 重新生成摘要（可能使用更新的提示词）
            summarized_papers = summarizer.batch_summarize(self.user_search_papers)
            self.user_search_papers = summarized_papers

            # 生成报告内容
            report_content = report_generator.generate_report_content(summarized_papers, cfg)

            # 保存新报告文件（新时间戳）
            user_reports_dir = Path("reports/user")
            user_reports_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            filename = f"{timestamp}_manual.md"
            report_path = user_reports_dir / filename
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)

            # 更新文档列表
            item = QListWidgetItem(filename)
            item.setData(Qt.ItemDataRole.UserRole, str(report_path))
            self.user_search_list.addItem(item)
            self.user_search_list.scrollToBottom()

            self.status_label.setText(f"已重新生成摘要文档 {filename}")
            QMessageBox.information(self, "完成", f"已重新生成摘要文档：{filename}")
        except Exception as e:
            self.status_label.setText("生成摘要失败")
            QMessageBox.critical(self, "错误", f"生成摘要过程中出错: {e}")

    def on_user_search_item_clicked(self, item):
        """点击用户检索文档列表项，预览文档。"""
        path = item.data(Qt.ItemDataRole.UserRole)
        self.display_report(path)

    def on_settings_clicked(self):
        """点击设置按钮，打开设置对话框。"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.save_config()
            self.status_label.setText("配置已保存")


def main():
    """应用程序入口点。"""
    app = QApplication(sys.argv)
    app.setApplicationName("ARXIV-DAILY")
    app.setOrganizationName("ARXIV-DAILY")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()