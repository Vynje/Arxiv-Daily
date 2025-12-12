import openai
import time
import logging
from typing import Optional
import gui_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def summarize_abstract(abstract: str) -> Optional[str]:
    """
    使用硅基流动 API 生成中文摘要。
    返回格式化后的摘要字符串，如果失败则返回 None。
    """
    cfg = gui_config.load_config()
    base_url = cfg.get("BASE_URL", "https://api.siliconflow.cn/v1")
    model_id = cfg.get("MODEL_ID", "deepseek-ai/DeepSeek-V3.2")
    api_key = cfg.get("API_KEY", "")
    system_prompt = cfg.get("SYSTEM_PROMPT", "")
    max_retries = cfg.get("MAX_RETRIES", 3)
    retry_delay = cfg.get("RETRY_DELAY", 2)

    if not api_key:
        logger.error("API_KEY 未设置，无法生成摘要")
        return None

    client = openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"请总结以下论文摘要：\n\n{abstract}"}
    ]

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            )
            summary = response.choices[0].message.content.strip()
            return summary
        except Exception as e:
            logger.error(f"第 {attempt + 1} 次尝试失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logger.error("达到最大重试次数，跳过该论文")
                return None


def batch_summarize(papers: list) -> list:
    """
    为每篇论文生成摘要，并添加到 paper 字典中。
    返回更新后的论文列表。
    """
    summarized = []
    for i, paper in enumerate(papers):
        logger.info(f"正在处理第 {i+1}/{len(papers)} 篇: {paper['title'][:50]}...")
        summary = summarize_abstract(paper["abstract"])
        paper["summary"] = summary
        summarized.append(paper)
        # 避免速率限制
        time.sleep(0.5)
    return summarized


if __name__ == "__main__":
    # 测试代码
    test_abstract = """
    Gaussian splatting is a novel approach for 3D reconstruction and rendering.
    It uses anisotropic 3D Gaussians to represent scenes, enabling real-time
    rendering with high visual quality. This paper introduces a differentiable
    splatting pipeline that optimizes Gaussian parameters via gradient descent.
    """
    result = summarize_abstract(test_abstract)
    print("测试摘要结果:")
    print(result)