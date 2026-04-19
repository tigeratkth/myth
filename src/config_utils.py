"""
配置与环境辅助工具

专注于 .env、config.yaml 的读写，以及给首页提供"环境状态"摘要。
与 llm.py 的 load_config() / list_models() 互补，不做 LLM 调用。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values, set_key

from .llm import _PROVIDER_ENV_KEY, load_config


_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"
_ENV_PATH = _ROOT / ".env"


# ============================================================
# .env
# ============================================================
def read_env() -> dict[str, str]:
    """读取 .env 到 dict。文件不存在时返回空 dict。"""
    if not _ENV_PATH.exists():
        return {}
    return {k: v or "" for k, v in dotenv_values(_ENV_PATH).items() if k}


def save_env(updates: dict[str, str]) -> None:
    """把 updates 合并写入 .env（更新已有键或追加新键），保留文件头部注释。"""
    if not _ENV_PATH.exists():
        _ENV_PATH.write_text("# 由 UI 自动生成\n", encoding="utf-8")
    for k, v in updates.items():
        # 允许清空：传入空串会写成 KEY=
        set_key(str(_ENV_PATH), k, v or "", quote_mode="never")


# ============================================================
# config.yaml
# ============================================================
def save_yaml_config(data: dict) -> None:
    """把配置写回 config.yaml（UTF-8, 保留中文可读）。"""
    with _CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def update_defaults(
    *,
    mode: str | None = None,
    temperature: float | None = None,
    module_models: dict[str, str] | None = None,
) -> dict:
    """更新 config.yaml 的 defaults 节，返回最新配置。"""
    cfg = load_config()
    defaults = cfg.setdefault("defaults", {})
    if mode is not None:
        defaults["mode"] = mode
    if temperature is not None:
        defaults["temperature"] = float(temperature)
    if module_models is not None:
        defaults.setdefault("module_models", {}).update(module_models)
    save_yaml_config(cfg)
    return cfg


def update_models(models: list[dict]) -> dict:
    """覆盖 config.yaml 的 models 列表。调用方负责构造完整列表。"""
    cfg = load_config()
    cfg["models"] = models
    save_yaml_config(cfg)
    return cfg


# ============================================================
# 首页环境状态摘要
# ============================================================
_PROVIDER_DISPLAY = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "deepseek": "DeepSeek",
    "dashscope": "通义千问",
}


def env_status() -> dict:
    """返回首页 3 卡片所需的数据结构，字段与 mocks.sample_env_status() 对齐。"""
    cfg = load_config()
    env = read_env()

    provider_status: list[tuple[str, bool]] = []
    for provider, env_key in _PROVIDER_ENV_KEY.items():
        display = _PROVIDER_DISPLAY.get(provider, provider)
        configured = bool(env.get(env_key, "").strip())
        provider_status.append((display, configured))

    configured_providers = [d for d, ok in provider_status if ok]
    defaults = cfg.get("defaults", {}) or {}
    module_models = defaults.get("module_models", {}) or {}
    distinct_models = {v for v in module_models.values() if v}
    all_same = len(distinct_models) <= 1

    if all_same and distinct_models:
        summary = f"全模块统一 · {next(iter(distinct_models))}"
    elif module_models:
        summary = f"分模块配置 · {len(distinct_models)} 个模型"
    else:
        summary = "未设置默认模型"

    return {
        "api_keys": {
            "configured_count": len(configured_providers),
            "total_providers": len(provider_status),
            "providers": configured_providers,
            "all_status": provider_status,
        },
        "default_model": {
            "all_module_same": all_same,
            "summary": summary,
            "module_models": module_models,
        },
        "default_mode": defaults.get("mode", "human_review"),
        "temperature": defaults.get("temperature", 0.7),
    }


__all__ = [
    "read_env",
    "save_env",
    "save_yaml_config",
    "update_defaults",
    "update_models",
    "env_status",
]
