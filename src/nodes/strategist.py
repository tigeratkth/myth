"""M3 · 推广策略规划师节点。"""
from __future__ import annotations

from ..state import WorkflowState
from ._helpers import run_module


def strategist_node(state: WorkflowState) -> dict:
    """围绕技术IP 制定推广策略骨架。"""
    def build_vars(s: WorkflowState) -> dict:
        return {
            "m2_output_json": s.get("m2_output", {}),
            "m1_output_json": s.get("m1_output", {}),
        }

    return run_module(
        module_key="m3",
        next_module="m4",
        prompt_name="strategist",
        build_variables=build_vars,
        output_field="m3_output",
        state=state,
    )
