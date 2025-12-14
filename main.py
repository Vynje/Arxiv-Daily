#!/usr/bin/env python3
"""
ARXIV-DAILY 主入口点。

如果 PyQt6 可用，则启动图形用户界面 (GUI)。
否则，回退到命令行界面 (CLI) 生成报告。
"""
import os
import sys
import datetime
from typing import List, Dict, Any

import report_generator


def cli_main():
    """命令行界面主函数"""
    from scraper import scrape_all
    from summarizer import batch_summarize

    print("开始爬取 arXiv 论文...")
    papers = scrape_all()
    if not papers:
        print("未找到新论文，退出。")
        return

    print("生成中文摘要...")
    papers = batch_summarize(papers)

    # 确定报告路径：reports/YYYY-MM-DD.md
    os.makedirs("reports", exist_ok=True)
    today = datetime.date.today().isoformat()
    report_path = f"reports/{today}.md"

    print("生成报告...")
    report_generator.write_report(papers, report_path)

    print(f"完成！报告已保存至 {report_path}")

def gui_main():
    """图形用户界面主函数"""
    try:
        from gui_main import main as gui_entry
        gui_entry()
    except ImportError as e:
        print(f"无法导入 GUI 模块: {e}")
        print("请确保已安装 PyQt6 和相关依赖。")
        sys.exit(1)

def main():
    # 检查是否安装了 PyQt6
    try:
        import PyQt6
        # 如果用户明确要求 CLI（例如通过参数），则使用 CLI
        if len(sys.argv) > 1 and sys.argv[1] == "--cli":
            cli_main()
        else:
            gui_main()
    except ImportError:
        print("PyQt6 未安装，使用命令行界面 (CLI)。")
        cli_main()

if __name__ == "__main__":
    main()