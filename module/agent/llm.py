# DeepSeek 模型工厂：统一负责 API Key 解析与 ChatDeepSeek 构建。
# langchain 延迟到 build_chat_model() 内导入，GUI 启动或未配置 Key 时不加载重依赖。

import os

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_TEMPERATURE = 0.7
ENV_API_KEY = "DEEPSEEK_API_KEY"  # 官方推荐的环境变量名


def get_api_key() -> str:
    """读取 API Key：优先本地环境变量 DEEPSEEK_API_KEY，其次 config.yaml 的 agent_api_key"""
    api_key = os.environ.get(ENV_API_KEY, "").strip()
    if api_key:
        return api_key
    try:
        from module.config import cfg
        api_key = str(cfg.get_value("agent_api_key", "") or "").strip()
    except Exception:
        pass  # 配置未就绪时安静回退，交由下方统一报错提示
    return api_key


def _cfg_value(key, default):
    """读取配置项；配置文件中尚未添加该键时静默回退默认值，避免启动报错"""
    try:
        from module.config import cfg
        value = cfg.get_value(key, default)
        return default if value in (None, "") else value
    except Exception:
        return default


def build_chat_model():
    """构建 DeepSeek 聊天模型；API Key 缺失时抛出 RuntimeError，交由上层渲染错误提示"""
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            f"未检测到 DeepSeek API Key：请设置环境变量 {ENV_API_KEY}，"
            "或在配置文件中填写 agent_api_key"
        )
    # 延迟导入：只有真正发起对话时才加载 langchain 依赖
    from langchain_deepseek import ChatDeepSeek

    params = {
        "model": _cfg_value("agent_model", DEFAULT_MODEL),
        "temperature": float(_cfg_value("agent_temperature", DEFAULT_TEMPERATURE)),
        "timeout": 60,
        "max_retries": 2,
    }
    # base_url 仅在配置里显式给出时才传，缺省时使用包内置的官方地址 https://api.deepseek.com
    base_url = str(_cfg_value("agent_base_url", "")).strip()
    if base_url:
        params["base_url"] = base_url
    return ChatDeepSeek(api_key=api_key, **params)
