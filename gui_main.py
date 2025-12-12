"""
ARXIV-DAILY 图形用户界面主窗口。
"""
import os
import sys
import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QToolBar, QStatusBar, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QTextBrowser, QDialog, QLineEdit, QFormLayout,
    QDialogButtonBox, QMessageBox, QProgressBar, QFrame, QSizePolicy,
    QPlainTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QSize
from PyQt6.QtGui import QIcon, QFont, QAction, QTextCursor, QTextCharFormat, QBrush, QColor

# 自定义模块
import gui_config
import gui_markdown
import gui_chat
import gui_worker


class SettingsDialog(QDialog):
    """设置对话框，用于配置 API Key、BaseURL、模型ID、自定义提示词和关键词。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(700, 450)  # 增加宽度和高度以容纳更大的输入框
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setMinimumWidth(500)  # 宽度增加
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setMinimumWidth(500)
        self.model_id_edit = QLineEdit()
        self.model_id_edit.setMinimumWidth(500)

        # 自定义提示词使用多行纯文本编辑框
        self.system_prompt_edit = QPlainTextEdit()
        self.system_prompt_edit.setPlaceholderText("可选，留空则使用默认提示词")
        self.system_prompt_edit.setMinimumHeight(80)
        self.system_prompt_edit.setMinimumWidth(500)

        # 关键词也使用多行编辑框，支持换行和逗号分隔
        self.keywords_edit = QPlainTextEdit()
        self.keywords_edit.setPlaceholderText(
            "每行一个关键词，或用逗号分隔。例如：\nGaussian Splatting\nRemote Sensing"
        )
        self.keywords_edit.setMinimumHeight(60)
        self.keywords_edit.setMinimumWidth(500)

        layout.addRow("API Key:", self.api_key_edit)
        layout.addRow("Base URL:", self.base_url_edit)
        layout.addRow("模型 ID:", self.model_id_edit)
        layout.addRow("自定义提示词:", self.system_prompt_edit)
        layout.addRow("关键词:", self.keywords_edit)

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
        """从 gui_config 加载当前配置并填充到输入框。"""
        cfg = gui_config.load_config()
        self.api_key_edit.setText(cfg.get("API_KEY", ""))
        self.base_url_edit.setText(cfg.get("BASE_URL", ""))
        self.model_id_edit.setText(cfg.get("MODEL_ID", ""))
        self.system_prompt_edit.setPlainText(cfg.get("SYSTEM_PROMPT", ""))
        # 关键词：列表转换为逗号分隔字符串（或每行一个）
        keywords = cfg.get("KEYWORDS", [])
        if isinstance(keywords, list):
            # 用逗号加空格连接，同时每行一个也可以
            self.keywords_edit.setPlainText(", ".join(keywords))
        else:
            self.keywords_edit.setPlainText(str(keywords))

    def save_config(self):
        """将输入框的值保存到配置文件。"""
        # 解析关键词文本：支持逗号分隔和换行分隔
        keywords_text = self.keywords_edit.toPlainText().strip()
        keywords = []
        if keywords_text:
            # 按换行分割，然后按逗号分割
            lines = keywords_text.splitlines()
            for line in lines:
                parts = line.split(",")
                for part in parts:
                    stripped = part.strip()
                    if stripped:
                        keywords.append(stripped)
        # 如果为空，则保留空列表（将使用默认值）

        cfg = {
            "API_KEY": self.api_key_edit.text().strip(),
            "BASE_URL": self.base_url_edit.text().strip(),
            "MODEL_ID": self.model_id_edit.text().strip(),
            "SYSTEM_PROMPT": self.system_prompt_edit.toPlainText().strip(),
            "KEYWORDS": keywords,
        }
        gui_config.save_config(cfg)
        # 注意：不再需要 apply_to_module，因为 scraper 和 summarizer 会动态加载配置


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
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)

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

        # 刷新按钮
        self.refresh_action = QAction("刷新", self)
        self.refresh_action.setToolTip("重新爬取并生成最新报告")
        self.refresh_action.triggered.connect(self.on_refresh_clicked)
        self.toolbar.addAction(self.refresh_action)

        # 设置按钮
        self.settings_action = QAction("设置", self)
        self.settings_action.setToolTip("配置 API 等参数")
        self.settings_action.triggered.connect(self.on_settings_clicked)
        self.toolbar.addAction(self.settings_action)

        self.toolbar.addSeparator()

        # 标题标签
        title_label = QLabel("ARXIV-DAILY")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toolbar.addWidget(title_label)

        # 占位弹簧
        self.toolbar.addWidget(QLabel(""))  # 占位
        self.toolbar.addSeparator()

        # 日期显示
        self.date_label = QLabel(datetime.date.today().isoformat())
        self.toolbar.addWidget(self.date_label)

    def create_left_panel(self) -> QWidget:
        """创建左侧历史列表面板。"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        title = QLabel("历史报告")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 日期选择器（简化：仅显示当前日期）
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
            QMessageBox.information(self, "完成", "未找到新论文，报告未更新。")

    def on_worker_error(self, error_msg: str):
        """后台任务出错。"""
        self.refresh_action.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("任务出错")
        QMessageBox.critical(self, "后台任务错误", error_msg)

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