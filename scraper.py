import arxiv
import datetime
from typing import List, Dict, Any, Optional, Union
import config


def _get_prefixed_config(prefix: str = "") -> Dict[str, Any]:
    """
    返回一个配置字典，其中键根据前缀进行映射。
    如果 prefix 为空，则使用原始键（例如 KEYWORDS）。
    否则使用 prefix + KEY（例如 DAILY_PUSH_KEYWORDS）。
    """
    cfg = config.load_config()
    if not prefix:
        return cfg
    # 映射原始键到带前缀的键
    key_map = {
        "KEYWORDS": prefix + "KEYWORDS",
        "FILTER_DAYS": prefix + "FILTER_DAYS",
        "ADDITIONAL_KEYWORDS": prefix + "ADDITIONAL_KEYWORDS",
        "BLACKLIST_KEYWORDS": prefix + "BLACKLIST_KEYWORDS",
        "START_DATE": prefix + "START_DATE",
        "END_DATE": prefix + "END_DATE",
    }
    result = {}
    for orig, prefixed in key_map.items():
        if orig in ("START_DATE", "END_DATE"):
            # 日期字段默认空字符串
            default = ""
        elif "KEYWORDS" in orig:
            default = []
        else:
            default = 1
        result[orig] = cfg.get(prefixed, cfg.get(orig, default))
    # 同时包含其他配置（如 BASE_URL 等）
    for key, value in cfg.items():
        if key not in result:
            result[key] = value
    return result


def fetch_papers(keyword: str, days: int = None, cfg: Dict[str, Any] = None,
                 start_date: Optional[Union[str, datetime.date]] = None,
                 end_date: Optional[Union[str, datetime.date]] = None) -> List[Dict[str, Any]]:
    """
    使用 arxiv API 搜索指定关键词，返回指定日期范围内或最近 days 天内的论文。
    如果提供了 start_date 和 end_date，则使用日期范围过滤（忽略 days）。
    否则使用 days 参数（或配置中的 FILTER_DAYS）进行天数过滤。
    """
    if cfg is None:
        cfg = config.load_config()
    if days is None:
        days = cfg.get("FILTER_DAYS", 1)

    client = arxiv.Client()
    search = arxiv.Search(
        query=keyword,
        max_results=100,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    papers = []

    # 日期范围过滤
    use_date_range = start_date is not None and end_date is not None
    if use_date_range:
        # 转换为 datetime.date 对象
        if isinstance(start_date, str):
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        # 将日期转换为带时区的 datetime（假设为 UTC 时间 00:00）
        start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=datetime.timezone.utc)
        end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=datetime.timezone.utc)
    else:
        # 使用天数过滤
        cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

    for result in client.results(search):
        if use_date_range:
            # 检查是否在日期范围内（包含边界）
            if not (start_dt <= result.published <= end_dt):
                continue
        else:
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


def filter_remote_sensing(papers: List[Dict[str, Any]], cfg: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    过滤 Remote Sensing 类论文，只保留标题或摘要中包含附加关键词的论文。
    """
    if cfg is None:
        cfg = config.load_config()
    additional_keywords = cfg.get("ADDITIONAL_KEYWORDS", [])

    filtered = []
    for paper in papers:
        if paper["category"] != "Remote Sensing":
            filtered.append(paper)
            continue

        text = (paper["title"] + " " + paper["abstract"]).lower()
        # 检查是否包含任意一个关键词
        if any(keyword.lower() in text for keyword in additional_keywords):
            filtered.append(paper)
        # 否则丢弃
    return filtered


def filter_blacklist(papers: List[Dict[str, Any]], cfg: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    应用全局黑名单过滤（白名单已移除）。
    """
    if cfg is None:
        cfg = config.load_config()
    blacklist = cfg.get("BLACKLIST_KEYWORDS", [])

    if not blacklist:
        return papers

    filtered = []
    for paper in papers:
        text = (paper["title"] + " " + paper["abstract"]).lower()
        # 黑名单检查：如果包含任意黑名单关键词，则排除
        if any(keyword.lower() in text for keyword in blacklist):
            continue
        filtered.append(paper)
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


def scrape_all(prefix: str = "") -> List[Dict[str, Any]]:
    """
    爬取所有关键词的论文，合并、过滤、去重。
    如果提供了前缀（例如 "DAILY_PUSH_"），则使用带前缀的配置键。
    """
    cfg = _get_prefixed_config(prefix)
    keywords = cfg.get("KEYWORDS", [])
    filter_days = cfg.get("FILTER_DAYS", 1)
    start_date = cfg.get("START_DATE")
    end_date = cfg.get("END_DATE")

    all_papers = []
    for keyword in keywords:
        print(f"正在爬取关键词: {keyword}")
        # 如果提供了起止日期，则使用日期范围过滤
        if start_date and end_date:
            papers = fetch_papers(keyword, filter_days, cfg,
                                  start_date=start_date,
                                  end_date=end_date)
        else:
            papers = fetch_papers(keyword, filter_days, cfg)
        all_papers.extend(papers)
        print(f"  找到 {len(papers)} 篇论文")

    # 过滤 Remote Sensing
    all_papers = filter_remote_sensing(all_papers, cfg)

    # 全局黑名单过滤（白名单已移除）
    all_papers = filter_blacklist(all_papers, cfg)

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