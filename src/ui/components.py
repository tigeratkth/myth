"""
Material Design 风格的 UI 组件库

通过向 Streamlit 注入自定义 HTML + CSS 类实现。所有样式定义在 styles/global.css 中。
组件函数命名统一以 md_ 前缀，保持与设计系统的对应关系。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal, Optional

import streamlit as st

# ============================================================
# 基础设施
# ============================================================
_STYLES_PATH = Path(__file__).resolve().parents[2] / "styles" / "global.css"
_ICON_CDN = (
    '<link rel="stylesheet" '
    'href="https://fonts.googleapis.com/css2?'
    'family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,300,0,0" />'
)


def inject_global_styles() -> None:
    """在 Streamlit 应用开头注入全局 CSS + 图标库 + 顶部渐变线。

    调用位置：app.py 与每个 pages/*.py 的顶部（使用 page_header 辅助函数可一次搞定）。
    """
    if _STYLES_PATH.exists():
        css = _STYLES_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    st.markdown(_ICON_CDN, unsafe_allow_html=True)
    st.markdown('<div class="md-top-line"></div>', unsafe_allow_html=True)


def page_header(page_title: str, *, layout: str = "wide", icon: str = "🤖") -> None:
    """每个页面的标准开场：page_config + 全局样式注入。"""
    st.set_page_config(
        page_title=f"业务智能体 · {page_title}",
        page_icon=icon,
        layout=layout,
        initial_sidebar_state="expanded",
    )
    inject_global_styles()


# ============================================================
# 图标
# ============================================================
def md_icon(name: str, size: Literal["sm", "md", "lg"] = "md", color: Optional[str] = None) -> str:
    """返回 Material Symbols Rounded 图标 HTML 字符串。

    name: Material Symbols 名称（如 rocket_launch、settings、check_circle）
    """
    style = f'style="color:{color}"' if color else ""
    return (
        f'<span class="material-symbols-rounded md-icon-{size}" {style}>{name}</span>'
    )


# ============================================================
# Banner · 模式提示等横幅
# ============================================================
BannerType = Literal["info", "warning", "success", "error"]


def md_banner(
    banner_type: BannerType,
    title: str,
    description: str = "",
    icon: str = "info",
    action_label: Optional[str] = None,
) -> None:
    """渲染 Material 横幅（含左侧色条与图标）。"""
    action_html = (
        f'<span class="md-banner-action">{action_label}</span>' if action_label else ""
    )
    desc_html = (
        f'<div class="md-banner-desc">{description}</div>' if description else ""
    )
    html = f"""
    <div class="md-banner md-banner-{banner_type}">
      <span class="material-symbols-rounded md-icon-md md-banner-icon">{icon}</span>
      <div class="md-banner-content">
        <div class="md-banner-title">{title}</div>
        {desc_html}
      </div>
      {action_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def mode_banner(mode: Literal["auto", "human_review"]) -> None:
    """双模式的标准提示 Banner。"""
    if mode == "auto":
        md_banner(
            "warning",
            "当前模式：全自动",
            "输入后将一次性运行 4 个模块，中间不停顿",
            icon="autorenew",
            action_label="切换 →",
        )
    else:
        md_banner(
            "info",
            "当前模式：人工审核",
            "每个模块完成后会暂停，等待你确认 / 修改 / 重跑",
            icon="reviews",
            action_label="切换 →",
        )


# ============================================================
# Chips · 状态胶囊
# ============================================================
ChipStatus = Literal["completed", "running", "awaiting", "failed", "pending"]

_CHIP_LABELS: dict[ChipStatus, str] = {
    "completed": "已完成",
    "running": "运行中",
    "awaiting": "待审核",
    "failed": "失败",
    "pending": "未开始",
}


def md_chip(status: ChipStatus, text: Optional[str] = None) -> str:
    """返回状态胶囊 HTML 字符串。"""
    label = text if text is not None else _CHIP_LABELS[status]
    return (
        f'<span class="md-chip md-chip-{status}">'
        f'<span class="md-chip-dot"></span>{label}</span>'
    )


def md_chip_render(status: ChipStatus, text: Optional[str] = None) -> None:
    st.markdown(md_chip(status, text), unsafe_allow_html=True)


# ============================================================
# Card · 标准卡片
# ============================================================
def md_card_open(accent: bool = False, extra_class: str = "") -> None:
    """开启一个自定义 HTML 卡片。必须以 md_card_close() 配对。"""
    classes = "md-card"
    if accent:
        classes += " md-card-accent"
    if extra_class:
        classes += " " + extra_class
    st.markdown(f'<div class="{classes}">', unsafe_allow_html=True)


def md_card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# KV Row · 键值对展示
# ============================================================
def md_kv(label: str, value: str, mono: bool = False) -> None:
    """单行 key-value 展示，常用于 meta 信息。"""
    cls = "md-kv-value mono" if mono else "md-kv-value"
    html = (
        f'<div class="md-kv">'
        f'<span class="md-kv-label">{label}</span>'
        f'<span class="{cls}">{value}</span>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# Step Progress · 四模块步骤条
# ============================================================
StepState = Literal["pending", "running", "completed", "awaiting", "failed"]


def md_step_progress(
    steps: list[tuple[str, str]],
    states: list[StepState],
    metas: Optional[list[str]] = None,
) -> None:
    """渲染四模块步骤条。

    steps : [(short_label, full_label), ...]，例如 [("M1", "技术翻译"), ...]
    states: 与 steps 等长，每步的状态
    metas : 可选，每步下方的 meta 文字（用时/token）
    """
    assert len(steps) == len(states), "steps 与 states 长度必须一致"
    if metas is None:
        metas = [""] * len(steps)

    nodes_html = []
    for i, ((short, label), state, meta) in enumerate(zip(steps, states, metas)):
        state_cls = f"md-step-{state}" if state != "pending" else ""
        connector_done = ""
        if i > 0:
            if states[i - 1] == "completed":
                connector_done = " done"
            nodes_html.append(
                f'<div class="md-step-connector{connector_done}"></div>'
            )
        icon = {
            "completed": "✓",
            "running": short,
            "awaiting": "!",
            "failed": "✕",
            "pending": short,
        }[state]
        meta_html = f'<div class="md-step-meta">{meta}</div>' if meta else ""
        nodes_html.append(
            f"""
            <div class="md-step {state_cls}">
              <div class="md-step-node">{icon}</div>
              <div class="md-step-label">{label}</div>
              {meta_html}
            </div>
            """
        )

    html = f'<div class="md-steps">{"".join(nodes_html)}</div>'
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# Typography helpers
# ============================================================
def md_display(text: str) -> None:
    st.markdown(f'<h1 class="md-display">{text}</h1>', unsafe_allow_html=True)


def md_headline(text: str) -> None:
    st.markdown(f'<h2 class="md-headline">{text}</h2>', unsafe_allow_html=True)


def md_title(text: str) -> None:
    st.markdown(f'<h3 class="md-title">{text}</h3>', unsafe_allow_html=True)


def md_body(text: str, small: bool = False, mono: bool = False) -> None:
    cls = "md-body-sm" if small else "md-body"
    if mono:
        cls += " md-mono"
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def md_caption(text: str) -> None:
    st.markdown(f'<div class="md-caption">{text}</div>', unsafe_allow_html=True)


# ============================================================
# 侧边栏徽章 · 当前任务
# ============================================================
def sidebar_task_badge(
    task_name: Optional[str] = None,
    stage: Optional[str] = None,
) -> None:
    """在侧边栏底部渲染"当前任务"徽章。

    task_name 为 None 表示无活跃任务。
    """
    if task_name:
        html = f"""
        <div class="md-sidebar-badge active">
          <div class="md-sidebar-badge-title">🔵 运行中</div>
          <div>{task_name}</div>
          <div class="md-caption md-mt-2">{stage or ""}</div>
        </div>
        """
    else:
        html = """
        <div class="md-sidebar-badge">
          <div class="md-sidebar-badge-title">◯ 无活跃任务</div>
          <div>从工作台或新建页开始</div>
        </div>
        """
    st.sidebar.markdown(html, unsafe_allow_html=True)


# ============================================================
# Snackbar · 临时提示（Streamlit 1.27+ 原生 st.toast 已够用，这里包一层文案约定）
# ============================================================
def snackbar(message: str, icon: str = "✅") -> None:
    st.toast(message, icon=icon)
