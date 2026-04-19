"""LLM 统一调用层

基于 LiteLLM 封装多 Provider 的统一入口。上层节点只通过本模块调用大模型，
不直接依赖 litellm，方便以后替换实现或做离线 Mock（参见 scripts/smoke_backend.py）。

核心职责：
  - 从 config.yaml 读取模型注册表、默认配置
  - 从 .env / 进程环境变量读取 API Key，并在调用前校验
  - 封装 JSON 输出模式（system prompt 强制 + 结果解析 + 失败重试）
  - 提供连通性测试接口
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


# ============================================================
# 配置读取
# ============================================================
_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config.yaml"
_ENV_PATH = _ROOT / ".env"

# 在模块加载时读取一次 .env；若用户后续修改，可再调 load_dotenv(override=True)
load_dotenv(_ENV_PATH, override=False)


# Provider → 需要的环境变量名。缺失时给出清晰的错误提示
_PROVIDER_ENV_KEY: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    # 火山方舟 / 字节豆包：API Key 来自 https://console.volcengine.com/ark
    # 可选环境变量 VOLCENGINE_API_BASE，默认 https://ark.cn-beijing.volces.com/api/v3
    "volcengine": "VOLCENGINE_API_KEY",
}


def load_config(path: str | Path | None = None) -> dict:
    """读取 config.yaml，返回结构化配置 dict。文件不存在时返回空配置。"""
    cfg_path = Path(path) if path else _CONFIG_PATH
    if not cfg_path.exists():
        return {"models": [], "defaults": {}, "runtime": {}}
    with cfg_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("models", [])
    data.setdefault("defaults", {})
    data.setdefault("runtime", {})
    return data


def list_models(only_enabled: bool = True) -> list[dict]:
    """返回模型清单，供 UI 下拉展示。

    返回项字段：id/display_name/provider/max_tokens/enabled/env_key/env_configured
    """
    cfg = load_config()
    models: list[dict] = []
    for m in cfg.get("models", []):
        if only_enabled and not m.get("enabled", True):
            continue
        provider = m.get("provider", "")
        env_key = _PROVIDER_ENV_KEY.get(provider, "")
        models.append(
            {
                "id": m["id"],
                "display_name": m.get("display_name", m["id"]),
                "provider": provider,
                "max_tokens": m.get("max_tokens", 4096),
                "enabled": m.get("enabled", True),
                "env_key": env_key,
                "env_configured": bool(env_key and os.getenv(env_key)),
            }
        )
    return models


def _provider_of(model_id: str) -> str:
    """从 LiteLLM 风格的 model id 中取 provider 前缀。"""
    return model_id.split("/", 1)[0] if "/" in model_id else ""


def _ensure_api_key(model_id: str) -> None:
    """若对应 Provider 的 API Key 未配置，抛出清晰错误。"""
    provider = _provider_of(model_id)
    env_key = _PROVIDER_ENV_KEY.get(provider)
    if not env_key:
        # 未知 provider 就交给 LiteLLM 自行处理（可能是自定义接入）
        return
    if not os.getenv(env_key):
        raise RuntimeError(
            f"未检测到环境变量 {env_key}，无法调用模型 {model_id}。"
            f"请在项目根目录的 .env 中填入对应的 API Key。"
        )


# ============================================================
# JSON 输出解析
# ============================================================
_JSON_ENFORCE_SUFFIX = (
    "\n\n请务必只输出一个合法的 JSON 对象，不要输出任何解释文字、Markdown 代码块标记或注释。"
    "若无法确定字段值请留空字符串或空数组，但结构必须完整。"
)


def _extract_json(text: str) -> dict:
    """从模型原始输出中抽取 JSON。

    优先直接 json.loads；失败则尝试截取首个 {...} 片段；再失败则抛 ValueError。
    """
    text = text.strip()
    # 去掉常见的 Markdown 围栏
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|JSON)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 回退：找第一个 '{' 到最后一个 '}' 之间的内容
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            raise ValueError(f"模型返回的内容无法解析为 JSON：{e}") from e
    raise ValueError("模型返回的内容不是合法 JSON，且未找到可提取的 JSON 片段")


# ============================================================
# 核心调用
# ============================================================
def invoke_llm(
    model: str,
    prompt: str,
    *,
    system: str = "",
    temperature: float = 0.7,
    response_format: str = "json",
    max_retries: int = 2,
    max_tokens: int | None = None,
) -> dict:
    """调用 LLM，返回结构化结果。

    返回字段：
      - content: 解析后的 dict（response_format="json"）或 {"text": ...}（文本模式）
      - raw: 原始字符串
      - tokens_in / tokens_out: 用量（若 provider 未返回则为 0）
      - model: 实际调用的 model id

    JSON 模式下会强制在 system 中追加约束，并在解析失败时重试 max_retries 次。
    """
    _ensure_api_key(model)

    # 延迟导入，方便测试时 monkeypatch 掉整个 invoke_llm 函数而不引入依赖
    from litellm import completion  # type: ignore

    sys_prompt = system or ""
    if response_format == "json":
        sys_prompt = (sys_prompt + _JSON_ENFORCE_SUFFIX).strip()

    messages = []
    if sys_prompt:
        messages.append({"role": "system", "content": sys_prompt})
    messages.append({"role": "user", "content": prompt})

    last_error: Exception | None = None
    raw_text = ""
    tokens_in = 0
    tokens_out = 0

    for attempt in range(max_retries + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            # 部分 provider 支持原生 JSON 模式，能更稳；不支持也不会报错
            if response_format == "json":
                kwargs["response_format"] = {"type": "json_object"}

            resp = completion(**kwargs)
            raw_text = _extract_response_text(resp)
            usage = _extract_usage(resp)
            tokens_in = usage.get("prompt_tokens", 0) or 0
            tokens_out = usage.get("completion_tokens", 0) or 0

            if response_format == "json":
                content: Any = _extract_json(raw_text)
            else:
                content = {"text": raw_text}

            return {
                "content": content,
                "raw": raw_text,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "model": model,
            }
        except ValueError as e:
            # JSON 解析失败 → 重试时在用户消息后追加"请严格输出 JSON"
            last_error = e
            if attempt < max_retries:
                messages.append(
                    {
                        "role": "user",
                        "content": "上一次回复无法解析为 JSON，请严格按要求只输出一个合法 JSON 对象。",
                    }
                )
                continue
            break
        except Exception as e:  # noqa: BLE001 — 网络/鉴权等异常统一抛给上层
            last_error = e
            # 非 JSON 解析错误：不重试，直接抛
            raise

    raise RuntimeError(
        f"调用模型 {model} 多次尝试后仍未返回合法 JSON：{last_error}\n原始输出：{raw_text[:500]}"
    )


def _extract_response_text(resp: Any) -> str:
    """兼容 LiteLLM 返回对象（ModelResponse / dict）。"""
    try:
        return resp.choices[0].message.content or ""
    except AttributeError:
        try:
            return resp["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return ""


def _extract_usage(resp: Any) -> dict[str, int]:
    try:
        u = resp.usage
        return {
            "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
            "total_tokens": getattr(u, "total_tokens", 0) or 0,
        }
    except AttributeError:
        try:
            u = resp.get("usage") or {}
            return {
                "prompt_tokens": u.get("prompt_tokens", 0) or 0,
                "completion_tokens": u.get("completion_tokens", 0) or 0,
                "total_tokens": u.get("total_tokens", 0) or 0,
            }
        except AttributeError:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


# ============================================================
# 连通性测试
# ============================================================
def test_connection(model: str) -> tuple[bool, str]:
    """测试某个模型是否可正常调用。

    使用一个极短的 ping 请求，成功返回 (True, "ok ... 用时xxms")，
    失败返回 (False, error_message)。
    """
    import time

    try:
        _ensure_api_key(model)
    except RuntimeError as e:
        return False, str(e)

    t0 = time.time()
    try:
        from litellm import completion  # type: ignore

        resp = completion(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.0,
            max_tokens=8,
        )
        text = _extract_response_text(resp)
        dt = int((time.time() - t0) * 1000)
        preview = (text or "").strip().replace("\n", " ")[:40]
        return True, f"连通成功，用时 {dt}ms；响应：{preview}"
    except Exception as e:  # noqa: BLE001
        return False, f"调用失败：{e}"


# ============================================================
# Prompt 模板工具（供节点共用）
# ============================================================
_PROMPT_DIR = _ROOT / "prompts"


def load_prompt(name: str) -> str:
    """读取 prompts/{name}.md 模板原文。"""
    p = _PROMPT_DIR / f"{name}.md"
    if not p.exists():
        raise FileNotFoundError(f"Prompt 模板不存在：{p}")
    return p.read_text(encoding="utf-8")


def render_prompt(template: str, variables: dict[str, Any]) -> str:
    """简易 {{var}} 变量替换。

    值若为 dict / list 会被 json.dumps 成可读 JSON 串，方便嵌入。
    """
    rendered = template
    for key, val in variables.items():
        if isinstance(val, (dict, list)):
            val_str = json.dumps(val, ensure_ascii=False, indent=2)
        else:
            val_str = "" if val is None else str(val)
        rendered = rendered.replace(f"{{{{{key}}}}}", val_str)
    return rendered


__all__ = [
    "load_config",
    "list_models",
    "invoke_llm",
    "test_connection",
    "load_prompt",
    "render_prompt",
]
