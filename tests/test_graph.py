"""tests/test_graph.py

覆盖 `src/graph.py` + 节点层：
  - build_graph("auto") / build_graph("human_review") 均能编译
  - 四个节点按 m1 → m2 → m3 → m4 顺序被调用
  - 每个节点写回正确的 output 字段 + meta.status = completed
  - 节点调用的模型取自 state.module_models
  - 异常时 meta.status = failed，overall_status = failed
"""
from __future__ import annotations

import pytest

from src.graph import build_auto_graph, build_graph, build_review_graph


# ============================================================
# 图编译
# ============================================================
class TestGraphCompile:
    def test_build_auto_graph_compiles(self):
        g = build_auto_graph()
        assert g is not None
        # 编译产物必须有 invoke 方法
        assert hasattr(g, "invoke")

    def test_build_review_graph_compiles(self):
        g = build_review_graph()
        assert g is not None
        assert hasattr(g, "invoke")

    def test_build_graph_dispatch(self):
        auto_g = build_graph("auto")
        review_g = build_graph("human_review")
        assert auto_g is not None
        assert review_g is not None
        # 两者应为不同实例
        assert auto_g is not review_g


# ============================================================
# 全自动模式端到端
# ============================================================
class TestAutoGraphRun:
    def test_four_modules_run_in_order(self, patch_llm, make_state):
        graph = build_graph("auto")
        state = make_state("测试原始技术资料：示例芯片 + 示例电池。")

        final_state = graph.invoke(state)

        # 1. 四个模块 output 都应写入
        for key in ("m1", "m2", "m3", "m4"):
            assert final_state.get(f"{key}_output"), f"{key}_output 未写入"
            meta = final_state.get(f"{key}_meta") or {}
            assert meta.get("status") == "completed", f"{key}_meta.status 非 completed"
            assert meta.get("duration_ms") is not None
            assert meta.get("tokens_in", 0) > 0

        # 2. overall_status 应是 completed
        assert final_state["overall_status"] == "completed"

        # 3. LLM 应被恰好调用 4 次，按 M1..M4 顺序
        calls = patch_llm.calls
        assert len(calls) == 4

        # 用完整角色名匹配 + "最早出现位置优先"，避免下游 Prompt 引用上游角色导致误判
        # （M2 的 prompt 会提 "M1 输出"，短标识符 "M1" 会在多个 prompt 里都命中）
        full_markers = [
            ("M1 技术翻译官", "M1"),
            ("M2 技术卖点包装师", "M2"),
            ("M3 推广策略规划师", "M3"),
            ("M4 营销内容策划师", "M4"),
        ]
        detected = []
        for c in calls:
            earliest = len(c["prompt"]) + 1
            chosen = None
            for full, short in full_markers:
                p = c["prompt"].find(full)
                if p != -1 and p < earliest:
                    earliest = p
                    chosen = short
            detected.append(chosen)
        assert detected == ["M1", "M2", "M3", "M4"]

    def test_model_assignment_propagates_to_llm_call(self, patch_llm, make_state):
        graph = build_graph("auto")
        state = make_state("材料")
        # 给每个模块配不同的模型，验证 _pick_model 正确工作
        state["module_models"] = {
            "m1": "deepseek/deepseek-chat",
            "m2": "anthropic/claude-sonnet-4-5",
            "m3": "openai/gpt-4o",
            "m4": "openai/gpt-4o-mini",
        }

        graph.invoke(state)

        models_seen = [c["model"] for c in patch_llm.calls]
        assert models_seen == [
            "deepseek/deepseek-chat",
            "anthropic/claude-sonnet-4-5",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
        ]

    def test_logs_accumulate_across_nodes(self, patch_llm, make_state):
        graph = build_graph("auto")
        state = make_state("材料")
        final_state = graph.invoke(state)
        logs = final_state.get("logs") or []
        # 每个模块应至少产生"开始"+"完成"两条日志
        assert len(logs) >= 8
        assert any("[m1]" in ln for ln in logs)
        assert any("[m4]" in ln for ln in logs)


# ============================================================
# 节点失败路径
# ============================================================
class TestNodeFailure:
    def test_llm_exception_marks_meta_failed(self, monkeypatch, make_state):
        """模拟 LLM 调用失败，m1_meta.status 应为 failed，且 overall_status = failed，流水线应立即中止。"""
        from src import llm as _llm_mod
        from src.nodes import _helpers as _helpers_mod

        def _boom(*a, **kw):
            raise RuntimeError("API Key 无效")

        monkeypatch.setattr(_llm_mod, "invoke_llm", _boom)
        monkeypatch.setattr(_helpers_mod, "invoke_llm", _boom)

        graph = build_graph("auto")
        state = make_state("材料")

        # run_module 捕获异常后返回 failed，图继续流转但后续节点同样会 failed
        # 我们断言首个失败节点的元信息正确即可
        final_state = graph.invoke(state)

        m1_meta = final_state.get("m1_meta") or {}
        assert m1_meta.get("status") == "failed"
        assert "API Key 无效" in (m1_meta.get("error") or "")
        assert final_state.get("overall_status") == "failed"


# ============================================================
# 人工审核模式：第一次 invoke 后，应在 m1 完成后中断
# ============================================================
class TestReviewGraphInterrupt:
    def test_interrupts_after_m1(self, patch_llm, make_state):
        """LangGraph 的 interrupt_after 语义：第一次 invoke 会执行 m1 后暂停。
        断言：
          - m1_output 已写入
          - m2/m3/m4_output 尚未写入
          - LLM 只被调用了 1 次
        """
        graph = build_graph("human_review")
        state = make_state("材料")
        config = {"configurable": {"thread_id": "test-review-001"}}

        graph.invoke(state, config=config)

        snapshot = graph.get_state(config)
        values = snapshot.values

        assert values.get("m1_output"), "m1_output 应已写入"
        assert not values.get("m2_output"), "m2_output 不应在首次中断时写入"
        assert not values.get("m3_output")
        assert not values.get("m4_output")

        assert len(patch_llm.calls) == 1, "review 模式下首次 invoke 应只调用 1 次 LLM"

    def test_resume_continues_to_next_module(self, patch_llm, make_state):
        """中断后用 invoke(None, config) 继续，应推进到 m2 完成后再次中断。"""
        graph = build_graph("human_review")
        state = make_state("材料")
        config = {"configurable": {"thread_id": "test-review-002"}}

        graph.invoke(state, config=config)
        graph.invoke(None, config=config)

        values = graph.get_state(config).values
        assert values.get("m1_output")
        assert values.get("m2_output")
        assert not values.get("m3_output")
        assert len(patch_llm.calls) == 2
