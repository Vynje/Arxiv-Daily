#!/usr/bin/env python3
"""
报告生成模块，用于生成 Markdown 格式的每日论文报告。
"""
import datetime
from typing import List, Dict, Any, Optional

import config


def generate_report_content(
    papers: List[Dict[str, Any]],
    config_dict: Optional[Dict[str, Any]] = None
) -> str:
    """
    根据论文列表生成 Markdown 报告内容。

    Args:
        papers: 论文字典列表，每个字典包含 title, link, authors, date, abstract, category, summary 等字段。
        config_dict: 可选的配置字典。如果为 None，则从配置文件加载。

    Returns:
        Markdown 格式的报告字符串。
    """
    if config_dict is None:
        config_dict = config.load_config()

    # 如果没有论文，生成占位符消息
    if not papers:
        filter_days = config_dict.get("FILTER_DAYS", 1)
        keywords = config_dict.get("KEYWORDS", [])
        blacklist = config_dict.get("BLACKLIST_KEYWORDS", [])
        today = datetime.date.today().isoformat()
        lines = [
            f"# 每日论文报告 ({today})\n\n",
            "## 今日无新论文\n\n",
            f"**可能的原因**:\n",
            f"- 时间范围: 过去 {filter_days} 天内\n",
            f"- 关键词: {', '.join(keywords) if keywords else '无'}\n",
        ]
        if blacklist:
            lines.append(f"- 黑名单关键词: {', '.join(blacklist)}\n")
        lines.append("\n")
        lines.append("建议：\n")
        lines.append("1. 检查网络连接和 arXiv API 可用性。\n")
        lines.append("2. 调整设置中的时间范围（FILTER_DAYS）或关键词。\n")
        lines.append("3. 检查黑名单过滤条件是否过于严格。\n")
        return "".join(lines)

    # 按类别分组
    categories = {}
    for paper in papers:
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


def write_report(
    papers: List[Dict[str, Any]],
    report_path: str,
    config_dict: Optional[Dict[str, Any]] = None
) -> str:
    """
    将报告内容写入指定文件（覆盖）。

    Args:
        papers: 论文字典列表。
        report_path: 输出文件路径。
        config_dict: 可选的配置字典。

    Returns:
        写入的报告文件路径（与 report_path 相同）。
    """
    content = generate_report_content(papers, config_dict)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)
    return report_path


if __name__ == "__main__":
    # 简单测试
    test_papers = [
        {
            "title": "Test Paper",
            "link": "https://arxiv.org/abs/1234.5678",
            "authors": ["Author A", "Author B"],
            "date": "2025-12-13",
            "abstract": "This is a test abstract.",
            "category": "cs.CV",
            "summary": "这是一个测试总结。"
        }
    ]
    print(generate_report_content(test_papers))