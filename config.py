"""
GUI 配置文件管理模块。
管理用户通过 GUI 修改的配置（API Key、BaseURL、模型ID、自定义提示词等），
并持久化到 config.json 文件中。
"""
import json
import os
import sys
from typing import Any, Dict, Optional

CONFIG_PATH = "config.json"

# 默认配置字典（与原始 config.py 保持一致）
DEFAULT_CONFIG = {
    "BASE_URL": "https://api.siliconflow.cn/v1",
    "MODEL_ID": "deepseek-ai/DeepSeek-V3.2",
    "API_KEY": "",
    "SYSTEM_PROMPT": """你是一个科研助手。请阅读摘要，用中文总结。输出格式：
**创新点**：...
**方法**：...
**结论**：...
请确保输出清晰、简洁，每部分用换行分隔。""",
    "KEYWORDS": ["Gaussian Splatting", "Remote Sensing"],
    "FILTER_DAYS": 7,
    "ADDITIONAL_KEYWORDS": ["Deep Learning", "Neural", "AI", "Machine Learning", "Artificial Intelligence"],
    "BLACKLIST_KEYWORDS": [],
    "OUTPUT_FILE": "Daily_Report.md",
    "MAX_RETRIES": 3,
    "RETRY_DELAY": 2,
    "DAILY_PUSH_FILTER_DAYS": 1,
    "DAILY_PUSH_KEYWORDS": ["Gaussian Splatting", "Remote Sensing"],
    "DAILY_PUSH_ADDITIONAL_KEYWORDS": ["Deep Learning", "Neural", "AI", "Machine Learning", "Artificial Intelligence"],
    "DAILY_PUSH_BLACKLIST_KEYWORDS": [],
    "DAILY_PUSH_TIMEZONE": "Asia/Shanghai",
    "DAILY_PUSH_TIME": "09:00",
    "USER_SEARCH_FILTER_DAYS": 7,
    "USER_SEARCH_KEYWORDS": [],
    "USER_SEARCH_ADDITIONAL_KEYWORDS": [],
    "USER_SEARCH_BLACKLIST_KEYWORDS": [],
    "USER_SEARCH_START_DATE": "",
    "USER_SEARCH_END_DATE": "",
}

def load_config() -> Dict[str, Any]:
    """
    从 config.json 加载配置，如果文件不存在则创建并返回默认配置。
    如果文件存在但缺少某些键，则用默认值补充（不写回文件）。
    """
    if not os.path.exists(CONFIG_PATH):
        # 创建默认配置文件
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"创建配置文件失败: {e}", file=sys.stderr)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
        # 确保所有默认键都存在，缺失的用默认值补充
        merged = DEFAULT_CONFIG.copy()
        merged.update(user_config)  # 用户配置覆盖默认值
        # 向后兼容：如果存在 REMOTE_SENSING_KEYWORDS 但 ADDITIONAL_KEYWORDS 不存在，则复制
        if "REMOTE_SENSING_KEYWORDS" in user_config and "ADDITIONAL_KEYWORDS" not in user_config:
            merged["ADDITIONAL_KEYWORDS"] = user_config["REMOTE_SENSING_KEYWORDS"]
        return merged
    except (json.JSONDecodeError, IOError) as e:
        print(f"加载配置文件失败: {e}", file=sys.stderr)
        return DEFAULT_CONFIG.copy()

def save_config(updates: Dict[str, Any]) -> None:
    """
    将更新的配置保存到 config.json。
    注意：只保存提供的键值对，其他键保持不变。
    """
    # 先加载当前配置
    current = load_config()
    current.update(updates)
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"保存配置文件失败: {e}", file=sys.stderr)

def apply_to_module(module=None) -> None:
    """
    将当前配置应用到指定的模块（默认为 config 模块）。
    此函数已弃用，因为 config.py 已被移除。保留仅为兼容性。
    """
    if module is not None:
        config_dict = load_config()
        for key, value in config_dict.items():
            if hasattr(module, key):
                setattr(module, key, value)
            else:
                setattr(module, key, value)
    else:
        # 如果没有提供模块，则忽略
        pass

def get_config_value(key: str, default: Any = None) -> Any:
    """获取单个配置项的值。"""
    config = load_config()
    return config.get(key, default)

if __name__ == "__main__":
    # 测试代码
    print("当前配置:", load_config())
    # 保存一个测试更新
    save_config({"API_KEY": "test_key"})
    print("更新后配置:", load_config())
