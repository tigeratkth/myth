"""
共享布局：侧边栏、页面外壳

封装所有页面都会用到的侧边栏结构（Logo + 导航 + 任务徽章 + 版本），
以及对 Streamlit 默认 pages/ 自动导航的隐藏，避免重复两套导航入口。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import streamlit as st

from .components import sidebar_task_badge


_NAV_ITEMS = [
    ("home", "app.py", "🏠 工作台"),
    ("workspace", "pages/1_workspace.py", "🆕 新建 & 运行"),
    ("result", "pages/2_result.py", "📄 结果详情"),
    ("history", "pages/3_history.py", "📚 历史记录"),
    ("settings", "pages/4_settings.py", "⚙️ 模型与设置"),
]


def _hide_default_nav() -> None:
    """隐藏 Streamlit 从 pages/ 目录自动生成的 sidebar 导航。

    我们用 `st.page_link` 构建中文标签的自定义导航，以替代默认英文文件名导航。
    """
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] { display: none; }
        section[data-testid="stSidebar"] .st-emotion-cache-79elbk { display: none; }
        section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] { padding-top: 0.25rem; }
        .md-sidebar-logo {
            text-align: center;
            padding: 16px 0 12px 0;
            border-bottom: 1px solid var(--md-outline);
            margin-bottom: 12px;
        }
        .md-sidebar-logo-title {
            font-size: 18px;
            font-weight: 700;
            background: linear-gradient(135deg, var(--md-primary), var(--md-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: 0.5px;
        }
        .md-sidebar-logo-sub {
            font-size: 11px;
            color: var(--md-on-surface-variant);
            margin-top: 2px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(
    current: str = "home",
    *,
    task_name: Optional[str] = None,
    stage: Optional[str] = None,
) -> None:
    """统一侧边栏结构。

    current: 当前页面 key，之一：home / workspace / result / history / settings。
    task_name: 当前活跃任务名；传 None 即显示 "无活跃任务"。
    stage: 当前阶段文本（如 "M2 · 技术IP"）。
    """
    _hide_default_nav()

    with st.sidebar:
        st.markdown(
            """
            <div class="md-sidebar-logo">
              <div class="md-sidebar-logo-title">★ 业务智能体</div>
              <div class="md-sidebar-logo-sub">Tech → IP → Growth → Content</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for key, path, label in _NAV_ITEMS:
            st.page_link(path, label=label, disabled=(key == current))

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    sidebar_task_badge(task_name, stage)

    with st.sidebar:
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        st.caption("v0.1.0 · [GitHub](https://github.com/)")


def ensure_workspace_root() -> Path:
    """返回工作区根目录路径（training/）。页面写入落盘时避免相对路径踩坑。"""
    return Path(__file__).resolve().parents[2]
