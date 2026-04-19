"""M1 · 技术翻译官节点。"""
from __future__ import annotations

from ..state import WorkflowState
from ._helpers import run_module


def translator_node(state: WorkflowState) -> dict:
    """抽取原始技术要点并翻译成用户语言。

    读：state['raw_material']、state['module_models']['m1']
    写：m1_output / m1_meta / logs / current_module
    """
    def build_vars(s: WorkflowState) -> dict:
        return {"raw_material": s.get("raw_material", "")}

    return run_module(
        module_key="m1",
        next_module="m2",
        prompt_name="translator",
        build_variables=build_vars,
        output_field="m1_output",
        state=state,
    )
