"""
页面 3 · 结果详情（Result）

Hero 卡 + 4 个模块 Tab，每个 Tab 支持 结构化 / Markdown / JSON 三视图切换。
数据源：默认 `sample_state_completed()`，可由 `session_state['viewing_task_id']` 触发。
"""
from __future__ import annotations

import json
from copy import deepcopy

import streamlit as st

from src.state import MODULE_KEYS, MODULE_LABELS
from src.ui.components import (
    page_header,
    mode_banner,
    md_headline,
    md_title,
    md_body,
    md_caption,
    md_kv,
    md_chip,
    snackbar,
)
from src.ui.layout import render_sidebar
from src.ui.mocks import (
    sample_state_completed,
    format_duration,
    format_datetime,
    STATUS_TO_CHIP,
)
from src.io_utils import load_task


MODULE_EMOJI = {"m1": "📘", "m2": "🎯", "m3": "📢", "m4": "📝"}
MODE_LABELS_CN = {"auto": "全自动", "human_review": "人工审核"}


def _resolve_task_state() -> dict:
    """根据 viewing_task_id 从磁盘加载对应 state。

    查找顺序：
      1. session_state['current_state'] 若 task_id 匹配且已完成
      2. outputs/{task_id}/state.json
      3. 若 viewing_task_id 为空 → 回落到 sample_state_completed 演示
    """
    task_id = st.session_state.get("viewing_task_id")
    cur = st.session_state.get("current_state")
    if cur and cur.get("task_id") == task_id:
        return cur
    if task_id:
        try:
            return load_task(task_id)
        except FileNotFoundError:
            st.error(f"任务不存在或已被删除：`{task_id}`")
    return deepcopy(sample_state_completed())


# ============================================================
# Hero 卡
# ============================================================
def _render_hero(state: dict) -> None:
    with st.container(border=True):
        top_l, top_r = st.columns([4, 3], vertical_alignment="center")
        with top_l:
            chip_html = md_chip(STATUS_TO_CHIP.get(state.get("overall_status", "completed"), "completed"))
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:12px'>"
                f"{chip_html}"
                f"<span class='md-headline'>{state.get('task_name','未命名任务')}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            m4_meta = state.get("m4_meta", {}) or {}
            finished_at = m4_meta.get("finished_at") or state.get("created_at", "")
            duration = format_duration(
                sum((state.get(f"{mk}_meta", {}) or {}).get("duration_ms", 0) for mk in MODULE_KEYS)
            )
            mode_cn = MODE_LABELS_CN.get(state.get("mode", ""), state.get("mode", ""))
            st.markdown(
                f"<div class='md-body-sm md-mt-2'>"
                f"🕐 {format_datetime(finished_at)} · ⏱ {duration} · ⚙️ {mode_cn}"
                f"</div>",
                unsafe_allow_html=True,
            )

        with top_r:
            b1, b2, b3 = st.columns([1, 1, 1], gap="small")
            with b1:
                st.download_button(
                    "📥 下载报告",
                    data=json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8"),
                    file_name=f"{state.get('task_id','task')}_report.json",
                    mime="application/json",
                    type="primary",
                    use_container_width=True,
                    key="result_download",
                )
            with b2:
                if st.button("🔗 分享", type="secondary", use_container_width=True, key="result_share"):
                    snackbar("分享链接已复制（mock）", icon="🔗")
            with b3:
                if st.button("🔄 重跑", type="secondary", use_container_width=True, key="result_rerun"):
                    st.session_state.pop("current_state", None)
                    st.switch_page("pages/1_workspace.py")

        st.markdown("<hr/>", unsafe_allow_html=True)

        col_models, col_tokens = st.columns(2, gap="large")
        mm = state.get("module_models", {})
        with col_models:
            md_caption("各模块模型")
            for mk in MODULE_KEYS:
                md_kv(
                    f"{MODULE_EMOJI[mk]} {mk.upper()}  {MODULE_LABELS[mk]}",
                    mm.get(mk, "—"),
                    mono=True,
                )
        with col_tokens:
            md_caption("Token 用量 & 用时")
            total_in = 0
            total_out = 0
            for mk in MODULE_KEYS:
                meta = state.get(f"{mk}_meta", {}) or {}
                total_in += meta.get("tokens_in", 0) or 0
                total_out += meta.get("tokens_out", 0) or 0
                md_kv(
                    f"{mk.upper()} 用时",
                    format_duration(meta.get("duration_ms", 0)),
                    mono=True,
                )
            md_kv("合计 Token in", f"{total_in:,}", mono=True)
            md_kv("合计 Token out", f"{total_out:,}", mono=True)


# ============================================================
# 模块内容渲染（结构化）
# ============================================================
def _structured_m1(o: dict) -> None:
    md_title("技术要点")
    for pt in o.get("tech_points", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-mono' style='color:var(--md-on-surface-variant)'>"
                f"原文：{pt.get('original','')}</div>",
                unsafe_allow_html=True,
            )
            md_body(f"🗣️ {pt.get('plain','')}")
            md_caption(f"🔍 {pt.get('analogy','')}")
            if pt.get("params"):
                md_kv("参数", pt["params"], mono=True)
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        md_title("关键能力")
        for c in o.get("capabilities", []) or []:
            md_body(f"· {c}")
    with col2:
        md_title("能力边界")
        for b in o.get("boundaries", []) or []:
            md_body(f"· {b}", small=True)


def _structured_m2(o: dict) -> None:
    with st.container(border=True):
        md_caption("核心主张")
        st.markdown(
            f"<div class='md-title' style='color:var(--md-primary)'>「{o.get('core_claim','')}」</div>",
            unsafe_allow_html=True,
        )
    md_title("技术卖点")
    for sp in o.get("selling_points", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-title'>💡 {sp.get('name','')}</div>",
                unsafe_allow_html=True,
            )
            md_body(sp.get("user_description", ""))
            md_kv("用户需求", sp.get("user_need", "—"))
            md_kv("差异化", sp.get("differentiation", "—"))
            if sp.get("supporting_points"):
                md_kv("支撑点", "、".join(sp["supporting_points"]), mono=True)
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        md_title("目标用户假设")
        for u in o.get("target_user_hypothesis", []) or []:
            md_body(f"· {u}")
    with col2:
        md_title("过滤的技术点")
        for f in o.get("filtered_points", []) or []:
            md_body(f"· {f}", small=True)


def _structured_m3(o: dict) -> None:
    md_title("目标人群")
    for a in o.get("target_audiences", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-title'>👤 {a.get('segment','')}</div>", unsafe_allow_html=True
            )
            md_body(a.get("description", ""))
            md_kv("痛点", "、".join(a.get("pain_points", []) or []))
            md_kv("渠道", "、".join(a.get("preferred_channels", []) or []), mono=True)
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        md_title("核心渠道")
        for ch in o.get("core_channels", []) or []:
            md_body(f"· {ch}")
        md_title("节奏")
        for p in o.get("phases", []) or []:
            md_body(f"· {p}", small=True)
    with col2:
        md_title("KPI")
        for k in o.get("kpis", []) or []:
            md_body(f"· {k}", small=True)
    md_title("内容矩阵")
    for m in o.get("content_matrix", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-title'>📌 {m.get('phase','')}</div>", unsafe_allow_html=True
            )
            md_kv("主打卖点", "、".join(m.get("key_selling_points", []) or []))
            md_kv("内容形态", "、".join(m.get("content_types", []) or []))
            md_kv("切入角度", "、".join(m.get("sample_angles", []) or []))


def _structured_m4(o: dict) -> None:
    with st.container(border=True):
        md_caption("活动主题")
        st.markdown(
            f"<div class='md-title' style='color:var(--md-primary)'>{o.get('campaign_theme','')}</div>"
            f"<div class='md-body-sm md-mt-2'>Slogan：{o.get('slogan','')}</div>",
            unsafe_allow_html=True,
        )
    md_title("视频脚本")
    for v in o.get("video_scripts", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-title'>🎬 {v.get('title','')}</div>"
                f"<div class='md-caption md-mt-2'>{v.get('duration_sec','—')} 秒</div>",
                unsafe_allow_html=True,
            )
            md_kv("Hook", v.get("hook", ""))
            md_body(v.get("body", ""), small=True)
            md_kv("CTA", v.get("cta", ""))
    md_title("长文章")
    with st.container(border=True):
        st.markdown(o.get("article", "—"))
    md_title("社交帖")
    for s in o.get("social_posts", []) or []:
        with st.container(border=True):
            md_kv("平台", s.get("platform", "—"))
            st.markdown(
                f"<div class='md-body' style='font-weight:600'>{s.get('title','')}</div>"
                f"<div class='md-body-sm md-mt-2'>{s.get('body','')}</div>",
                unsafe_allow_html=True,
            )
            if s.get("hashtags"):
                md_caption("  ".join(s["hashtags"]))
    md_title("海报")
    for p in o.get("posters", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-title'>{p.get('headline','')}</div>"
                f"<div class='md-body-sm md-mt-2'>{p.get('subline','')}</div>",
                unsafe_allow_html=True,
            )
            md_kv("视觉关键词", "、".join(p.get("visual_keywords", []) or []))
    if o.get("offline_event"):
        md_title("线下活动")
        ev = o["offline_event"]
        with st.container(border=True):
            st.markdown(f"<div class='md-title'>📅 {ev.get('theme','')}</div>", unsafe_allow_html=True)
            md_caption("流程")
            for f in ev.get("flow", []) or []:
                md_body(f"· {f}", small=True)
            md_kv("物料", "、".join(ev.get("materials", []) or []))
            md_kv("预算", ev.get("budget_framework", "—"))


STRUCTURED = {"m1": _structured_m1, "m2": _structured_m2, "m3": _structured_m3, "m4": _structured_m4}


def _to_markdown(mk: str, output: dict) -> str:
    """把模块输出序列化为便于阅读的 Markdown 文本。"""
    if not output:
        return "_（暂无数据）_"
    title = f"# {MODULE_EMOJI[mk]} {mk.upper()} · {MODULE_LABELS[mk]}\n\n"
    body = ""
    if mk == "m1":
        body += "## 技术要点\n\n"
        for pt in output.get("tech_points", []) or []:
            body += f"- **原文**：{pt.get('original','')}\n"
            body += f"  - 通俗：{pt.get('plain','')}\n"
            body += f"  - 类比：{pt.get('analogy','')}\n"
            if pt.get("params"):
                body += f"  - 参数：`{pt['params']}`\n"
        body += "\n## 关键能力\n\n" + "\n".join(f"- {c}" for c in output.get("capabilities", []) or [])
        body += "\n\n## 能力边界\n\n" + "\n".join(f"- {c}" for c in output.get("boundaries", []) or [])
    elif mk == "m2":
        body += f"**核心主张**：{output.get('core_claim','')}\n\n## 技术卖点\n\n"
        for sp in output.get("selling_points", []) or []:
            body += f"### 💡 {sp.get('name','')}\n"
            body += f"{sp.get('user_description','')}\n\n"
            body += f"- 用户需求：{sp.get('user_need','')}\n"
            body += f"- 差异化：{sp.get('differentiation','')}\n"
    elif mk == "m3":
        body += "## 目标人群\n\n"
        for a in output.get("target_audiences", []) or []:
            body += f"- **{a.get('segment','')}**：{a.get('description','')}\n"
    elif mk == "m4":
        body += f"**活动主题**：{output.get('campaign_theme','')}\n\n"
        body += f"**Slogan**：{output.get('slogan','')}\n\n"
        body += "## 长文章\n\n" + output.get("article", "—") + "\n"
    return title + body


def _render_module_tab(mk: str, state: dict) -> None:
    output = state.get(f"{mk}_output", {}) or {}
    meta = state.get(f"{mk}_meta", {}) or {}

    top_l, top_r = st.columns([3, 2], vertical_alignment="center")
    with top_l:
        md_kv("用时", format_duration(meta.get("duration_ms", 0)), mono=True)
        md_kv(
            "Tokens",
            f"{meta.get('tokens_in',0)} in · {meta.get('tokens_out',0)} out",
            mono=True,
        )
        md_kv("模型", meta.get("model", "—"), mono=True)
    with top_r:
        view = st.radio(
            "视图",
            options=["structured", "markdown", "json"],
            format_func=lambda v: {
                "structured": "📊 结构化",
                "markdown": "📝 Markdown",
                "json": "🔢 原始 JSON",
            }[v],
            horizontal=True,
            key=f"result_view_{mk}",
        )

    md_text = _to_markdown(mk, output)
    act_l, act_r = st.columns([6, 2])
    with act_r:
        a, b = st.columns(2, gap="small")
        with a:
            if st.button("📋 复制", key=f"result_copy_{mk}", type="tertiary", use_container_width=True):
                snackbar("已复制到剪贴板（mock）", icon="📋")
        with b:
            st.download_button(
                "💾 .md",
                data=md_text.encode("utf-8"),
                file_name=f"{state.get('task_id','task')}_{mk}.md",
                mime="text/markdown",
                type="secondary",
                use_container_width=True,
                key=f"result_dl_{mk}",
            )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if view == "structured":
        STRUCTURED[mk](output)
    elif view == "markdown":
        with st.container(border=True):
            st.markdown(md_text)
    else:
        st.json(output, expanded=True)


# ============================================================
# Page entry
# ============================================================
def render_result() -> None:
    page_header("结果详情")

    state = _resolve_task_state()

    render_sidebar(current="result")

    mode_banner(state.get("mode", "human_review") if state.get("mode") in ("auto", "human_review") else "human_review")

    md_headline("结果详情")
    md_caption(f"任务 ID：{state.get('task_id','—')}")
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    _render_hero(state)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    tab_labels = [f"{MODULE_EMOJI[mk]} {MODULE_LABELS[mk]}" for mk in MODULE_KEYS]
    tabs = st.tabs(tab_labels)
    for i, mk in enumerate(MODULE_KEYS):
        with tabs[i]:
            _render_module_tab(mk, state)


render_result()
