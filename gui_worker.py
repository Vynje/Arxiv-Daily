"""
后台工作线程模块，用于执行爬虫和摘要生成任务。
"""
import os
import sys
import datetime
import traceback
import logging
import io
from typing import List, Dict, Any

from PyQt6.QtCore import QThread, pyqtSignal

import scraper
import summarizer
import gui_config


class RefreshWorker(QThread):
    """执行刷新任务的工作线程"""

    # 信号定义
    progress = pyqtSignal(str)          # 进度消息
    progress_percent = pyqtSignal(int)  # 进度百分比 (0-100)
    finished = pyqtSignal(str)          # 任务完成，参数为报告文件路径
    error = pyqtSignal(str)             # 错误消息

    def __init__(self):
        super().__init__()
        self.papers: List[Dict[str, Any]] = []
        self._original_stdout = None
        self._original_stderr = None
        self._log_handler = None

    def run(self):
        """线程主函数"""
        try:
            # 设置日志和输出重定向
            self._setup_output_redirection()

            # 步骤0：加载配置（确保使用最新配置）
            self.progress.emit("正在加载配置...")
            # 无需额外操作，因为 scraper 和 summarizer 会自己加载配置
            self.progress_percent.emit(5)

            # 步骤1：爬取论文
            self.progress.emit("正在爬取 arXiv 论文...")
            self.papers = scraper.scrape_all()
            if not self.papers:
                self.progress.emit("未找到新论文。")
                self.progress_percent.emit(100)
                self.finished.emit("")  # 空路径表示无新内容
                return
            self.progress_percent.emit(30)

            # 步骤2：生成摘要
            total = len(self.papers)
            for i, paper in enumerate(self.papers):
                self.progress.emit(f"正在生成摘要 ({i+1}/{total}): {paper['title'][:50]}...")
                # 注意：batch_summarize 会原地添加 summary 字段
                # 但我们希望逐篇处理以更新进度
                # 为了简单，我们直接调用 summarizer.summarize_abstract
                # 但 batch_summarize 内部有重试和延迟，我们直接使用它
                pass
            # 直接调用 batch_summarize 并更新进度
            self.progress.emit("正在批量生成中文摘要...")
            self.papers = summarizer.batch_summarize(self.papers)
            self.progress_percent.emit(70)

            # 步骤3：保存报告
            self.progress.emit("正在保存报告...")
            report_path = self._save_reports()
            self.progress_percent.emit(100)
            self.progress.emit("任务完成！")
            self.finished.emit(report_path)

        except Exception as e:
            error_msg = f"后台任务出错: {e}\n{traceback.format_exc()}"
            self.error.emit(error_msg)
        finally:
            # 恢复原始输出
            self._restore_output_redirection()

    def _setup_output_redirection(self):
        """重定向 stdout/stderr 和日志到进度信号。"""
        # 保存原始流
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        # 创建自定义流，将写入的内容发送到进度信号
        class EmittingStream:
            def __init__(self, signal, original_stdout):
                self.signal = signal
                self.original_stdout = original_stdout

            def write(self, text):
                # 调用原始流以保持终端输出
                self.original_stdout.write(text)
                # 发送到信号（按行分割）
                lines = text.rstrip('\n').split('\n')
                for line in lines:
                    if line.strip():
                        self.signal.emit(line)
                return len(text)

            def flush(self):
                pass

        # 创建流实例
        self._emitting_stream = EmittingStream(self.progress, self._original_stdout)
        # 重定向 stdout 和 stderr
        sys.stdout = self._emitting_stream
        sys.stderr = self._emitting_stream

        # 配置日志处理器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)  # 确保 INFO 级别日志被捕获
        self._log_handler = LogSignalHandler(self.progress)
        self._log_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(name)s: %(message)s')
        self._log_handler.setFormatter(formatter)
        root_logger.addHandler(self._log_handler)

    def _restore_output_redirection(self):
        """恢复原始 stdout/stderr 并移除日志处理器。"""
        if self._original_stdout:
            sys.stdout = self._original_stdout
        if self._original_stderr:
            sys.stderr = self._original_stderr
        if self._log_handler:
            root_logger = logging.getLogger()
            root_logger.removeHandler(self._log_handler)
            self._log_handler = None

    def _save_reports(self) -> str:
        """
        保存报告到 reports/YYYY-MM-DD.md（按日期归档）。
        返回报告文件路径。
        """
        import os
        import datetime

        # 确保 reports 目录存在
        os.makedirs("reports", exist_ok=True)

        today = datetime.date.today().isoformat()
        date_file = f"reports/{today}.md"

        # 构建报告内容
        content = self._generate_report_content()

        # 写入日期文件（覆盖）
        with open(date_file, "w", encoding="utf-8") as f:
            f.write(content)

        return date_file

    def _generate_report_content(self) -> str:
        """根据 self.papers 生成 Markdown 报告内容"""
        # 按类别分组
        categories = {}
        for paper in self.papers:
            cat = paper["category"]
            categories.setdefault(cat, []).append(paper)

        lines = []
        today = datetime.date.today().isoformat()
        lines.append(f"# 每日论文报告 ({today})\n\n")

        for cat in sorted(categories.keys()):
            lines.append(f"## {cat}\n\n")
            for paper in categories[cat]:
                title = paper["title"]
                link = paper["link"]
                authors = ", ".join(paper["authors"][:5])
                if len(paper["authors"]) > 5:
                    authors += " 等"
                date = paper["date"]
                abstract = paper["abstract"].replace("\n", " ")
                summary = paper.get("summary", "")

                lines.append(f"### [{title}]({link})\n")
                lines.append(f"- **作者**: {authors}\n")
                lines.append(f"- **日期**: {date}\n")
                lines.append(f"- **摘要**: {abstract[:300]}...\n")
                if summary:
                    lines.append(f"- **中文总结**:\n{summary}\n")
                else:
                    lines.append(f"- **中文总结**: (生成失败)\n")
                lines.append("\n")

        return "".join(lines)


class LogSignalHandler(logging.Handler):
    """将日志记录发送到 PyQt 信号的自定义处理器。"""

    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        try:
            msg = self.format(record)
            self.signal.emit(msg)
        except Exception:
            pass


if __name__ == "__main__":
    # 简单测试
    print("测试 RefreshWorker 的生成内容...")
    worker = RefreshWorker()
    # 模拟一些数据
    worker.papers = [
        {
            "title": "Test Paper",
            "link": "https://arxiv.org/abs/1234.5678",
            "authors": ["Author A", "Author B"],
            "date": datetime.date.today(),
            "abstract": "This is a test abstract.",
            "summary": "这是一个测试总结。",
            "category": "Gaussian Splatting",
        }
    ]
    content = worker._generate_report_content()
    print(content[:200])