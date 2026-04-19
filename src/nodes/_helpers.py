"""节点共用工具：运行封装 / 元信息填充 / 默认模型回退。

节点实现应尽量薄——把"读模板 → 渲染 → 调 LLM → 写回 state"的骨架集中在这里，
各节点只需提供模块 key、prompt 名、变量构造逻辑和输出字段名。
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable

from ..llm import invoke_llm, load_config, load_prompt, render_prompt
from ..state import ModuleKey, WorkflowState


def _default_model_for(module_key: ModuleKey) -> str:
    """从 config.yaml 的 defaults.module_models 取该模块默认模型。"""
    cfg = load_config()
    mapping = (cfg.get("defaults") or {}).get("module_models") or {}
    # config.yaml 中 key 形如 m1_translator，这里兼容 m1 / m1_translator 两种
    for k, v in mapping.items():
        if k == module_key or k.startswith(f"{module_key}_"):
            return v
    # 回退：用第一个启用的模型
    for m in cfg.get("models") or []:
        if m.get("enabled", True):
            return m["id"]
    raise RuntimeError("config.yaml 中未找到可用模型")


def _pick_model(state: WorkflowState, module_key: ModuleKey) -> str:
    models = state.get("module_models") or {}
    model = models.get(module_key)
    if not model:
        model = _default_model_for(module_key)
    return model


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log(module_key: ModuleKey, msg: str) -> str:
    return f"[{datetime.now().strftime('%H:%M:%S')}] [{module_key}] {msg}"


def run_module(
    *,
    module_key: ModuleKey,
    next_module: ModuleKey | None,
    prompt_name: str,
    build_variables: Callable[[WorkflowState], dict[str, Any]],
    output_field: str,
    state: WorkflowState,
) -> dict:
    """通用节点执行器。

    返回要合并回 state 的 dict（LangGraph 节点契约）。
    """
    model = _pick_model(state, module_key)
    temperature = float(state.get("temperature", 0.7))

    started_at = _now_iso()
    t0 = time.time()
    meta: dict[str, Any] = {
        "status": "running",
        "model": model,
        "started_at": started_at,
    }
    logs: list[str] = [_log(module_key, f"开始执行，使用模型 {model}")]

    try:
        template = load_prompt(prompt_name)
        variables = build_variables(state)
        prompt = render_prompt(template, variables)
        result = invoke_llm(
            model,
            prompt,
            temperature=temperature,
            response_format="json",
        )
        content = result["content"]
        duration_ms = int((time.time() - t0) * 1000)
        meta.update(
            {
                "status": "completed",
                "finished_at": _now_iso(),
                "duration_ms": duration_ms,
                "tokens_in": int(result.get("tokens_in") or 0),
                "tokens_out": int(result.get("tokens_out") or 0),
            }
        )
        logs.append(_log(module_key, f"完成，用时 {duration_ms}ms"))

        update: dict[str, Any] = {
            output_field: content,
            f"{module_key}_meta": meta,
            "logs": logs,
        }
        if next_module is not None:
            update["current_module"] = next_module
            update["overall_status"] = "running"
        else:
            update["current_module"] = module_key
            update["overall_status"] = "completed"
        return update
    except Exception as e:  # noqa: BLE001 — 任何异常都写入 meta.error
        duration_ms = int((time.time() - t0) * 1000)
        meta.update(
            {
                "status": "failed",
                "finished_at": _now_iso(),
                "duration_ms": duration_ms,
                "error": str(e),
            }
        )
        logs.append(_log(module_key, f"失败：{e}"))
        return {
            f"{module_key}_meta": meta,
            "logs": logs,
            "current_module": module_key,
            "overall_status": "failed",
        }
