"""M4 · 营销内容策划师节点。"""
from __future__ import annotations

from ..state import WorkflowState
from ._helpers import run_module


def marketer_node(state: WorkflowState) -> dict:
    """基于技术IP + 推广策略，产出可落地文案与活动方案。"""
    def build_vars(s: WorkflowState) -> dict:
        return {
            "m2_output_json": s.get("m2_output", {}),
            "m3_output_json": s.get("m3_output", {}),
        }

    return run_module(
        module_key="m4",
        next_module=None,
        prompt_name="marketer",
        build_variables=build_vars,
        output_field="m4_output",
        state=state,
    )
