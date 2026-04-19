"""tests/test_io_utils.py

覆盖 `src/io_utils.py`：
  - read_material：txt / md / 路径 / 字节流 / 未知后缀
  - save_task + load_task + list_tasks + delete_task 闭环
  - render_module_markdown 基本结构
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from src.io_utils import (
    delete_task,
    list_tasks,
    load_task,
    read_material,
    render_module_markdown,
    save_task,
)


# ============================================================
# 一、read_material
# ============================================================
class TestReadMaterial:
    def test_read_md_from_path(self, materials_dir: Path):
        path = materials_dir / "01_carbon_ceramic_brake.md"
        text = read_material(path)
        assert "碳陶瓷" in text or "碳纤维" in text
        assert len(text) > 500

    def test_read_txt_short(self, materials_dir: Path):
        path = materials_dir / "05_minimal_edge_case.txt"
        text = read_material(path)
        assert "硅胶" in text
        assert len(text) < 200

    def test_read_from_binary_stream_with_filename(self, materials_dir: Path):
        """Streamlit UploadedFile 场景：传字节流 + filename。"""
        raw = (materials_dir / "02_ctb_battery_body.md").read_bytes()
        stream = io.BytesIO(raw)
        text = read_material(stream, filename="ctb.md")
        assert "CTB" in text
        # 读完后应 seek 回 0，允许上层再次读
        assert stream.tell() == 0

    def test_read_binary_stream_without_filename_fails(self):
        stream = io.BytesIO(b"hello")
        with pytest.raises(ValueError, match="filename"):
            read_material(stream)

    def test_read_unknown_extension_fails(self, tmp_path: Path):
        f = tmp_path / "foo.xls"
        f.write_bytes(b"not a real xls")
        with pytest.raises(ValueError, match="不支持的文件类型"):
            read_material(f)

    def test_read_gbk_encoded_txt(self, tmp_path: Path):
        """验证编码兜底：GBK 文本能被正确 decode。"""
        f = tmp_path / "gbk.txt"
        f.write_bytes("中文测试内容".encode("gbk"))
        text = read_material(f)
        assert "中文测试内容" in text


# ============================================================
# 二、save / load / list / delete 闭环
# ============================================================
def _minimal_completed_state(task_id: str = "task-io-001") -> dict:
    """构造一个已跑完流水线的 state（不调用任何 LLM）。"""
    return {
        "task_id": task_id,
        "task_name": "IO 测试任务",
        "created_at": "2026-04-19T10:00:00",
        "raw_material": "原始材料示例",
        "source_type": "paste",
        "source_filename": "",
        "mode": "auto",
        "module_models": {
            "m1": "openai/gpt-4o-mini",
            "m2": "openai/gpt-4o-mini",
            "m3": "openai/gpt-4o-mini",
            "m4": "openai/gpt-4o-mini",
        },
        "temperature": 0.7,
        "m1_output": {
            "tech_points": [
                {"original": "o", "plain": "p", "analogy": "a", "params": "-"}
            ],
            "capabilities": ["cap1"],
            "boundaries": ["bd1"],
        },
        "m2_output": {
            "core_claim": "一句话主张",
            "selling_points": [
                {
                    "name": "点1",
                    "user_description": "描述",
                    "user_need": "需求",
                    "supporting_points": ["cap1"],
                    "differentiation": "差异",
                }
            ],
            "target_user_hypothesis": ["用户A"],
            "filtered_points": ["过细"],
        },
        "m3_output": {
            "target_audiences": [
                {
                    "segment": "seg",
                    "description": "desc",
                    "pain_points": ["pp"],
                    "preferred_channels": ["ch"],
                }
            ],
            "core_channels": ["ch"],
            "content_matrix": [
                {
                    "phase": "awareness",
                    "key_selling_points": ["点1"],
                    "content_types": ["图文"],
                    "sample_angles": ["角度"],
                }
            ],
            "phases": ["冷启动"],
            "kpis": ["KPI"],
        },
        "m4_output": {
            "campaign_theme": "主题",
            "slogan": "Slogan",
            "video_scripts": [
                {
                    "title": "v",
                    "duration_sec": 30,
                    "hook": "h",
                    "body": "b",
                    "cta": "c",
                }
            ],
            "article": "# 文章",
            "social_posts": [
                {"platform": "小红书", "title": "t", "body": "b", "hashtags": ["#a"]}
            ],
            "posters": [
                {"headline": "hl", "subline": "sl", "visual_keywords": ["k"]}
            ],
            "offline_event": {
                "theme": "ev",
                "flow": ["s1"],
                "materials": ["m"],
                "budget_framework": "2 万",
            },
        },
        "m1_meta": {"status": "completed", "model": "m", "duration_ms": 100, "tokens_in": 1, "tokens_out": 2, "finished_at": "2026-04-19T10:01:00"},
        "m2_meta": {"status": "completed", "model": "m", "duration_ms": 200, "tokens_in": 1, "tokens_out": 2, "finished_at": "2026-04-19T10:02:00"},
        "m3_meta": {"status": "completed", "model": "m", "duration_ms": 300, "tokens_in": 1, "tokens_out": 2, "finished_at": "2026-04-19T10:03:00"},
        "m4_meta": {"status": "completed", "model": "m", "duration_ms": 400, "tokens_in": 1, "tokens_out": 2, "finished_at": "2026-04-19T10:04:00"},
        "current_module": "m4",
        "overall_status": "completed",
        "logs": ["done"],
    }


class TestSaveLoadLifecycle:
    def test_save_creates_all_artifacts(self, tmp_outputs: Path):
        state = _minimal_completed_state()
        out_dir = save_task(state, outputs_dir=tmp_outputs)
        out_path = Path(out_dir)

        for name in ("meta.json", "state.json", "m1.md", "m2.md", "m3.md", "m4.md", "report.md"):
            f = out_path / name
            assert f.exists(), f"缺失产物：{name}"
            assert f.stat().st_size > 0

    def test_meta_json_structure(self, tmp_outputs: Path):
        state = _minimal_completed_state()
        save_task(state, outputs_dir=tmp_outputs)

        meta = json.loads((tmp_outputs / "task-io-001" / "meta.json").read_text("utf-8"))
        assert meta["task_id"] == "task-io-001"
        assert meta["status"] == "completed"
        assert meta["mode"] == "auto"
        # 总耗时 = 100 + 200 + 300 + 400 = 1000
        assert meta["duration_ms"] == 1000
        # 完成时间应来自 m4_meta.finished_at
        assert meta["completed_at"] == "2026-04-19T10:04:00"
        # 四个模块的 model 都应出现
        assert set(meta["models"].keys()) == {"m1", "m2", "m3", "m4"}

    def test_load_task_roundtrip(self, tmp_outputs: Path):
        state = _minimal_completed_state("task-io-roundtrip")
        save_task(state, outputs_dir=tmp_outputs)

        loaded = load_task("task-io-roundtrip", outputs_dir=tmp_outputs)
        assert loaded["task_id"] == "task-io-roundtrip"
        assert loaded["m2_output"]["core_claim"] == "一句话主张"
        assert loaded["m4_output"]["slogan"] == "Slogan"

    def test_load_task_not_found(self, tmp_outputs: Path):
        with pytest.raises(FileNotFoundError, match="任务不存在"):
            load_task("not-exists", outputs_dir=tmp_outputs)

    def test_list_tasks_sorts_by_created_at_desc(self, tmp_outputs: Path):
        s1 = _minimal_completed_state("task-a")
        s1["created_at"] = "2026-04-18T10:00:00"
        s2 = _minimal_completed_state("task-b")
        s2["created_at"] = "2026-04-19T10:00:00"
        s3 = _minimal_completed_state("task-c")
        s3["created_at"] = "2026-04-17T10:00:00"

        save_task(s1, outputs_dir=tmp_outputs)
        save_task(s2, outputs_dir=tmp_outputs)
        save_task(s3, outputs_dir=tmp_outputs)

        rows = list_tasks(outputs_dir=tmp_outputs)
        ids = [r["task_id"] for r in rows]
        assert ids == ["task-b", "task-a", "task-c"]

    def test_list_tasks_on_empty_dir(self, tmp_outputs: Path):
        assert list_tasks(outputs_dir=tmp_outputs) == []

    def test_list_tasks_skips_non_task_dirs(self, tmp_outputs: Path):
        """outputs 下若存在无 meta.json 的子目录（如用户误创建），应被忽略。"""
        (tmp_outputs / "random_dir").mkdir()
        save_task(_minimal_completed_state("task-valid"), outputs_dir=tmp_outputs)
        rows = list_tasks(outputs_dir=tmp_outputs)
        assert len(rows) == 1
        assert rows[0]["task_id"] == "task-valid"

    def test_delete_task_removes_dir(self, tmp_outputs: Path):
        save_task(_minimal_completed_state("to-delete"), outputs_dir=tmp_outputs)
        target = tmp_outputs / "to-delete"
        assert target.exists()

        delete_task("to-delete", outputs_dir=tmp_outputs)
        assert not target.exists()

    def test_delete_nonexistent_task_is_noop(self, tmp_outputs: Path):
        delete_task("never-existed", outputs_dir=tmp_outputs)


# ============================================================
# 三、Markdown 渲染
# ============================================================
class TestRenderModuleMarkdown:
    def test_m1_markdown_contains_tech_points(self, tmp_outputs: Path):
        state = _minimal_completed_state()
        md = render_module_markdown(state, "m1")
        assert "技术要点" in md
        assert "关键能力" in md
        assert "能力边界" in md
        assert "cap1" in md
        assert "bd1" in md

    def test_m2_markdown_contains_core_claim_and_selling_point(self):
        state = _minimal_completed_state()
        md = render_module_markdown(state, "m2")
        assert "一句话主张" in md
        assert "点1" in md
        assert "差异化" in md

    def test_m3_markdown_contains_phase_labels(self):
        state = _minimal_completed_state()
        md = render_module_markdown(state, "m3")
        # "awareness" → "认知"
        assert "认知" in md
        assert "seg" in md

    def test_m4_markdown_contains_slogan_and_poster(self):
        state = _minimal_completed_state()
        md = render_module_markdown(state, "m4")
        assert "Slogan" in md
        assert "hl" in md
        assert "小红书" in md

    def test_empty_output_renders_placeholder(self):
        state = _minimal_completed_state()
        state["m2_output"] = {}  # 模拟尚未执行到 m2
        md = render_module_markdown(state, "m2")
        assert "暂无输出" in md
