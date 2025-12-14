"""
AI 聊天模块，用于右侧栏的提问功能。
"""
import json
import sys
import threading
import time
import re
from typing import Optional

from PyQt6.QtCore import (
    QThread, pyqtSignal, pyqtSlot, Qt, QTimer
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QTextEdit, QPushButton, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtGui import QFont, QTextCursor, QColor

from config import get_config_value
import openai
import gui_markdown

class ChatWorker(QThread):
    """
    在后台线程中执行 AI 聊天请求的工作线程。
    """
    # 信号：请求完成时发送回复文本
    finished = pyqtSignal(str)
    # 信号：请求失败时发送错误信息
    error = pyqtSignal(str)
    # 信号：请求开始（用于 UI 状态更新）
    started = pyqtSignal()
    # 信号：请求结束（无论成功失败）
    ended = pyqtSignal()

    def __init__(self, prompt: str, parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self._is_running = True

    def run(self):
        """执行 API 调用。"""
        self.started.emit()
        try:
            reply = self.call_api(self.prompt)
            self.finished.emit(reply)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.ended.emit()

    def call_api(self, prompt: str) -> str:
        """
        调用硅基流动 API 进行聊天。
        使用 config 中的配置。
        """
        base_url = get_config_value("BASE_URL")
        model_id = get_config_value("MODEL_ID")
        api_key = get_config_value("API_KEY")
        max_retries = get_config_value("MAX_RETRIES", 3)
        retry_delay = get_config_value("RETRY_DELAY", 2)

        if not api_key:
            raise ValueError("API Key 未配置，请在设置中填写。")

        client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
        )

        messages = [
            {"role": "system", "content": "你是一个科研助手，请根据用户提供的论文摘要片段和问题，给出详细、专业的回答。"},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=0.5,
                    max_tokens=800,
                )
                reply = response.choices[0].message.content.strip()
                return reply
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise e
        raise Exception("达到最大重试次数，请求失败。")

    def stop(self):
        """停止线程（如果支持）。"""
        self._is_running = False
        self.terminate()


class ChatWidget(QWidget):
    """
    聊天界面组件。
    """
    # 信号：当用户发送消息时，可以用于外部记录
    message_sent = pyqtSignal(str)
    message_received = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.quote_text = ""  # 当前引用的文本
        self.worker = None   # 当前工作线程
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """创建 UI 布局和组件。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 标题
        title_label = QLabel("AI 问答助手")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # 引用区域
        quote_frame = QFrame()
        quote_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        quote_layout = QVBoxLayout(quote_frame)
        quote_layout.setContentsMargins(6, 6, 6, 6)
        quote_title = QLabel("引用内容")
        quote_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        quote_layout.addWidget(quote_title)
        self.quote_display = QLabel("（未选择任何文本）")
        self.quote_display.setWordWrap(True)
        self.quote_display.setStyleSheet("color: #666; font-style: italic;")
        quote_layout.addWidget(self.quote_display)
        main_layout.addWidget(quote_frame)

        # 消息历史显示区域
        self.history_browser = QTextBrowser()
        self.history_browser.setReadOnly(True)
        self.history_browser.setMinimumHeight(300)
        self.history_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #f9f9f9;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        main_layout.addWidget(self.history_browser, stretch=1)

        # 输入区域
        input_layout = QVBoxLayout()
        input_label = QLabel("输入问题：")
        input_label.setFont(QFont("Arial", 10))
        input_layout.addWidget(input_label)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("请输入你的问题...（可以结合上方引用的内容）")
        self.input_edit.setMaximumHeight(100)
        input_layout.addWidget(self.input_edit)

        # 按钮行
        button_layout = QHBoxLayout()
        self.send_button = QPushButton("发送")
        self.send_button.setFixedWidth(80)
        self.clear_button = QPushButton("清除")
        self.clear_button.setFixedWidth(80)
        self.quote_button = QPushButton("使用引用")
        self.quote_button.setFixedWidth(80)
        self.quote_button.setToolTip("将当前引用内容插入输入框")
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.quote_button)
        button_layout.addStretch()
        input_layout.addLayout(button_layout)

        main_layout.addLayout(input_layout)

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 12px;")
        main_layout.addWidget(self.status_label)

    def setup_connections(self):
        """连接信号和槽。"""
        self.send_button.clicked.connect(self.send_message)
        self.clear_button.clicked.connect(self.clear_input)
        self.quote_button.clicked.connect(self.insert_quote)

    @pyqtSlot(str)
    def set_quote(self, text: str):
        """
        设置引用的文本（从中栏选择而来）。
        """
        self.quote_text = text.strip()
        if self.quote_text:
            # 截断过长的文本
            display = self.quote_text[:200] + ("..." if len(self.quote_text) > 200 else "")
            self.quote_display.setText(display)
        else:
            self.quote_display.setText("（未选择任何文本）")

    def insert_quote(self):
        """将引用文本插入输入框。"""
        if self.quote_text:
            cursor = self.input_edit.textCursor()
            cursor.insertText(self.quote_text)
            self.input_edit.setTextCursor(cursor)

    def send_message(self):
        """发送用户输入的消息。"""
        user_text = self.input_edit.toPlainText().strip()
        if not user_text:
            self.status_label.setText("请输入问题")
            return

        # 构建完整的提示
        if self.quote_text:
            prompt = f"引用内容：\n{self.quote_text}\n\n用户问题：\n{user_text}"
        else:
            prompt = user_text

        # 在历史中显示用户消息
        self.append_message("用户", user_text, is_user=True)

        # 清空输入框
        self.input_edit.clear()
        self.status_label.setText("正在思考...")
        self.send_button.setEnabled(False)

        # 启动工作线程
        self.worker = ChatWorker(prompt)
        self.worker.finished.connect(self.on_reply_received)
        self.worker.error.connect(self.on_reply_error)
        self.worker.started.connect(lambda: self.status_label.setText("正在请求 AI..."))
        self.worker.ended.connect(self.on_request_ended)
        self.worker.start()

    def on_reply_received(self, reply: str):
        """收到 AI 回复。"""
        self.append_message("AI", reply, is_user=False)
        self.status_label.setText("回复已接收")
        self.message_received.emit(reply)

    def on_reply_error(self, error_msg: str):
        """请求出错。"""
        self.append_message("系统", f"错误: {error_msg}", is_user=False)
        self.status_label.setText(f"错误: {error_msg}")

    def on_request_ended(self):
        """请求结束（无论成功或失败）。"""
        self.send_button.setEnabled(True)

    def _markdown_to_html_fragment(self, text: str) -> str:
        """将 Markdown 文本转换为适合在聊天气泡中显示的 HTML 片段。"""
        full_html = gui_markdown.render_markdown(text)
        # 提取 <style> 部分
        style_match = re.search(r'<style>(.*?)</style>', full_html, re.DOTALL)
        style = style_match.group(1) if style_match else ''
        # 提取 <body> 内容
        body_match = re.search(r'<body>(.*?)</body>', full_html, re.DOTALL)
        if body_match:
            body_content = body_match.group(1).strip()
        else:
            # 如果没有 body 标签，则回退到完整 HTML
            body_content = full_html
        # 构建片段：将样式内联（放在 <style> 标签中）
        fragment = f'<style>{style}</style>{body_content}'
        return fragment

    def append_message(self, sender: str, content: str, is_user: bool):
        """向历史浏览器添加一条消息。"""
        timestamp = time.strftime("%H:%M:%S")
        color = "#0066cc" if is_user else "#009933"
        align = "right" if is_user else "left"
        
        # 决定是否渲染 Markdown
        # 对于 AI 回复和用户消息都渲染，但系统消息不渲染
        if sender in ("AI", "用户"):
            try:
                rendered = self._markdown_to_html_fragment(content)
                # 将渲染后的 HTML 放入气泡中
                inner_html = rendered
            except Exception as e:
                # 如果渲染失败，回退到纯文本
                inner_html = content.replace("\n", "<br/>")
        else:
            inner_html = content.replace("\n", "<br/>")
        
        html = f"""
        <div style="margin-bottom: 10px; text-align: {align};">
            <span style="font-size: 11px; color: #999;">{timestamp} <b>{sender}</b></span><br/>
            <div style="background-color: {color}; color: white; padding: 8px; border-radius: 8px;
                 display: inline-block; max-width: 80%; text-align: left; word-wrap: break-word;">
                {inner_html}
            </div>
        </div>
        """
        self.history_browser.append(html)
        # 滚动到底部
        cursor = self.history_browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.history_browser.setTextCursor(cursor)

    def clear_input(self):
        """清空输入框。"""
        self.input_edit.clear()
        self.status_label.setText("已清空输入")

    def clear_history(self):
        """清空聊天历史。"""
        self.history_browser.clear()
        self.status_label.setText("历史已清空")


if __name__ == "__main__":
    # 简单的测试窗口
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = ChatWidget()
    window.setWindowTitle("聊天测试")
    window.resize(500, 700)
    window.show()
    sys.exit(app.exec())