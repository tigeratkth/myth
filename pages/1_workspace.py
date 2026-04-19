"""
页面 2 · 新建 & 运行（Workspace）

三段式：
- Section A · 资料与参数（idle 展开）
- Section B · 流水线进度步骤条（非 idle 常驻）
- Section C · 当前模块交互区（依状态渲染）
- Section D · 已完成模块历史（折叠）

调试期顶部放"Mock 场景切换器"，便于预览 4 种状态。
"""
from __future__ import annotations

import json
from copy import deepcopy

import streamlit as st
import yaml

from src.state import MODULE_KEYS, MODULE_LABELS
from src.ui.components import (
    page_header,
    mode_banner,
    md_headline,
    md_title,
    md_caption,
    md_body,
    md_chip,
    md_step_progress,
    md_kv,
    snackbar,
)
from src.ui.layout import render_sidebar, ensure_workspace_root
from src.ui.mocks import (
    sample_state_idle,
    sample_state_running,
    sample_state_awaiting_review,
    sample_state_completed,
    format_duration,
)
from src import runtime
from src.io_utils import read_material, load_task


SCENE_FACTORIES = {
    "idle": sample_state_idle,
    "running": sample_state_running,
    "awaiting_review": sample_state_awaiting_review,
    "completed": sample_state_completed,
}
SCENE_LABELS = {
    "idle": "① Idle · 未开始",
    "running": "② Running · 运行中",
    "awaiting_review": "③ AwaitingReview · 等待审核",
    "completed": "④ Completed · 已完成",
}
MODULE_EMOJI = {"m1": "📘", "m2": "🎯", "m3": "📢", "m4": "📝"}
MODE_LABELS_CN = {"auto": "全自动", "human_review": "人工审核"}


# ============================================================
# 工具：读 config.yaml 的模型注册表
# ============================================================
@st.cache_data(ttl=60)
def load_enabled_models() -> list[dict]:
    cfg_path = ensure_workspace_root() / "config.yaml"
    if not cfg_path.exists():
        return []
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return [m for m in (data.get("models") or []) if m.get("enabled")]


def _chip_status_for(module_status: str) -> str:
    mapping = {
        "pending": "pending",
        "running": "running",
        "awaiting_review": "awaiting",
        "approved": "completed",
        "completed": "completed",
        "failed": "failed",
    }
    return mapping.get(module_status, "pending")


def _step_state_for(module_status: str) -> str:
    mapping = {
        "pending": "pending",
        "running": "running",
        "awaiting_review": "awaiting",
        "approved": "completed",
        "completed": "completed",
        "failed": "failed",
    }
    return mapping.get(module_status, "pending")


def _meta_text(module_status: str, meta: dict) -> str:
    if module_status == "completed" and meta.get("duration_ms"):
        return format_duration(meta["duration_ms"])
    if module_status == "running":
        return "运行中"
    if module_status == "awaiting_review":
        return "待审核"
    if module_status == "failed":
        return "失败"
    return ""


# ============================================================
# 调试器：场景切换
# ============================================================
def _scene_switcher_sidebar() -> None:
    with st.sidebar.expander("🛠️ 调试 · 场景切换", expanded=False):
        st.caption("仅开发期使用，切换当前 WorkflowState 的 overall_status")
        current_scene = st.session_state.get("_scene", "idle")
        scene = st.radio(
            "选择场景",
            list(SCENE_FACTORIES.keys()),
            index=list(SCENE_FACTORIES.keys()).index(current_scene),
            format_func=lambda k: SCENE_LABELS[k],
            key="_scene_radio",
        )
        if scene != current_scene:
            st.session_state["_scene"] = scene
            st.session_state["current_state"] = deepcopy(SCENE_FACTORIES[scene]())
            st.rerun()


# ============================================================
# Section A · 资料与参数
# ============================================================
def _section_a(models: list[dict]) -> None:
    md_headline("新建任务")
    md_caption("第 1 步 · 准备资料与运行参数")
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    tab_upload, tab_paste = st.tabs(["📎 上传文件", "📝 粘贴文本"])
    with tab_upload:
        uploaded = st.file_uploader(
            "选择技术资料",
            type=["txt", "md", "docx", "pdf"],
            help="支持 txt / md / docx / pdf，单文件 ≤ 10MB",
            key="ws_upload",
        )
        if uploaded is not None:
            md_caption(f"已选择：`{uploaded.name}` · {uploaded.size // 1024} KB")

    with tab_paste:
        pasted = st.text_area(
            "粘贴技术资料",
            height=300,
            placeholder="把产品规格书 / 技术白皮书 / 论文摘要粘贴在这里…",
            key="ws_paste",
        )
        if pasted:
            md_caption(f"{len(pasted)} 字")

    task_name = st.text_input(
        "任务名（可选）",
        placeholder="例：芯片X 技术IP 包装",
        key="ws_task_name",
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    md_title("运行参数")
    col_mode, col_model = st.columns(2, gap="large")
    with col_mode:
        mode = st.radio(
            "运行模式",
            options=["human_review", "auto"],
            format_func=lambda v: f"{'🧑‍⚖️ 人工审核' if v == 'human_review' else '🤖 全自动'}",
            horizontal=True,
            key="ws_mode",
        )
        if mode == "auto":
            md_caption("一次性跑完 4 个模块，中间不停顿")
        else:
            md_caption("每个模块完成后暂停，等待你确认 / 修改 / 重跑")

    with col_model:
        model_config = st.radio(
            "模型配置",
            options=["global", "per_module"],
            format_func=lambda v: "🌐 全局统一" if v == "global" else "🧩 分模块指定",
            horizontal=True,
            key="ws_model_config",
        )

    model_options = [m["id"] for m in models] or ["（尚未配置模型）"]
    model_display = {m["id"]: f"{m['display_name']}（{m['id']}）" for m in models}

    if model_config == "global":
        chosen = st.selectbox(
            "所有模块使用",
            options=model_options,
            format_func=lambda v: model_display.get(v, v),
            key="ws_global_model",
        )
        st.session_state["_ws_module_models"] = {k: chosen for k in MODULE_KEYS}
    else:
        cols = st.columns(4, gap="small")
        module_models: dict[str, str] = {}
        for i, mk in enumerate(MODULE_KEYS):
            with cols[i]:
                module_models[mk] = st.selectbox(
                    f"{MODULE_EMOJI[mk]} {mk.upper()} · {MODULE_LABELS[mk]}",
                    options=model_options,
                    format_func=lambda v: model_display.get(v, v),
                    key=f"ws_model_{mk}",
                )
        st.session_state["_ws_module_models"] = module_models

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    uploaded = st.session_state.get("ws_upload")
    pasted = st.session_state.get("ws_paste", "") or ""
    material_text = ""
    source_type: str = "paste"
    source_filename = ""
    if uploaded is not None:
        try:
            material_text = read_material(uploaded, uploaded.name)
            source_type = "upload"
            source_filename = uploaded.name
        except Exception as e:  # noqa: BLE001
            st.error(f"读取上传文件失败：{e}")
    elif pasted.strip():
        material_text = pasted.strip()

    has_material = bool(material_text.strip())
    has_models = bool(model_options) and model_options != ["（尚未配置模型）"]

    if st.button(
        "🚀 开始运行",
        type="primary",
        use_container_width=True,
        disabled=not (has_material and has_models),
        key="ws_start",
    ):
        chosen_models = st.session_state.get("_ws_module_models") or {
            k: model_options[0] for k in MODULE_KEYS
        }
        try:
            with st.spinner("正在启动..." if mode == "human_review" else "正在运行流水线(全自动)..."):
                runtime.start_task(
                    raw_material=material_text,
                    task_name=task_name or "未命名任务",
                    mode=mode,
                    module_models=chosen_models,
                    source_type=source_type,  # type: ignore[arg-type]
                    source_filename=source_filename,
                )
            st.session_state["_scene"] = "running"  # 调试器同步
            if mode == "auto":
                snackbar("任务已完成，可在结果页查看", icon="✅")
            else:
                snackbar("M1 已完成，请审核", icon="⏸")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"任务启动失败：{e}")


# ============================================================
# Section A 折叠版摘要（非 idle 时显示）
# ============================================================
def _section_a_summary(state: dict) -> None:
    with st.expander("📋 资料与参数（已折叠）", expanded=False):
        md_body(
            f"**任务名**：{state.get('task_name') or '—'}  |  "
            f"**模式**：{MODE_LABELS_CN.get(state.get('mode', ''), state.get('mode', ''))}  |  "
            f"**来源**：{state.get('source_type', '—')}"
        )
        md_caption("模块模型：")
        mm = state.get("module_models", {})
        for mk in MODULE_KEYS:
            md_kv(f"{MODULE_EMOJI[mk]} {mk.upper()} · {MODULE_LABELS[mk]}", mm.get(mk, "—"), mono=True)


# ============================================================
# Section B · 流水线进度步骤条
# ============================================================
def _section_b(state: dict) -> None:
    md_headline("流水线进度")
    steps = [(mk.upper(), MODULE_LABELS[mk]) for mk in MODULE_KEYS]
    states = []
    metas = []
    for mk in MODULE_KEYS:
        meta = state.get(f"{mk}_meta", {}) or {}
        s = meta.get("status", "pending")
        states.append(_step_state_for(s))
        metas.append(_meta_text(s, meta))
    md_step_progress(steps, states, metas)


# ============================================================
# Section C · 当前模块交互区
# ============================================================
def _render_m1_structured(output: dict) -> None:
    if not output:
        md_caption("（暂无数据）")
        return
    md_title("技术要点")
    for pt in output.get("tech_points", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-mono' style='color:var(--md-on-surface-variant)'>"
                f"原文：{pt.get('original','')}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='md-body md-mt-2'>🗣️ {pt.get('plain','')}</div>"
                f"<div class='md-body-sm md-mt-2'>🔍 {pt.get('analogy','')}</div>",
                unsafe_allow_html=True,
            )
            if pt.get("params"):
                md_kv("参数", pt["params"], mono=True)
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        md_title("关键能力")
        for c in output.get("capabilities", []) or []:
            md_body(f"· {c}")
    with col2:
        md_title("能力边界")
        for b in output.get("boundaries", []) or []:
            md_body(f"· {b}", small=True)


def _render_m2_structured(output: dict) -> None:
    if not output:
        md_caption("（暂无数据）")
        return
    with st.container(border=True):
        md_caption("核心技术IP 主张")
        st.markdown(
            f"<div class='md-title' style='color:var(--md-primary)'>"
            f"「{output.get('core_claim','')}」</div>",
            unsafe_allow_html=True,
        )
    md_title("技术卖点")
    for sp in output.get("selling_points", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-title'>💡 {sp.get('name','')}</div>"
                f"<div class='md-body md-mt-2'>{sp.get('user_description','')}</div>",
                unsafe_allow_html=True,
            )
            md_kv("用户需求", sp.get("user_need", "—"))
            md_kv("差异化", sp.get("differentiation", "—"))
            if sp.get("supporting_points"):
                md_kv("支撑点", "、".join(sp["supporting_points"]), mono=True)
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        md_title("目标用户假设")
        for u in output.get("target_user_hypothesis", []) or []:
            md_body(f"· {u}")
    with col2:
        md_title("过滤的技术点")
        for f in output.get("filtered_points", []) or []:
            md_body(f"· {f}", small=True)


def _render_m3_structured(output: dict) -> None:
    if not output:
        md_caption("（暂无数据）")
        return
    md_title("目标人群")
    for a in output.get("target_audiences", []) or []:
        with st.container(border=True):
            st.markdown(f"<div class='md-title'>👤 {a.get('segment','')}</div>", unsafe_allow_html=True)
            md_body(a.get("description", ""))
            md_kv("痛点", "、".join(a.get("pain_points", []) or []))
            md_kv("渠道", "、".join(a.get("preferred_channels", []) or []), mono=True)

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        md_title("核心渠道")
        for ch in output.get("core_channels", []) or []:
            md_body(f"· {ch}")
        md_title("节奏")
        for p in output.get("phases", []) or []:
            md_body(f"· {p}", small=True)
    with col2:
        md_title("KPI")
        for k in output.get("kpis", []) or []:
            md_body(f"· {k}", small=True)

    md_title("内容矩阵")
    for m in output.get("content_matrix", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-title'>📌 {m.get('phase','')}</div>", unsafe_allow_html=True
            )
            md_kv("主打卖点", "、".join(m.get("key_selling_points", []) or []))
            md_kv("内容形态", "、".join(m.get("content_types", []) or []))
            md_kv("切入角度", "、".join(m.get("sample_angles", []) or []))


def _render_m4_structured(output: dict) -> None:
    if not output:
        md_caption("（暂无数据）")
        return
    with st.container(border=True):
        md_caption("活动主题")
        st.markdown(
            f"<div class='md-title' style='color:var(--md-primary)'>"
            f"{output.get('campaign_theme','')}</div>"
            f"<div class='md-body-sm md-mt-2'>Slogan：{output.get('slogan','')}</div>",
            unsafe_allow_html=True,
        )

    md_title("视频脚本")
    for v in output.get("video_scripts", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-title'>🎬 {v.get('title','')}</div>"
                f"<div class='md-caption md-mt-2'>{v.get('duration_sec','—')} 秒</div>",
                unsafe_allow_html=True,
            )
            md_kv("Hook", v.get("hook", ""))
            md_body(v.get("body", ""), small=True)
            md_kv("CTA", v.get("cta", ""))

    md_title("长文章（节选）")
    with st.container(border=True):
        st.markdown(output.get("article", "—"))

    md_title("社交帖")
    for s in output.get("social_posts", []) or []:
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
    for p in output.get("posters", []) or []:
        with st.container(border=True):
            st.markdown(
                f"<div class='md-title'>{p.get('headline','')}</div>"
                f"<div class='md-body-sm md-mt-2'>{p.get('subline','')}</div>",
                unsafe_allow_html=True,
            )
            md_kv("视觉关键词", "、".join(p.get("visual_keywords", []) or []))

    if output.get("offline_event"):
        md_title("线下活动")
        ev = output["offline_event"]
        with st.container(border=True):
            st.markdown(f"<div class='md-title'>📅 {ev.get('theme','')}</div>", unsafe_allow_html=True)
            md_caption("流程")
            for f in ev.get("flow", []) or []:
                md_body(f"· {f}", small=True)
            md_kv("物料", "、".join(ev.get("materials", []) or []))
            md_kv("预算", ev.get("budget_framework", "—"))


STRUCTURED_RENDERERS = {
    "m1": _render_m1_structured,
    "m2": _render_m2_structured,
    "m3": _render_m3_structured,
    "m4": _render_m4_structured,
}


def _section_c_running(state: dict) -> None:
    cur = state.get("current_module", "m1")
    with st.container(border=True):
        with st.spinner(f"正在运行 {cur.upper()} · {MODULE_LABELS.get(cur,'')}…"):
            md_caption(
                "演示期：此处会替换为 `st.write_stream` 的实时流式输出（由 Track A 后端对接）"
            )
            st.progress(0.6, text="已生成约 60% 内容")


def _section_c_awaiting(state: dict) -> None:
    cur = state.get("current_module", "m2")
    meta = state.get(f"{cur}_meta", {}) or {}
    output = state.get(f"{cur}_output", {}) or {}

    with st.container(border=True):
        head_l, head_r = st.columns([3, 2], vertical_alignment="center")
        with head_l:
            st.markdown(
                f"<div class='md-title'>{MODULE_EMOJI[cur]} {cur.upper()} · "
                f"{MODULE_LABELS[cur]}</div>"
                f"<div class='md-mt-2'>{md_chip('awaiting')}</div>",
                unsafe_allow_html=True,
            )
        with head_r:
            md_kv("用时", _meta_text("completed", meta) or "—", mono=True)
            tok_in = meta.get("tokens_in", 0)
            tok_out = meta.get("tokens_out", 0)
            md_kv("Tokens", f"{tok_in} in · {tok_out} out", mono=True)
            md_kv("模型", meta.get("model", "—"), mono=True)

    tab_struct, tab_md, tab_json = st.tabs(["📊 结构化视图", "📝 Markdown", "🔢 原始 JSON"])

    with tab_struct:
        renderer = STRUCTURED_RENDERERS.get(cur)
        if renderer:
            renderer(output)
        else:
            md_caption("该模块暂无结构化渲染器")

    with tab_md:
        st.markdown(
            f"```json\n{json.dumps(output, ensure_ascii=False, indent=2)}\n```"
        )

    with tab_json:
        st.json(output, expanded=True)

    with st.expander("✎ 编辑后提交", expanded=False):
        edited = st.text_area(
            "直接修改下面的 JSON，然后点击 [✎ 修改后通过]",
            value=json.dumps(output, ensure_ascii=False, indent=2),
            height=260,
            key=f"ws_edit_{cur}",
        )
        st.caption("保存时会校验 JSON 格式；字段结构需与 state.py 的 TypedDict 一致")
        _ = edited  # 占位：真正提交在 [✎ 修改后通过] 按钮里读取 session state

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4, gap="small")
    is_real_task = bool(st.session_state.get("_runtime_thread_id"))

    def _do_continue(action: str, edited: dict | None = None) -> None:
        if not is_real_task:
            snackbar("调试模式:仅前端 mock,不会真正推进", icon="🛠️")
            return
        try:
            with st.spinner("处理中…"):
                runtime.continue_task(action, edited_output=edited)  # type: ignore[arg-type]
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"继续执行失败：{e}")

    with col1:
        if st.button("✓ 通过", type="primary", use_container_width=True, key="ws_approve"):
            _do_continue("approve")
    with col2:
        if st.button(
            "✎ 修改后通过",
            type="secondary",
            use_container_width=True,
            key="ws_edit_approve",
        ):
            txt = st.session_state.get(f"ws_edit_{cur}", "")
            try:
                parsed = json.loads(txt)
                _do_continue("edit", parsed)
            except json.JSONDecodeError as e:
                st.error(f"JSON 格式错误：{e}")
    with col3:
        if st.button("↻ 重跑本模块", type="secondary", use_container_width=True, key="ws_rerun"):
            _do_continue("rerun")
    with col4:
        if st.button("⏸ 暂停", type="tertiary", use_container_width=True, key="ws_pause"):
            snackbar("任务已保留当前进度,可稍后从历史记录继续", icon="⏸")


def _section_c_completed(state: dict) -> None:
    with st.container(border=True):
        st.markdown(
            "<div style='text-align:center;padding:16px 0'>"
            "<div style='font-size:40px'>🎉</div>"
            "<div class='md-title md-mt-2'>任务已完成</div>"
            "<div class='md-caption md-mt-2'>4 个模块全部产出完毕，可前往结果详情页浏览与导出</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("📄 前往结果详情", type="primary", use_container_width=True, key="ws_go_result"):
                st.session_state["viewing_task_id"] = state.get("task_id", "")
                st.switch_page("pages/2_result.py")
        with c2:
            if st.button("🔄 再来一条", type="secondary", use_container_width=True, key="ws_new_again"):
                st.session_state["current_state"] = deepcopy(sample_state_idle())
                st.session_state["_scene"] = "idle"
                st.rerun()


# ============================================================
# Section D · 已完成模块历史
# ============================================================
def _section_d(state: dict) -> None:
    completed_modules = [
        mk
        for mk in MODULE_KEYS
        if (state.get(f"{mk}_meta", {}) or {}).get("status") in ("completed", "approved")
    ]
    if not completed_modules:
        return
    with st.expander(f"📂 已完成模块（{len(completed_modules)}）", expanded=False):
        for mk in completed_modules:
            meta = state.get(f"{mk}_meta", {})
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(
                    f"**{MODULE_EMOJI[mk]} {mk.upper()} · {MODULE_LABELS[mk]}**",
                    unsafe_allow_html=False,
                )
            with c2:
                md_kv("用时", format_duration(meta.get("duration_ms", 0)), mono=True)
            with c3:
                if st.button(
                    "展开查看",
                    key=f"ws_view_{mk}",
                    type="tertiary",
                    use_container_width=True,
                ):
                    st.session_state["viewing_task_id"] = state.get("task_id", "")
                    st.session_state["_result_active_tab"] = mk
                    st.switch_page("pages/2_result.py")


# ============================================================
# Page entry
# ============================================================
def render_workspace() -> None:
    page_header("新建 & 运行")

    # 从历史页点"继续"带过来的 task_id:若没加载过就从磁盘读
    pending_view = st.session_state.get("viewing_task_id")
    if pending_view and (
        not st.session_state.get("current_state")
        or st.session_state["current_state"].get("task_id") != pending_view
    ):
        try:
            st.session_state["current_state"] = load_task(pending_view)
            st.session_state["_scene"] = "awaiting_review"
        except FileNotFoundError:
            st.warning(f"未找到任务 `{pending_view}`,将进入新建流程")
        finally:
            st.session_state.pop("viewing_task_id", None)

    if "current_state" not in st.session_state:
        st.session_state["current_state"] = deepcopy(sample_state_idle())
        st.session_state["_scene"] = "idle"

    state = st.session_state["current_state"]
    status = state.get("overall_status", "idle")

    # sidebar
    task_name = state.get("task_name") if status in ("running", "awaiting_review") else None
    stage = None
    if task_name:
        cur = state.get("current_module", "m1").upper()
        stage = f"{cur} · {'待审核' if status == 'awaiting_review' else '运行中'}"
    render_sidebar(current="workspace", task_name=task_name, stage=stage)
    _scene_switcher_sidebar()

    # mode banner
    mode_banner(state.get("mode", "human_review") if state.get("mode") in ("auto", "human_review") else "human_review")

    models = load_enabled_models()
    if not models:
        st.error("⚠️ 模型注册表为空。请前往 [⚙️ 设置] 配置至少一个模型。")

    # Section A
    if status == "idle":
        _section_a(models)
    else:
        _section_a_summary(state)

    # Section B
    if status != "idle":
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        _section_b(state)

    # Section C
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if status == "running":
        _section_c_running(state)
    elif status == "awaiting_review":
        _section_c_awaiting(state)
    elif status == "completed":
        _section_c_completed(state)

    # Section D
    if status != "idle":
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        _section_d(state)


render_workspace()
