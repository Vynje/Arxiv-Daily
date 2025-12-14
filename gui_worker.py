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
import config
import report_generator
from pathlib import Path


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
            self.papers = scraper.scrape_all("DAILY_PUSH_")
            self.progress_percent.emit(30)
            if not self.papers:
                self.progress.emit("未找到新论文，将生成空报告。")

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

            # 步骤3：决定是否保存报告
            today = datetime.date.today().isoformat()
            date_file = f"reports/{today}.md"
            report_exists = os.path.exists(date_file)

            # 如果论文为空且报告已存在，则发送空路径（让 GUI 询问是否覆盖）
            if not self.papers and report_exists:
                self.progress.emit("未找到新论文，且今日报告已存在。")
                self.progress_percent.emit(100)
                self.progress.emit("任务完成！")
                self.finished.emit("")  # 空路径表示无新内容
            else:
                # 否则保存报告（覆盖或新建）
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

        # 使用 report_generator 写入报告
        report_generator.write_report(self.papers, date_file)

        return date_file


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


class UserSearchWorker(QThread):
    """执行用户检索任务的工作线程"""

    # 信号定义
    progress = pyqtSignal(str)          # 进度消息
    progress_percent = pyqtSignal(int)  # 进度百分比 (0-100)
    finished = pyqtSignal(list, str)    # 任务完成，参数为论文列表和报告文件路径
    error = pyqtSignal(str)             # 错误消息

    def __init__(self, keywords, filter_days, start_date=None, end_date=None):
        super().__init__()
        self.keywords = keywords
        self.filter_days = filter_days
        self.start_date = start_date
        self.end_date = end_date
        self.papers: List[Dict[str, Any]] = []
        self._original_stdout = None
        self._original_stderr = None
        self._log_handler = None

    def run(self):
        """线程主函数"""
        try:
            self._setup_output_redirection()

            self.progress.emit("正在加载配置...")
            cfg = config.load_config()
            self.progress_percent.emit(5)

            # 爬取论文
            all_papers = []
            total_keywords = len(self.keywords)
            for i, keyword in enumerate(self.keywords):
                self.progress.emit(f"正在检索关键词 '{keyword}'...")
                if self.start_date and self.end_date:
                    papers = scraper.fetch_papers(keyword, None, cfg,
                                                  start_date=self.start_date,
                                                  end_date=self.end_date)
                else:
                    papers = scraper.fetch_papers(keyword, self.filter_days, cfg)
                all_papers.extend(papers)
                self.progress_percent.emit(5 + int((i + 1) / total_keywords * 30))
                self.progress.emit(f"已检索 '{keyword}'，找到 {len(papers)} 篇论文")

            # 过滤 Remote Sensing
            self.progress.emit("正在过滤 Remote Sensing 论文...")
            all_papers = scraper.filter_remote_sensing(all_papers, cfg)
            # 黑名单过滤
            all_papers = scraper.filter_blacklist(all_papers, cfg)
            # 去重
            all_papers = scraper.deduplicate_papers(all_papers)
            self.progress_percent.emit(40)

            if not all_papers:
                self.progress.emit("检索完成，无结果")
                self.finished.emit([], "")
                return

            self.progress.emit(f"找到 {len(all_papers)} 篇论文，正在生成摘要...")
            # 生成摘要
            summarized_papers = summarizer.batch_summarize(all_papers)
            self.papers = summarized_papers
            self.progress_percent.emit(70)

            # 生成报告内容
            report_content = report_generator.generate_report_content(summarized_papers, cfg)

            # 保存报告文件
            user_reports_dir = Path("reports/user")
            user_reports_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            filename = f"{timestamp}.md"
            report_path = user_reports_dir / filename
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)

            self.progress_percent.emit(100)
            self.progress.emit("任务完成！")
            self.finished.emit(summarized_papers, str(report_path))

        except Exception as e:
            error_msg = f"用户检索任务出错: {e}\n{traceback.format_exc()}"
            self.error.emit(error_msg)
        finally:
            self._restore_output_redirection()

    def _setup_output_redirection(self):
        """重定向 stdout/stderr 和日志到进度信号。"""
        # 与 RefreshWorker 相同
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        class EmittingStream:
            def __init__(self, signal, original_stdout):
                self.signal = signal
                self.original_stdout = original_stdout

            def write(self, text):
                self.original_stdout.write(text)
                lines = text.rstrip('\n').split('\n')
                for line in lines:
                    if line.strip():
                        self.signal.emit(line)
                return len(text)

            def flush(self):
                pass

        self._emitting_stream = EmittingStream(self.progress, self._original_stdout)
        sys.stdout = self._emitting_stream
        sys.stderr = self._emitting_stream

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
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
    content = report_generator.generate_report_content(worker.papers)
    print(content[:200])