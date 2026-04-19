"""
页面 5 · 模型与 API 设置（Settings）

三区块：API Key 管理 / 模型注册表 / 默认配置。
v1 所有保存都走 session_state + toast 提示；真实落盘（.env + config.yaml）
留待主 agent 在集成阶段接入。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.state import MODULE_KEYS, MODULE_LABELS
from src.ui.components import (
    page_header,
    mode_banner,
    md_headline,
    md_title,
    md_caption,
    md_chip,
    snackbar,
)
from src.ui.layout import render_sidebar
from src.config_utils import (
    env_status,
    read_env,
    save_env,
    update_defaults,
    update_models,
)
from src.llm import load_config, test_connection


PROVIDERS = [
    {
        "key": "openai",
        "name": "OpenAI",
        "icon": "🧠",
        "env_key": "OPENAI_API_KEY",
        "has_base_url": True,
        "base_url_env": "OPENAI_BASE_URL",
    },
    {
        "key": "anthropic",
        "name": "Anthropic",
        "icon": "🪶",
        "env_key": "ANTHROPIC_API_KEY",
        "has_base_url": False,
    },
    {
        "key": "deepseek",
        "name": "DeepSeek",
        "icon": "🐋",
        "env_key": "DEEPSEEK_API_KEY",
        "has_base_url": False,
    },
    {
        "key": "dashscope",
        "name": "通义千问 / DashScope",
        "icon": "🐉",
        "env_key": "DASHSCOPE_API_KEY",
        "has_base_url": False,
    },
    {
        "key": "volcengine",
        "name": "火山方舟（豆包）",
        "icon": "🌋",
        "env_key": "VOLCENGINE_API_KEY",
        "has_base_url": True,
        "base_url_env": "VOLCENGINE_API_BASE",
    },
]

MODE_LABELS_CN = {"auto": "全自动", "human_review": "人工审核"}


# ============================================================
# 工具
# ============================================================
def _load_config() -> dict:
    return load_config()


# ============================================================
# 区块 1 · API Key 管理
# ============================================================
def _first_model_of(models: list[dict], provider: str) -> str | None:
    for m in models:
        if m.get("provider") == provider and m.get("enabled", True):
            return m.get("id")
    return None


def _tail4(val: str) -> str:
    """取 Key 末 4 位（长度不足则全部），用于状态 chip 展示。"""
    if not val:
        return ""
    return val[-4:] if len(val) >= 4 else val


def _render_provider_row(p: dict, env: dict, models_cfg: list[dict]) -> None:
    """单家 Provider 的设置块：小标题 + API Key 行 + 可选 Base URL 行。"""
    env_key = p["env_key"]
    saved = env.get(env_key, "") or ""
    has_base = p.get("has_base_url", False)

    # —— 标题行：图标 + 名称 + 已配置 chip（右对齐）——
    chip_html = (
        md_chip("completed", f"已配置 · ****{_tail4(saved)}")
        if saved
        else md_chip("pending", "未配置")
    )
    st.markdown(
        f"<div style='display:flex;align-items:center;justify-content:space-between;"
        f"margin-top:4px;margin-bottom:8px'>"
        f"<div class='md-title'>{p['icon']} {p['name']}</div>"
        f"<div>{chip_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # —— 第一行：API Key 输入 + 保存/测试 按钮 ——
    input_state_key = f"settings_key_{p['key']}"
    c_input, c_btn = st.columns([6, 2], vertical_alignment="bottom")
    with c_input:
        st.text_input(
            f"{p['name']} API Key",
            type="password",
            placeholder=(
                "在此粘贴新 Key（留空保存则不修改已配置的 Key）"
                if saved
                else "粘贴你的 API Key，例如 sk-..."
            ),
            key=input_state_key,
            label_visibility="collapsed",
        )

        # —— 第二行（仅有 Base URL 的 Provider）——
        if has_base:
            base_env = p["base_url_env"]
            saved_base = env.get(base_env, "") or ""
            base_state_key = f"settings_baseurl_{p['key']}"
            # 首次渲染时回填已保存值，之后交给 session_state
            if base_state_key not in st.session_state:
                st.session_state[base_state_key] = saved_base
            st.text_input(
                f"{p['name']} Base URL（可选）",
                placeholder="留空使用默认值",
                key=base_state_key,
                help="仅需自定义代理或接入点时填写。",
            )

    with c_btn:
        col_save, col_test = st.columns(2, gap="small")
        with col_save:
            if st.button(
                "保存",
                key=f"settings_save_{p['key']}",
                type="primary",
                use_container_width=True,
            ):
                input_val = (st.session_state.get(input_state_key, "") or "").strip()
                updates: dict[str, str] = {}
                # 留空不覆盖已保存 Key，避免误清空
                if input_val:
                    updates[env_key] = input_val
                if has_base:
                    base_val = (
                        st.session_state.get(f"settings_baseurl_{p['key']}", "") or ""
                    ).strip()
                    updates[p["base_url_env"]] = base_val
                if not updates:
                    snackbar("没有需要保存的改动", icon="ℹ️")
                else:
                    save_env(updates)
                    # 保存后清空输入，避免明文长期留在页面
                    st.session_state[input_state_key] = ""
                    snackbar(f"{p['name']} 已保存到 .env", icon="💾")
                    st.rerun()
        with col_test:
            if st.button(
                "测试",
                key=f"settings_test_{p['key']}",
                type="secondary",
                use_container_width=True,
            ):
                import os

                # 优先用当前输入，否则用已保存的
                input_val = (
                    st.session_state.get(input_state_key, "") or ""
                ).strip() or saved
                if not input_val:
                    snackbar(f"{p['name']} Key 为空，请先填写或保存", icon="⚠️")
                else:
                    orig = os.environ.get(env_key)
                    os.environ[env_key] = input_val
                    try:
                        model_id = _first_model_of(models_cfg, p["key"])
                        if not model_id:
                            snackbar(
                                f"{p['name']} 无启用模型，请在下方模型注册表开启",
                                icon="⚠️",
                            )
                        else:
                            ok, msg = test_connection(model_id)
                            snackbar(
                                f"{p['name']} {'✅' if ok else '❌'} {msg[:120]}",
                                icon="🟢" if ok else "🔴",
                            )
                    finally:
                        if orig is None:
                            os.environ.pop(env_key, None)
                        else:
                            os.environ[env_key] = orig


def _block_api_keys(cfg: dict) -> None:
    env = read_env()
    models_cfg = cfg.get("models", []) or []

    with st.container(border=True):
        md_title("🔑 API Key 管理")
        md_caption(
            "每家 Provider 独立一组；Key 保存到本地 `.env`，不会上传到任何服务器。"
            "留空保存 = 不修改已配置的 Key。"
        )

        for i, p in enumerate(PROVIDERS):
            if i > 0:
                st.markdown(
                    "<hr style='margin:18px 0 4px;border:none;"
                    "border-top:1px solid var(--md-outline-variant)'/>",
                    unsafe_allow_html=True,
                )
            _render_provider_row(p, env, models_cfg)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.info("🔒 Key 仅保存在本地 .env 文件，不会上传任何服务器")


# ============================================================
# 区块 2 · 模型注册表
# ============================================================
def _block_models_registry(cfg: dict) -> None:
    with st.container(border=True):
        md_title("🧠 模型注册表")
        md_caption(
            "LiteLLM 命名：`<provider>/<model_id>`；仅启用的模型会出现在工作台下拉里。"
        )

        models = cfg.get("models", []) or []
        df = pd.DataFrame(models or [])
        if df.empty:
            df = pd.DataFrame(columns=["enabled", "display_name", "id", "provider", "max_tokens"])
        else:
            cols_order = [c for c in ["enabled", "display_name", "id", "provider", "max_tokens"] if c in df.columns]
            df = df[cols_order]

        edited = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "enabled": st.column_config.CheckboxColumn("启用"),
                "display_name": st.column_config.TextColumn("显示名"),
                "id": st.column_config.TextColumn("Model ID"),
                "provider": st.column_config.SelectboxColumn(
                    "Provider",
                    options=["openai", "anthropic", "deepseek", "dashscope", "volcengine", "custom"],
                ),
                "max_tokens": st.column_config.NumberColumn("Max Tokens", min_value=512, step=1024),
            },
            hide_index=True,
            key="settings_models_editor",
        )

        c1, c2 = st.columns([1, 5])
        with c1:
            if st.button("+ 添加模型", type="tertiary", use_container_width=True, key="settings_add_model"):
                snackbar("请直接在表格底部追加一行（num_rows='dynamic'）", icon="ℹ️")

        st.session_state["_settings_models"] = edited.to_dict(orient="records")


# ============================================================
# 区块 3 · 默认配置
# ============================================================
def _block_defaults(cfg: dict) -> None:
    with st.container(border=True):
        md_title("⚙️ 默认配置")
        md_caption("工作台 / 首页会读取这里的默认值作为初始选择。")

        defaults = cfg.get("defaults", {}) or {}
        models_cfg = cfg.get("models", []) or []
        enabled_ids = [m["id"] for m in models_cfg if m.get("enabled")]
        if not enabled_ids:
            enabled_ids = [m.get("id", "") for m in models_cfg] or ["openai/gpt-4o"]

        col_mode, col_temp = st.columns(2)
        with col_mode:
            cur_mode = defaults.get("mode", "human_review")
            st.radio(
                "默认运行模式",
                options=["human_review", "auto"],
                index=0 if cur_mode == "human_review" else 1,
                format_func=lambda v: MODE_LABELS_CN[v],
                horizontal=True,
                key="settings_default_mode",
            )
        with col_temp:
            st.slider(
                "默认温度 temperature",
                min_value=0.0,
                max_value=1.5,
                value=float(defaults.get("temperature", 0.7)),
                step=0.1,
                key="settings_temperature",
            )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        md_caption("各模块默认模型")

        mm = defaults.get("module_models", {}) or {}
        mm_map_key = {
            "m1": "m1_translator",
            "m2": "m2_ip_builder",
            "m3": "m3_strategist",
            "m4": "m4_marketer",
        }
        cols = st.columns(4, gap="small")
        for i, mk in enumerate(MODULE_KEYS):
            with cols[i]:
                cur = mm.get(mm_map_key[mk], enabled_ids[0])
                idx = enabled_ids.index(cur) if cur in enabled_ids else 0
                st.selectbox(
                    f"{mk.upper()} · {MODULE_LABELS[mk]}",
                    options=enabled_ids,
                    index=idx,
                    key=f"settings_default_model_{mk}",
                )

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        b1, b2, _ = st.columns([1.2, 1.2, 4])
        with b1:
            if st.button("💾 保存设置", type="primary", use_container_width=True, key="settings_save"):
                try:
                    module_models_by_code = {
                        mm_map_key[mk]: st.session_state[f"settings_default_model_{mk}"]
                        for mk in MODULE_KEYS
                    }
                    update_defaults(
                        mode=st.session_state["settings_default_mode"],
                        temperature=st.session_state["settings_temperature"],
                        module_models=module_models_by_code,
                    )
                    edited_models = st.session_state.get("_settings_models")
                    if edited_models is not None:
                        cleaned = [
                            {
                                "id": m.get("id", ""),
                                "display_name": m.get("display_name", m.get("id", "")),
                                "provider": m.get("provider", ""),
                                "max_tokens": int(m.get("max_tokens", 4096) or 4096),
                                "enabled": bool(m.get("enabled", True)),
                            }
                            for m in edited_models
                            if m.get("id")
                        ]
                        update_models(cleaned)
                    snackbar("已保存到 config.yaml", icon="💾")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"保存失败：{e}")
        with b2:
            if st.button("⟲ 重置未保存", type="secondary", use_container_width=True, key="settings_reset"):
                for k in list(st.session_state.keys()):
                    if isinstance(k, str) and k.startswith("settings_"):
                        st.session_state.pop(k, None)
                snackbar("已清空未保存的表单值", icon="⟲")
                st.rerun()


# ============================================================
# Page entry
# ============================================================
def render_settings() -> None:
    page_header("模型与设置")

    render_sidebar(current="settings")

    env = env_status()
    mode_banner(env.get("default_mode", "human_review"))

    md_headline("模型与 API 设置")
    md_caption("在这里管理 Key、模型注册表与默认运行参数。")

    cfg = _load_config()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    _block_api_keys(cfg)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    _block_models_registry(cfg)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    _block_defaults(cfg)


render_settings()
