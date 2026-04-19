"""LangGraph 构图 · 双模式编译产物

- build_auto_graph()       — 全自动模式，编译后一口气跑完四个节点
- build_review_graph()     — 人工审核模式，每个节点后中断 + MemorySaver checkpointer
- build_graph(mode)        — 根据 mode 字符串返回上述两者之一
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from .nodes import (
    ip_builder_node,
    marketer_node,
    strategist_node,
    translator_node,
)
from .state import WorkflowState


def _base_builder() -> StateGraph:
    g = StateGraph(WorkflowState)
    g.add_node("m1", translator_node)
    g.add_node("m2", ip_builder_node)
    g.add_node("m3", strategist_node)
    g.add_node("m4", marketer_node)

    g.add_edge(START, "m1")
    g.add_edge("m1", "m2")
    g.add_edge("m2", "m3")
    g.add_edge("m3", "m4")
    g.add_edge("m4", END)
    return g


def build_auto_graph():
    """全自动模式 — 无中断，无 checkpointer。"""
    return _base_builder().compile()


def build_review_graph():
    """人工审核模式 — 每个节点后中断，配 MemorySaver。

    前端通过 `graph.invoke(None, config)` 或 `graph.update_state(...)` 驱动。
    """
    return _base_builder().compile(
        checkpointer=MemorySaver(),
        interrupt_after=["m1", "m2", "m3", "m4"],
    )


def build_graph(mode: Literal["auto", "human_review"] = "auto"):
    """统一入口。"""
    if mode == "human_review":
        return build_review_graph()
    return build_auto_graph()


__all__ = ["build_graph", "build_auto_graph", "build_review_graph"]
