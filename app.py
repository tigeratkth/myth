"""
业务智能体 · Streamlit 主入口 + 首页 / 工作台

- 页面 1（Home）内容直接渲染在本文件
- 页面 2~5 通过 Streamlit `pages/` 目录自动发现
- 使用 `src/ui/layout.render_sidebar` 统一侧边栏（自定义中文导航）
"""
from __future__ import annotations

import streamlit as st

from src.ui.components import (
    page_header,
    mode_banner,
    md_display,
    md_caption,
    md_headline,
    md_title,
    md_body,
    md_chip,
    md_card_open,
    md_card_close,
)
from src.ui.layout import render_sidebar
from src.ui.mocks import (
    STATUS_TO_CHIP,
    format_datetime,
    format_duration,
)
from src.config_utils import env_status
from src.io_utils import list_tasks


MODE_LABELS_CN = {"auto": "全自动", "human_review": "人工审核"}


def _current_task_for_sidebar() -> tuple:
    """根据 session_state 决定 sidebar 底部徽章展示的活跃任务。"""
    state = st.session_state.get("current_state")
    if not state:
        return None, None
    status = state.get("overall_status")
    if status in ("running", "awaiting_review"):
        name = state.get("task_name") or "未命名任务"
        cur = state.get("current_module", "m1").upper()
        stage = f"{cur} · {'待审核' if status == 'awaiting_review' else '运行中'}"
        return name, stage
    return None, None


def _env_status_cards(env: dict) -> None:
    """首页环境状态 3 卡片。"""
    col1, col2, col3 = st.columns(3, gap="medium")

    with col1:
        with st.container(border=True):
            md_title("🔑 API Key")
            keys = env["api_keys"]
            configured = keys["configured_count"]
            total = keys["total_providers"]
            if configured > 0:
                st.markdown(
                    f"<div class='md-body' style='color:var(--md-success);font-weight:600'>"
                    f"{configured} / {total} 家已配置</div>",
                    unsafe_allow_html=True,
                )
                md_caption("· ".join(keys["providers"]))
            else:
                st.markdown(
                    "<div class='md-body' style='color:var(--md-error);font-weight:600'>"
                    "未配置</div>",
                    unsafe_allow_html=True,
                )
                md_caption("前往设置添加至少一个 Key")
            st.page_link("pages/4_settings.py", label="管理 →")

    with col2:
        with st.container(border=True):
            md_title("🧠 默认模型")
            dm = env["default_model"]
            md_body(dm["summary"])
            md_caption("用于新任务的默认配置")
            st.page_link("pages/4_settings.py", label="更改 →")

    with col3:
        with st.container(border=True):
            md_title("⚙️ 默认模式")
            mode = env["default_mode"]
            md_body(MODE_LABELS_CN.get(mode, mode))
            md_caption("全自动 = 一气呵成；人工审核 = 逐模块确认")
            st.page_link("pages/4_settings.py", label="切换 →")


def _main_cta() -> None:
    """大号主 CTA 卡片。"""
    md_card_open(accent=True, extra_class="md-mt-4")
    c1, c2 = st.columns([4, 1], gap="medium")
    with c1:
        st.markdown(
            "<div class='md-title'>🚀 新建任务</div>"
            "<div class='md-body-sm md-mt-2'>"
            "上传技术资料或粘贴文本，进入 4 模块流水线工作台"
            "</div>",
            unsafe_allow_html=True,
        )
    with c2:
        if st.button("开始 →", type="primary", use_container_width=True, key="home_cta"):
            st.session_state.pop("current_state", None)
            st.switch_page("pages/1_workspace.py")
    md_card_close()


def _recent_tasks_row(task: dict) -> None:
    """单行最近任务卡。"""
    chip_status = STATUS_TO_CHIP.get(task["status"], "pending")
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.2, 5, 1.2], gap="small", vertical_alignment="center")
        with c1:
            st.markdown(md_chip(chip_status), unsafe_allow_html=True)
        with c2:
            mode_cn = MODE_LABELS_CN.get(task["mode"], task["mode"])
            meta_parts = [mode_cn, format_datetime(task["created_at"])]
            if task.get("duration_ms"):
                meta_parts.append(format_duration(task["duration_ms"]))
            elif task["status"] == "running":
                meta_parts.append("进行中")
            meta_text = " · ".join(meta_parts)
            models = task.get("models", {})
            model_summary = models.get("m2", "") or models.get("m1", "")
            st.markdown(
                f"<div class='md-body' style='font-weight:600'>{task['task_name']}</div>"
                f"<div class='md-body-sm md-mt-2'>{meta_text}"
                f" · <span class='md-mono'>{model_summary}</span></div>",
                unsafe_allow_html=True,
            )
        with c3:
            if task["status"] == "interrupted":
                btn_label = "继续"
            elif task["status"] == "running":
                btn_label = "进入"
            else:
                btn_label = "查看"
            if st.button(btn_label, key=f"home_task_{task['task_id']}", use_container_width=True):
                st.session_state["viewing_task_id"] = task["task_id"]
                if task["status"] in ("interrupted", "running"):
                    st.switch_page("pages/1_workspace.py")
                else:
                    st.switch_page("pages/2_result.py")


def render_home() -> None:
    page_header("工作台")

    env = env_status()
    default_mode = env.get("default_mode", "human_review")

    task_name, stage = _current_task_for_sidebar()
    render_sidebar(current="home", task_name=task_name, stage=stage)

    mode_banner(default_mode if default_mode in ("auto", "human_review") else "human_review")

    st.markdown(
        "<div class='md-hero-block md-fade-in'>"
        "<div class='md-label' style='color:var(--md-primary)'>BUSINESS INTELLIGENCE AGENT</div>"
        "<h1 class='md-display' style='margin-top:8px'>欢迎回来</h1>"
        "<div class='md-body md-mt-3' style='max-width:560px;color:var(--md-on-surface-variant)'>"
        "把技术说给用户听 — 4 模块流水线，自动或手动皆宜。从原始技术资料到可传播的营销内容，"
        "一条龙搞定。"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    md_headline("环境状态")
    _env_status_cards(env)

    _main_cta()

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    head_c1, head_c2 = st.columns([6, 1], vertical_alignment="bottom")
    with head_c1:
        md_headline("最近任务")
    with head_c2:
        if st.button("查看全部 →", key="home_view_all", type="tertiary", use_container_width=True):
            st.switch_page("pages/3_history.py")

    tasks = list_tasks()[:5]
    if not tasks:
        with st.container(border=True):
            st.markdown(
                "<div style='text-align:center;padding:24px 0'>"
                "<div style='font-size:40px'>🗂️</div>"
                "<div class='md-body md-mt-2'>还没有任务，去新建一个吧</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("🚀 新建任务", type="primary", key="home_empty_new"):
                st.switch_page("pages/1_workspace.py")
    else:
        for task in tasks:
            _recent_tasks_row(task)


render_home()
