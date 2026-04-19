"""
Streamlit ↔ LangGraph 运行时胶水层

封装两种模式的执行细节，让页面只需：
  - `start_task(material, task_name, mode, module_models, ...)` 启动任务
  - `continue_task(action, edited_output=None)` 处理审核反馈
  - `get_running_state()` 读取当前活跃任务的 WorkflowState

内部职责：
  - 保存 compiled graph 与 thread_id 到 st.session_state（每个会话一份）
  - 将每次 LangGraph 事件流映射为 UI 可读的 WorkflowState 快照
  - 自动在阶段性节点落盘到 outputs/{task_id}/
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Iterable, Literal, Optional

import streamlit as st

from .graph import build_graph
from .io_utils import save_task
from .state import MODULE_KEYS, RunMode, WorkflowState, make_initial_state


# ============================================================
# Session 键名（统一管理，避免拼写错误）
# ============================================================
_SK_GRAPH = "_runtime_graph"
_SK_THREAD = "_runtime_thread_id"
_SK_STATE = "current_state"
_SK_MODE = "_runtime_mode"


# ============================================================
# 启动任务
# ============================================================
def start_task(
    *,
    raw_material: str,
    task_name: str,
    mode: RunMode,
    module_models: dict[str, str],
    source_type: Literal["upload", "paste"] = "paste",
    source_filename: str = "",
    temperature: float = 0.7,
) -> WorkflowState:
    """启动一个新任务，写入 session_state，并返回当前 state。

    - 全自动模式：同步跑完 4 个节点，返回最终 state（已落盘）
    - 人工审核模式：跑到第 1 个 interrupt 后返回（m1 完成 / 待审核），state 已落盘
    """
    task_id = _make_task_id(task_name)
    init = make_initial_state(
        task_id=task_id,
        task_name=task_name or "未命名任务",
        raw_material=raw_material,
        mode=mode,
        module_models=module_models,
        source_type=source_type,
        source_filename=source_filename,
        temperature=temperature,
    )
    init["overall_status"] = "running"

    graph = build_graph(mode)
    st.session_state[_SK_GRAPH] = graph
    st.session_state[_SK_THREAD] = task_id
    st.session_state[_SK_MODE] = mode

    config = _thread_config(task_id)

    if mode == "auto":
        final = graph.invoke(init, config)
        state = _merge_final_state(init, final)
        state["overall_status"] = "completed"
        state["current_module"] = "m4"
        st.session_state[_SK_STATE] = state
        save_task(state)
        return state

    # 人工审核：跑到第一个 interrupt
    _run_until_interrupt(graph, init, config)
    state = _snapshot_from_checkpoint(graph, config, base=init)
    st.session_state[_SK_STATE] = state
    save_task(state)
    return state


# ============================================================
# 继续任务（审核动作）
# ============================================================
def continue_task(
    action: Literal["approve", "edit", "rerun"],
    *,
    edited_output: Optional[dict] = None,
    comment: str = "",
) -> WorkflowState:
    """处理人工审核动作。

    approve : 直接继续到下一个节点（或完成）
    edit    : 先用 edited_output 覆盖当前模块输出, 再继续
    rerun   : 清空当前模块输出, 从本模块重新执行
    """
    graph = st.session_state.get(_SK_GRAPH)
    thread_id = st.session_state.get(_SK_THREAD)
    if not graph or not thread_id:
        raise RuntimeError("没有活跃任务，无法继续。请先 start_task。")

    config = _thread_config(thread_id)

    # 定位当前所在模块（刚刚 interrupt 的那个）
    state = st.session_state.get(_SK_STATE) or {}
    cur = _current_paused_module(state)
    if cur is None:
        raise RuntimeError("当前任务状态异常，找不到等待审核的模块。")

    if action == "edit" and edited_output is not None:
        # 用 update_state 写入修改后的输出；as_node=cur 表示以该节点身份提交
        graph.update_state(
            config,
            {f"{cur}_output": edited_output, "logs": [f"[review] 模块 {cur} 编辑后通过"]},
            as_node=cur,
        )
    elif action == "rerun":
        # 清空当前模块产出，并把图状态回滚到进入该节点之前
        graph.update_state(
            config,
            {f"{cur}_output": {}, f"{cur}_meta": {"status": "pending"}, "logs": [f"[review] 重跑模块 {cur}"]},
            as_node=_prev_node(cur),
        )

    # 驱动图继续（None 表示 resume）
    _run_until_interrupt(graph, None, config)
    base = st.session_state.get(_SK_STATE) or {}
    state = _snapshot_from_checkpoint(graph, config, base=base)

    # 判断是否已跑完
    if _is_final(state):
        state["overall_status"] = "completed"
    else:
        state["overall_status"] = "awaiting_review"

    st.session_state[_SK_STATE] = state
    save_task(state)
    return state


# ============================================================
# 其他工具
# ============================================================
def get_running_state() -> Optional[WorkflowState]:
    return st.session_state.get(_SK_STATE)


def clear_runtime() -> None:
    for k in (_SK_GRAPH, _SK_THREAD, _SK_STATE, _SK_MODE):
        st.session_state.pop(k, None)


def has_active_task() -> bool:
    state = st.session_state.get(_SK_STATE)
    if not state:
        return False
    return state.get("overall_status") in ("running", "awaiting_review")


# ============================================================
# Internals
# ============================================================
def _thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _run_until_interrupt(graph, input_state, config) -> None:
    """驱动 graph 直到遇到 interrupt 或 END。"""
    for _ in graph.stream(input_state, config):
        pass  # 仅推进；状态由 checkpointer 自动保存


def _snapshot_from_checkpoint(graph, config, *, base: dict) -> WorkflowState:
    """从 MemorySaver 读取最新 state 快照并补上 UI 需要的字段。"""
    try:
        snap = graph.get_state(config)
        values = dict(snap.values) if snap and snap.values else {}
    except Exception:
        values = {}
    merged = WorkflowState(**{**base, **values})
    # 确定当前活跃模块
    merged["current_module"] = _current_paused_module(merged) or "m4"
    return merged


def _merge_final_state(base: dict, final: dict) -> WorkflowState:
    return WorkflowState(**{**base, **final})


def _current_paused_module(state: dict) -> Optional[str]:
    """找到最新一个已完成且后面还有未开始模块的 key。"""
    for i, mk in enumerate(MODULE_KEYS):
        meta = state.get(f"{mk}_meta", {}) or {}
        st_ = meta.get("status")
        if st_ in ("completed", "awaiting_review"):
            # 若后续还有 pending 的模块，则当前即处于"完成等待审核"状态
            if i + 1 < len(MODULE_KEYS):
                next_mk = MODULE_KEYS[i + 1]
                next_status = (state.get(f"{next_mk}_meta", {}) or {}).get("status", "pending")
                if next_status == "pending":
                    return mk
            else:
                return mk
    return None


def _prev_node(current: str) -> str:
    """回滚时的 as_node 目标：当前节点的上一个；m1 的上一个是 __start__。"""
    idx = MODULE_KEYS.index(current)  # type: ignore[arg-type]
    if idx == 0:
        return "__start__"
    return MODULE_KEYS[idx - 1]


def _is_final(state: dict) -> bool:
    m4 = (state.get("m4_meta", {}) or {}).get("status")
    return m4 in ("completed", "approved")


_SLUG_RE = re.compile(r"[^\w\-]+", flags=re.UNICODE)


def _make_task_id(task_name: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _SLUG_RE.sub("-", (task_name or "task")).strip("-")[:24] or "task"
    return f"{ts}-{slug}-{uuid.uuid4().hex[:4]}"


__all__ = [
    "start_task",
    "continue_task",
    "get_running_state",
    "clear_runtime",
    "has_active_task",
]
