import arxiv
import datetime
from typing import List, Dict, Any
import gui_config

def fetch_papers(keyword: str, days: int = None) -> List[Dict[str, Any]]:
    """
    使用 arxiv API 搜索指定关键词，返回最近 days 天内的论文。
    如果 days 为 None，则使用配置中的 FILTER_DAYS。
    """
    if days is None:
        cfg = gui_config.load_config()
        days = cfg.get("FILTER_DAYS", 1)

    client = arxiv.Client()
    search = arxiv.Search(
        query=keyword,
        max_results=100,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    papers = []
    cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

    for result in client.results(search):
        # 检查是否在时间范围内
        if result.published < cutoff_date:
            continue

        paper = {
            "title": result.title,
            "authors": [author.name for author in result.authors],
            "abstract": result.summary,
            "link": result.entry_id,
            "date": result.published.date(),
            "category": keyword,
        }
        papers.append(paper)

    return papers


def filter_remote_sensing(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    过滤 Remote Sensing 类论文，只保留标题或摘要中包含特定关键词的论文。
    """
    cfg = gui_config.load_config()
    remote_sensing_keywords = cfg.get("REMOTE_SENSING_KEYWORDS", [])

    filtered = []
    for paper in papers:
        if paper["category"] != "Remote Sensing":
            filtered.append(paper)
            continue

        text = (paper["title"] + " " + paper["abstract"]).lower()
        # 检查是否包含任意一个关键词
        if any(keyword.lower() in text for keyword in remote_sensing_keywords):
            filtered.append(paper)
        # 否则丢弃
    return filtered


def deduplicate_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据标题去重（简单去重）。
    """
    seen = set()
    unique = []
    for paper in papers:
        title = paper["title"]
        if title not in seen:
            seen.add(title)
            unique.append(paper)
    return unique


def scrape_all() -> List[Dict[str, Any]]:
    """
    爬取所有关键词的论文，合并、过滤、去重。
    """
    cfg = gui_config.load_config()
    keywords = cfg.get("KEYWORDS", [])
    filter_days = cfg.get("FILTER_DAYS", 1)

    all_papers = []
    for keyword in keywords:
        print(f"正在爬取关键词: {keyword}")
        papers = fetch_papers(keyword, filter_days)
        all_papers.extend(papers)
        print(f"  找到 {len(papers)} 篇论文")

    # 过滤 Remote Sensing
    all_papers = filter_remote_sensing(all_papers)

    # 去重
    all_papers = deduplicate_papers(all_papers)

    print(f"总计保留 {len(all_papers)} 篇论文")
    return all_papers


if __name__ == "__main__":
    # 测试代码
    papers = scrape_all()
    for i, p in enumerate(papers[:3]):
        print(f"{i+1}. {p['title']}")
        print(f"   作者: {', '.join(p['authors'][:3])}")
        print(f"   链接: {p['link']}")
        print()