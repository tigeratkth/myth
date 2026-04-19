"""tests/test_end_to_end.py

**端到端集成测试** — 把 `test_materials/` 下的真实汽车零部件技术资料，作为原始输入灌入
完整流水线（LLM 调用被 mock），断言：

  1. 四个模块输出的**结构完整性**（字段存在、类型正确）
  2. 每个模块都消耗了**非空 Prompt**（即素材被正确下发）
  3. 落盘后 `outputs/{task_id}/` 目录结构完整，报告可被回读
  4. 极短素材（edge case）也能跑完流水线不崩溃

这些测试不依赖任何真实 LLM API Key，可在 CI 中稳定运行。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.graph import build_graph
from src.io_utils import list_tasks, load_task, read_material, save_task
from src.state import make_initial_state


# 四份"有分量"的素材 + 1 份极短素材 —— 用 parametrize 展开为独立 case
REAL_MATERIALS = [
    ("carbon_ceramic_brake", "碳陶瓷刹车盘"),
    ("ctb_battery_body", "CTB 电池车身一体化"),
    ("4d_imaging_radar", "4D 毫米波成像雷达"),
    ("air_suspension_cdc", "空气悬架 + CDC"),
]


# ============================================================
# 一、素材加载
# ============================================================
class TestMaterialsLoading:
    """确保 test_materials/ 本身是健康的——这是所有端到端测试的前置条件。"""

    @pytest.mark.parametrize("slug,label", REAL_MATERIALS)
    def test_each_material_non_trivial(self, material_texts, slug, label):
        text = material_texts[slug]
        assert text.strip(), f"{label} 素材为空"
        # 真实技术资料应该都在 500 字以上
        assert len(text) >= 500, f"{label} 素材过短，可能未正确保存（当前 {len(text)} 字）"

    def test_minimal_edge_case_is_short(self, material_texts):
        text = material_texts["minimal_edge_case"]
        assert 0 < len(text) < 200

    def test_read_material_handles_all_files(self, materials_dir: Path):
        """io_utils.read_material 应能处理 test_materials/ 下所有 .md + .txt。"""
        for path in materials_dir.iterdir():
            if path.suffix.lower() not in (".md", ".txt"):
                continue
            if path.name.lower() == "readme.md":
                continue
            text = read_material(path)
            assert text.strip(), f"{path.name} 读取后为空"


# ============================================================
# 二、全流程：每份素材跑一次
# ============================================================
@pytest.mark.parametrize("slug,label", REAL_MATERIALS)
def test_full_pipeline_with_real_material(
    patch_llm, make_state, tmp_outputs, material_texts, slug, label
):
    """端到端：真实材料 → 4 模块 → 落盘 → 回读。"""
    raw = material_texts[slug]
    state = make_state(raw, task_id=f"e2e-{slug}", task_name=f"端到端 · {label}")

    # 1. 跑完整流水线
    graph = build_graph("auto")
    final_state = graph.invoke(state)

    # ---- 断言：四个模块 output 结构完整 ----
    m1 = final_state.get("m1_output") or {}
    assert isinstance(m1.get("tech_points"), list) and len(m1["tech_points"]) >= 1
    assert isinstance(m1.get("capabilities"), list)
    assert isinstance(m1.get("boundaries"), list)
    first_tp = m1["tech_points"][0]
    assert all(k in first_tp for k in ("original", "plain", "analogy", "params"))

    m2 = final_state.get("m2_output") or {}
    assert m2.get("core_claim")
    assert isinstance(m2.get("selling_points"), list) and len(m2["selling_points"]) >= 1
    first_sp = m2["selling_points"][0]
    assert all(
        k in first_sp
        for k in ("name", "user_description", "user_need", "supporting_points", "differentiation")
    )

    m3 = final_state.get("m3_output") or {}
    assert isinstance(m3.get("target_audiences"), list) and len(m3["target_audiences"]) >= 1
    assert m3.get("content_matrix")
    phases = {cm["phase"] for cm in m3["content_matrix"]}
    # 三阶段内容矩阵至少覆盖 awareness（认知）
    assert "awareness" in phases

    m4 = final_state.get("m4_output") or {}
    assert m4.get("campaign_theme")
    assert m4.get("slogan")
    assert isinstance(m4.get("video_scripts"), list) and len(m4["video_scripts"]) >= 1
    assert m4.get("article")
    assert isinstance(m4.get("posters"), list)
    assert isinstance(m4.get("offline_event"), dict)

    # ---- 断言：LLM 被正确调用 4 次，每次 Prompt 都包含原始材料片段 ----
    assert len(patch_llm.calls) == 4
    # 至少 m1 的 Prompt 应该引用了 raw_material（模板通过 {{raw_material}} 变量注入）
    m1_prompt = patch_llm.calls[0]["prompt"]
    # 从原始材料里挑一段前 20 字作为 substring
    head = raw.strip().split("\n", 1)[0][:20]
    if head:
        assert head in m1_prompt, "M1 Prompt 中未找到原始材料开头，变量渲染可能失败"

    # ---- 断言：全局状态正确 ----
    assert final_state["overall_status"] == "completed"

    # 2. 落盘
    out_dir = save_task(final_state, outputs_dir=tmp_outputs)
    out_path = Path(out_dir)
    for name in ("meta.json", "state.json", "report.md"):
        assert (out_path / name).exists()

    # 3. 回读
    reloaded = load_task(f"e2e-{slug}", outputs_dir=tmp_outputs)
    assert reloaded["task_id"] == f"e2e-{slug}"
    assert reloaded["m2_output"]["core_claim"] == final_state["m2_output"]["core_claim"]

    # 4. list_tasks 能找到它
    rows = list_tasks(outputs_dir=tmp_outputs)
    assert any(r["task_id"] == f"e2e-{slug}" for r in rows)


# ============================================================
# 三、极短素材：边界用例
# ============================================================
def test_pipeline_survives_minimal_material(patch_llm, make_state, material_texts, tmp_outputs):
    """极短素材也不应导致流水线崩溃或字段缺失。

    注：真实 LLM 在材料不足时可能产出空泛内容，这里用 mock 关注的是**代码路径稳定性**。
    """
    raw = material_texts["minimal_edge_case"]
    state = make_state(raw, task_id="e2e-minimal", task_name="端到端 · 极短边界")

    graph = build_graph("auto")
    final_state = graph.invoke(state)

    assert final_state["overall_status"] == "completed"
    for key in ("m1", "m2", "m3", "m4"):
        meta = final_state.get(f"{key}_meta") or {}
        assert meta.get("status") == "completed"

    out_dir = save_task(final_state, outputs_dir=tmp_outputs)
    assert (Path(out_dir) / "report.md").exists()


# ============================================================
# 四、同一 outputs 目录下并列多个任务
# ============================================================
def test_multiple_tasks_isolated_in_outputs(patch_llm, make_state, material_texts, tmp_outputs):
    """依次跑 2 份素材，两个任务目录互不污染，list_tasks 返回两条。"""
    for slug in ("carbon_ceramic_brake", "4d_imaging_radar"):
        raw = material_texts[slug]
        state = make_state(raw, task_id=f"multi-{slug}")
        final_state = build_graph("auto").invoke(state)
        save_task(final_state, outputs_dir=tmp_outputs)

    rows = list_tasks(outputs_dir=tmp_outputs)
    ids = {r["task_id"] for r in rows}
    assert {"multi-carbon_ceramic_brake", "multi-4d_imaging_radar"} <= ids
