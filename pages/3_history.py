"""
页面 4 · 历史记录（History）

筛选条 + 任务卡片列表，支持搜索 / 状态 / 模式筛选，以及查看 / 继续 / 删除。
mock 阶段数据来自 `sample_history_list()`，删除仅在 session 内生效。
"""
from __future__ import annotations

import streamlit as st

from src.ui.components import (
    page_header,
    mode_banner,
    md_headline,
    md_caption,
    md_chip,
    snackbar,
)
from src.ui.layout import render_sidebar
from src.ui.mocks import (
    format_datetime,
    format_duration,
    STATUS_TO_CHIP,
)
from src.io_utils import list_tasks, delete_task
from src.config_utils import env_status


STATUS_FILTER_OPTIONS = {
    "all": "全部状态",
    "completed": "已完成",
    "interrupted": "中断",
    "running": "运行中",
    "failed": "失败",
}
MODE_FILTER_OPTIONS = {"all": "全部模式", "auto": "全自动", "human_review": "人工审核"}
MODE_LABELS_CN = {"auto": "全自动", "human_review": "人工审核"}


def _init_history_cache() -> list[dict]:
    """从 outputs/ 扫描持久化任务。每次页面加载都重新读取, 保证新完成任务可见。"""
    st.session_state["history_cache"] = list_tasks()
    return st.session_state["history_cache"]


def _filter_rows(
    rows: list[dict],
    *,
    keyword: str,
    status: str,
    mode: str,
) -> list[dict]:
    out = []
    kw = (keyword or "").strip().lower()
    for r in rows:
        if kw and kw not in (r.get("task_name", "") or "").lower() and kw not in (r.get("task_id", "") or "").lower():
            continue
        if status != "all" and r.get("status") != status:
            continue
        if mode != "all" and r.get("mode") != mode:
            continue
        out.append(r)
    return out


# ============================================================
# 单行任务卡
# ============================================================
def _task_card(row: dict) -> None:
    chip_status = STATUS_TO_CHIP.get(row.get("status", ""), "pending")
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.2, 5, 2.2], gap="small", vertical_alignment="center")
        with c1:
            st.markdown(md_chip(chip_status), unsafe_allow_html=True)
        with c2:
            mode_cn = MODE_LABELS_CN.get(row.get("mode", ""), row.get("mode", ""))
            duration = format_duration(row.get("duration_ms", 0)) if row.get("duration_ms") else "—"
            stage = (row.get("current_stage", "") or "").upper()
            models = row.get("models", {})
            model_list = ", ".join(
                sorted({models.get(mk, "") for mk in ("m1", "m2", "m3", "m4") if models.get(mk)})
            )
            st.markdown(
                f"<div class='md-body' style='font-weight:600'>{row.get('task_name','')}</div>"
                f"<div class='md-body-sm md-mt-2'>"
                f"{mode_cn} · {duration} · 当前阶段 {stage or '—'}"
                f"</div>"
                f"<div class='md-caption md-mt-2'>"
                f"{format_datetime(row.get('created_at'))}"
                f" · <span class='md-mono'>{model_list}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with c3:
            b1, b2, b3 = st.columns([2, 2, 1.5], gap="small")
            with b1:
                if st.button(
                    "查看",
                    key=f"hist_view_{row['task_id']}",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state["viewing_task_id"] = row["task_id"]
                    if row.get("status") == "completed":
                        st.switch_page("pages/2_result.py")
                    else:
                        st.switch_page("pages/1_workspace.py")
            with b2:
                if row.get("status") == "interrupted":
                    if st.button(
                        "继续",
                        key=f"hist_resume_{row['task_id']}",
                        type="secondary",
                        use_container_width=True,
                    ):
                        st.session_state["viewing_task_id"] = row["task_id"]
                        st.switch_page("pages/1_workspace.py")
                else:
                    st.write("")
            with b3:
                with st.popover("🗑️", use_container_width=True):
                    st.markdown(f"**确认删除任务？**")
                    md_caption(row["task_name"])
                    md_caption("将永久删除 outputs/{task_id}/ 下的所有文件。")
                    if st.button(
                        "确认删除",
                        key=f"hist_confirm_del_{row['task_id']}",
                        type="primary",
                        use_container_width=True,
                    ):
                        delete_task(row["task_id"])
                        st.session_state.pop("history_cache", None)
                        snackbar(f"已删除：{row['task_name']}", icon="🗑️")
                        st.rerun()


# ============================================================
# Empty state
# ============================================================
def _empty_state() -> None:
    with st.container(border=True):
        st.markdown(
            "<div style='text-align:center;padding:40px 0'>"
            "<div style='font-size:56px'>🗂️</div>"
            "<div class='md-title md-mt-3'>还没有任务</div>"
            "<div class='md-caption md-mt-2'>从首页或工作台新建一条，开始你的第一次流水线</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns([2, 1, 2])
        with c2:
            if st.button("🚀 新建任务", type="primary", use_container_width=True, key="hist_new"):
                st.switch_page("pages/1_workspace.py")


# ============================================================
# Page entry
# ============================================================
def render_history() -> None:
    page_header("历史记录")

    render_sidebar(current="history")

    env = env_status()
    mode_banner(env.get("default_mode", "human_review"))

    md_headline("历史记录")
    md_caption("所有跑过的任务都在这里可回看、继续或重跑")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Filter row
    fc1, fc2, fc3, fc4 = st.columns([5, 2, 2, 1], vertical_alignment="bottom")
    with fc1:
        keyword = st.text_input(
            "搜索",
            placeholder="按任务名或 ID 搜索…",
            label_visibility="collapsed",
            key="hist_kw",
        )
    with fc2:
        status = st.selectbox(
            "状态",
            options=list(STATUS_FILTER_OPTIONS.keys()),
            format_func=lambda v: STATUS_FILTER_OPTIONS[v],
            label_visibility="collapsed",
            key="hist_status",
        )
    with fc3:
        mode = st.selectbox(
            "模式",
            options=list(MODE_FILTER_OPTIONS.keys()),
            format_func=lambda v: MODE_FILTER_OPTIONS[v],
            label_visibility="collapsed",
            key="hist_mode",
        )
    with fc4:
        if st.button("↻", key="hist_refresh", use_container_width=True, help="刷新"):
            st.session_state.pop("history_cache", None)
            snackbar("已刷新历史列表", icon="↻")
            st.rerun()

    all_rows = _init_history_cache()
    filtered = _filter_rows(all_rows, keyword=keyword, status=status, mode=mode)

    st.markdown(
        f"<div class='md-caption md-mt-3'>共 {len(filtered)} / {len(all_rows)} 条</div>",
        unsafe_allow_html=True,
    )

    if not filtered:
        _empty_state()
        return

    for row in filtered:
        _task_card(row)


render_history()
