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
def _mask(val: str) -> str:
    """把已保存的 Key 做脱敏展示,只保留后 4 位。"""
    if not val:
        return ""
    if len(val) <= 6:
        return "*" * len(val)
    return f"{'*' * (len(val) - 4)}{val[-4:]}"


def _first_model_of(models: list[dict], provider: str) -> str | None:
    for m in models:
        if m.get("provider") == provider and m.get("enabled", True):
            return m.get("id")
    return None


def _block_api_keys(cfg: dict) -> None:
    env = read_env()
    models_cfg = cfg.get("models", []) or []

    with st.container(border=True):
        md_title("🔑 API Key 管理")
        md_caption("每家 Provider 一行;Key 保存到本地 `.env`,不会上传到任何服务器。")

        for p in PROVIDERS:
            env_key = p["env_key"]
            saved = env.get(env_key, "") or ""
            c_name, c_input, c_btn = st.columns([2, 5, 2], vertical_alignment="bottom")
            with c_name:
                badge = " · 🟢 已配置" if saved else ""
                st.markdown(
                    f"<div class='md-body' style='padding-top:12px'>"
                    f"{p['icon']} <b>{p['name']}</b>"
                    f"<span class='md-caption'>{badge}</span></div>",
                    unsafe_allow_html=True,
                )
            with c_input:
                default_key = st.session_state.get(f"settings_key_{p['key']}")
                st.text_input(
                    f"{p['name']} API Key",
                    type="password",
                    placeholder=_mask(saved) if saved else "sk-...",
                    key=f"settings_key_{p['key']}",
                    label_visibility="collapsed",
                    value=default_key if default_key is not None else "",
                )
                if p.get("has_base_url"):
                    base_key = p["base_url_env"]
                    saved_base = env.get(base_key, "") or ""
                    st.text_input(
                        f"{p['name']} Base URL(可选)",
                        value=saved_base,
                        placeholder="https://api.openai.com/v1",
                        key=f"settings_baseurl_{p['key']}",
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
                        input_val = st.session_state.get(f"settings_key_{p['key']}", "")
                        updates = {env_key: input_val}
                        if p.get("has_base_url"):
                            updates[p["base_url_env"]] = st.session_state.get(
                                f"settings_baseurl_{p['key']}", ""
                            )
                        save_env(updates)
                        snackbar(f"{p['name']} 已保存到 .env", icon="💾")
                        st.rerun()
                with col_test:
                    if st.button(
                        "测试",
                        key=f"settings_test_{p['key']}",
                        type="secondary",
                        use_container_width=True,
                    ):
                        # 测试时临时把输入写到环境变量,再回滚
                        import os

                        input_val = st.session_state.get(f"settings_key_{p['key']}", "") or saved
                        if not input_val:
                            snackbar(f"{p['name']} Key 为空,请先填写或保存", icon="⚠️")
                        else:
                            orig = os.environ.get(env_key)
                            os.environ[env_key] = input_val
                            try:
                                model_id = _first_model_of(models_cfg, p["key"])
                                if not model_id:
                                    snackbar(
                                        f"{p['name']} 无启用模型,请在下方模型注册表开启",
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

        st.info("🔒 Key 仅保存在本地 .env 文件,不会上传任何服务器")


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
                    options=["openai", "anthropic", "deepseek", "dashscope", "custom"],
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
