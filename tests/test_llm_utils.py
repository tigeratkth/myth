"""tests/test_llm_utils.py

覆盖 `src/llm.py` 的**纯函数**（不触发真实 LLM 调用）：
  - load_config：config.yaml 读取与默认值
  - list_models：字段完整性、enabled 过滤
  - load_prompt：读取 prompts/*.md
  - render_prompt：变量替换 + dict/list 自动 JSON
  - _extract_json：裸 JSON / markdown 围栏 / 前后缀文本 / 非法输入
"""
from __future__ import annotations

import json

import pytest

from src.llm import (
    _extract_json,
    list_models,
    load_config,
    load_prompt,
    render_prompt,
)


# ============================================================
# load_config
# ============================================================
class TestLoadConfig:
    def test_returns_dict_with_core_sections(self):
        cfg = load_config()
        assert "models" in cfg
        assert "defaults" in cfg
        assert "runtime" in cfg
        assert isinstance(cfg["models"], list)

    def test_models_have_required_fields(self):
        cfg = load_config()
        assert len(cfg["models"]) > 0
        for m in cfg["models"]:
            assert "id" in m
            assert "provider" in m

    def test_missing_config_file_returns_empty(self, tmp_path):
        """传入一个不存在的路径，应返回空配置而不抛错。"""
        cfg = load_config(tmp_path / "no_such.yaml")
        assert cfg == {"models": [], "defaults": {}, "runtime": {}}


# ============================================================
# list_models
# ============================================================
class TestListModels:
    def test_only_enabled_by_default(self):
        models = list_models()
        for m in models:
            assert m["enabled"] is True

    def test_include_disabled_when_requested(self):
        all_models = list_models(only_enabled=False)
        enabled_only = list_models(only_enabled=True)
        assert len(all_models) >= len(enabled_only)

    def test_model_entry_schema(self):
        models = list_models()
        assert models, "config.yaml 中应至少有一个启用的模型"
        m = models[0]
        for key in ("id", "display_name", "provider", "max_tokens", "enabled", "env_key", "env_configured"):
            assert key in m


# ============================================================
# load_prompt
# ============================================================
class TestLoadPrompt:
    @pytest.mark.parametrize("name", ["translator", "ip_builder", "strategist", "marketer"])
    def test_all_four_prompts_exist(self, name):
        text = load_prompt(name)
        assert len(text) > 50, f"{name}.md 内容过短，检查是否为空"

    def test_prompts_contain_role_marker(self):
        """smoke_backend.py 和 tests/conftest.py 都依赖 M1/M2/M3/M4 角色标识做路由，
        若 prompts/*.md 不再包含这个标识，测试的 mock 路由会全部失效。这里做防御性断言。"""
        for name, marker in [
            ("translator", "M1"),
            ("ip_builder", "M2"),
            ("strategist", "M3"),
            ("marketer", "M4"),
        ]:
            text = load_prompt(name)
            assert marker in text, f"prompts/{name}.md 中找不到角色标识 {marker}"

    def test_unknown_prompt_raises(self):
        with pytest.raises(FileNotFoundError):
            load_prompt("not_a_real_prompt")


# ============================================================
# render_prompt
# ============================================================
class TestRenderPrompt:
    def test_simple_string_substitution(self):
        out = render_prompt("你好 {{name}}！", {"name": "世界"})
        assert out == "你好 世界！"

    def test_missing_variable_is_left_as_is(self):
        """未提供的变量原样保留（当前实现行为）。"""
        out = render_prompt("hello {{a}} {{b}}", {"a": "x"})
        assert out == "hello x {{b}}"

    def test_dict_value_is_serialized_as_json(self):
        out = render_prompt("data = {{payload}}", {"payload": {"k": "v", "n": 1}})
        # 应是合法 JSON 子串
        body = out.replace("data = ", "")
        parsed = json.loads(body)
        assert parsed == {"k": "v", "n": 1}

    def test_list_value_is_serialized_as_json(self):
        out = render_prompt("items = {{xs}}", {"xs": ["a", "b", "c"]})
        body = out.replace("items = ", "")
        assert json.loads(body) == ["a", "b", "c"]

    def test_none_becomes_empty_string(self):
        out = render_prompt("v = [{{v}}]", {"v": None})
        assert out == "v = []"


# ============================================================
# _extract_json（重点：模型输出往往掺杂 Markdown 围栏 / 解释文字）
# ============================================================
class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}

    def test_json_with_markdown_code_fence_lower(self):
        raw = "```json\n{\"a\": 1}\n```"
        assert _extract_json(raw) == {"a": 1}

    def test_json_with_markdown_code_fence_upper(self):
        raw = "```JSON\n{\"a\": 2}\n```"
        assert _extract_json(raw) == {"a": 2}

    def test_json_with_bare_code_fence(self):
        raw = "```\n{\"a\": 3}\n```"
        assert _extract_json(raw) == {"a": 3}

    def test_json_with_preamble_and_trailing_text(self):
        """模型经常在 JSON 前后加"这是你要的 JSON："之类的话。"""
        raw = '这是你要的 JSON：{"a": 4, "b": [1, 2]} 以上就是全部内容。'
        assert _extract_json(raw) == {"a": 4, "b": [1, 2]}

    def test_nested_json_object(self):
        raw = '{"outer": {"inner": [1, 2, {"k": "v"}]}}'
        assert _extract_json(raw) == {"outer": {"inner": [1, 2, {"k": "v"}]}}

    def test_totally_invalid_input_raises(self):
        with pytest.raises(ValueError):
            _extract_json("this is plainly not json at all")

    def test_broken_json_inside_braces_raises(self):
        """首 { 到末 } 之间也不是合法 JSON → 应抛 ValueError 而不是静默返回 None。"""
        with pytest.raises(ValueError):
            _extract_json('{"a": 1, "b": }')
