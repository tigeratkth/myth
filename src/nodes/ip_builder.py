"""M2 · 技术卖点包装师节点（产出技术IP）。"""
from __future__ import annotations

from ..state import WorkflowState
from ._helpers import run_module


def ip_builder_node(state: WorkflowState) -> dict:
    """基于 M1 的翻译结果，产出用户可理解 + 用户需要的技术卖点集合。"""
    def build_vars(s: WorkflowState) -> dict:
        return {
            "m1_output_json": s.get("m1_output", {}),
            "raw_material": s.get("raw_material", ""),
        }

    return run_module(
        module_key="m2",
        next_module="m3",
        prompt_name="ip_builder",
        build_variables=build_vars,
        output_field="m2_output",
        state=state,
    )
