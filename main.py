import os
import datetime
from typing import List, Dict, Any
from scraper import scrape_all
from summarizer import batch_summarize

def generate_report_content(papers: List[Dict[str, Any]]) -> str:
    """根据论文列表生成 Markdown 报告内容"""
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
            authors = ", ".join(paper["authors"][:5])  # 最多显示5位作者
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

def write_report(papers: List[Dict[str, Any]], report_path: str):
    """将报告内容写入指定文件（覆盖）"""
    content = generate_report_content(papers)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)

def main():
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
    write_report(papers, report_path)

    print(f"完成！报告已保存至 {report_path}")


if __name__ == "__main__":
    main()