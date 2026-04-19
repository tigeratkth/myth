"""Pytest 共享 fixtures

本文件为整个 `tests/` 目录提供通用的：
  1. 项目根目录识别与 sys.path 注入
  2. `test_materials/` 下汽车零部件素材的加载
  3. 真实 LLM 调用的拦截（monkeypatch `invoke_llm` → 按 Prompt 角色标识返回合法 mock 输出）
  4. 临时 outputs 目录（隔离真实 outputs/）
  5. WorkflowState 工厂
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ------------------------------------------------------------
# 路径与 sys.path
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MATERIALS_DIR = PROJECT_ROOT / "test_materials"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ------------------------------------------------------------
# 素材加载
# ------------------------------------------------------------
@pytest.fixture(scope="session")
def materials_dir() -> Path:
    assert MATERIALS_DIR.exists(), f"测试素材目录不存在：{MATERIALS_DIR}"
    return MATERIALS_DIR


@pytest.fixture(scope="session")
def material_texts(materials_dir: Path) -> dict[str, str]:
    """加载 test_materials/ 下所有 .md / .txt 成 {slug: text}。

    slug 取文件名去掉前缀数字与扩展名后的核心词，便于在测试里按语义引用。
    """
    mapping: dict[str, str] = {}
    for path in sorted(materials_dir.iterdir()):
        if path.suffix.lower() not in (".md", ".txt"):
            continue
        if path.name.lower() == "readme.md":
            continue
        stem = path.stem
        if "_" in stem and stem.split("_", 1)[0].isdigit():
            slug = stem.split("_", 1)[1]
        else:
            slug = stem
        mapping[slug] = path.read_text(encoding="utf-8")
    # 兜底断言：确保 5 份素材都被收录
    assert "carbon_ceramic_brake" in mapping
    assert "ctb_battery_body" in mapping
    assert "4d_imaging_radar" in mapping
    assert "air_suspension_cdc" in mapping
    assert "minimal_edge_case" in mapping
    return mapping


# ------------------------------------------------------------
# Mock LLM —— 不同 Prompt 角色返回不同的合法样例
# ------------------------------------------------------------
def _mock_m1_output(_: str) -> dict:
    return {
        "tech_points": [
            {
                "original": "碳纤维增强陶瓷基复合材料 / 7nm FinFET / CTB 结构 / 4D 毫米波 等关键术语",
                "plain": "用了非常硬核的技术，相比上一代有代际提升",
                "analogy": "就像从普通水管换成精密医用导管，性能档次跳一级",
                "params": "典型参数以原文为准",
            },
            {
                "original": "系统级集成与多模块协同",
                "plain": "这项技术不是单颗零件的升级，而是整套系统的重构",
                "analogy": "好比装修时不是单独换一件家电，而是重做了水电",
                "params": "-",
            },
        ],
        "capabilities": ["高性能", "高可靠性", "相比上一代有显著工程优势"],
        "boundaries": ["需要配套方案支持", "成本高于传统方案"],
    }


def _mock_m2_output(_: str) -> dict:
    return {
        "core_claim": "用更硬核的底层技术，把用户最在意的体验做到新一代水准",
        "selling_points": [
            {
                "name": "性能跃迁 · 不用再忍受将就",
                "user_description": "同样的操作，体验好一大截",
                "user_need": "老方案用得难受却又换不起",
                "supporting_points": ["高性能", "相比上一代有显著工程优势"],
                "differentiation": "同价位竞品仍在使用上一代方案",
            },
            {
                "name": "可靠耐用 · 陪你到车辆退役",
                "user_description": "买一次，用十年",
                "user_need": "担心高科技反而更易出毛病",
                "supporting_points": ["高可靠性"],
                "differentiation": "材料寿命对齐整车寿命",
            },
        ],
        "target_user_hypothesis": ["性能敏感型车主", "商用车队采购决策者"],
        "filtered_points": ["过于底层的化学 / 电磁细节 —— 用户不关心"],
    }


def _mock_m3_output(_: str) -> dict:
    return {
        "target_audiences": [
            {
                "segment": "性能车爱好者",
                "description": "25–40 岁男性，关注赛道日/改装",
                "pain_points": ["现有零部件在极限工况下易失效"],
                "preferred_channels": ["B 站", "懂车帝", "线下改装店"],
            }
        ],
        "core_channels": ["微信公众号", "知乎机构号", "B 站", "懂车帝"],
        "content_matrix": [
            {
                "phase": "awareness",
                "key_selling_points": ["性能跃迁 · 不用再忍受将就"],
                "content_types": ["科普长图文", "拆解短视频"],
                "sample_angles": ["一张图看懂老方案与新方案的差距"],
            },
            {
                "phase": "seeding",
                "key_selling_points": ["性能跃迁 · 不用再忍受将就", "可靠耐用 · 陪你到车辆退役"],
                "content_types": ["深度测评", "KOL 背书"],
                "sample_angles": ["连续赛道日 5 小时后的状态对比"],
            },
            {
                "phase": "conversion",
                "key_selling_points": ["可靠耐用 · 陪你到车辆退役"],
                "content_types": ["限时权益", "门店试驾"],
                "sample_angles": ["首批用户享延长质保"],
            },
        ],
        "phases": ["冷启动 2 周", "爬坡 4 周", "持续放量"],
        "kpis": ["冷启动期总曝光 100 万+", "种草期私域新增 5000", "转化期试驾转化率 8%"],
    }


def _mock_m4_output(_: str) -> dict:
    return {
        "campaign_theme": "懂车的人，都换了",
        "slogan": "硬核不硬凑，换就换整套",
        "video_scripts": [
            {
                "title": "30 秒看懂这项新技术",
                "duration_sec": 30,
                "hook": "你上次被刹车热衰退吓到是什么时候？",
                "body": "答案藏在一块新材料里……",
                "cta": "预约门店体验",
            }
        ],
        "article": "# 懂车的人，都换了\n\n正文示例……",
        "social_posts": [
            {
                "platform": "小红书",
                "title": "终于不怕连续过弯了",
                "body": "换上之后的真实体感分享……",
                "hashtags": ["#汽车升级", "#硬核技术"],
            }
        ],
        "posters": [
            {
                "headline": "懂车的人，都换了",
                "subline": "一次升级，全程安心",
                "visual_keywords": ["科技蓝渐变", "金属质感", "赛道元素"],
            }
        ],
        "offline_event": {
            "theme": "硬核日 · 技术开放体验",
            "flow": ["签到 & 技术讲解", "赛道日体验", "用户圆桌"],
            "materials": ["主题展台", "实物剖面", "体验券"],
            "budget_framework": "单场 15–25 万",
        },
    }


# Prompt 顶部角色标识 → mock 输出生成器
# 注意：必须使用"完整角色名"而不是裸的 M1/M2，因为下游 Prompt 会把上游模块的角色
# 引用作为变量注入（例如 M2 的 prompt 正文里写了"(M1 输出)"），若仅用 "M1" 作
# marker 会导致 M2 的 Prompt 同时命中 M1 与 M2，按顺序误路由到 M1。—— 这也是
# RETROSPECTIVE.md 已记录过的坑。
_ROLE_TO_SAMPLE: list[tuple[str, Any]] = [
    ("M1 技术翻译官", _mock_m1_output),
    ("M2 技术卖点包装师", _mock_m2_output),
    ("M3 推广策略规划师", _mock_m3_output),
    ("M4 营销内容策划师", _mock_m4_output),
]


def _route_by_prompt(prompt: str, raw_material_hint: str = "") -> dict:
    """按照 Prompt 顶部角色标识精确路由到对应 mock。

    规则：统计每个 marker 在 prompt 中出现的次数，选**出现最早**（且存在的）那个作为
    归属模块。这样即使下游 Prompt 把上游角色名作为 JSON 片段引用进来，也不会误路由。
    """
    earliest_pos = len(prompt) + 1
    chosen = None
    for marker, factory in _ROLE_TO_SAMPLE:
        pos = prompt.find(marker)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos
            chosen = factory
    if chosen is None:
        raise RuntimeError(
            f"Mock LLM 无法识别 Prompt 所属模块；前 200 字符：{prompt[:200]}"
        )
    return chosen(raw_material_hint or prompt)


@pytest.fixture
def fake_invoke_llm():
    """返回一个可作为 invoke_llm 替身的 callable。

    记录每次调用的 model 与 prompt，便于测试断言 LLM 被按序/按模型调用。
    """
    calls: list[dict[str, Any]] = []

    def _fake(model, prompt, *, system="", temperature=0.7, response_format="json", **kw):
        calls.append(
            {
                "model": model,
                "prompt": prompt,
                "system": system,
                "temperature": temperature,
                "response_format": response_format,
            }
        )
        content = _route_by_prompt(prompt)
        return {
            "content": content,
            "raw": json.dumps(content, ensure_ascii=False),
            "tokens_in": len(prompt) // 4,
            "tokens_out": 400,
            "model": model,
        }

    _fake.calls = calls  # type: ignore[attr-defined]
    return _fake


@pytest.fixture
def patch_llm(monkeypatch, fake_invoke_llm):
    """把 fake_invoke_llm 同时打到 src.llm 与 src.nodes._helpers 两个绑定名上。

    因为 _helpers.py 里用 `from ..llm import invoke_llm`，
    是把对象绑定到本模块命名空间，仅 patch src.llm 不够。
    """
    from src import llm as _llm_mod
    from src.nodes import _helpers as _helpers_mod

    monkeypatch.setattr(_llm_mod, "invoke_llm", fake_invoke_llm)
    monkeypatch.setattr(_helpers_mod, "invoke_llm", fake_invoke_llm)
    return fake_invoke_llm


# ------------------------------------------------------------
# 临时 outputs 目录
# ------------------------------------------------------------
@pytest.fixture
def tmp_outputs(tmp_path: Path) -> Path:
    """每个测试用例独占的 outputs 目录。"""
    out = tmp_path / "outputs"
    out.mkdir()
    return out


# ------------------------------------------------------------
# WorkflowState 工厂
# ------------------------------------------------------------
@pytest.fixture
def make_state():
    """返回一个 make_initial_state 的轻量包装，默认填好 4 个模块模型。"""
    from src.state import make_initial_state

    def _factory(raw_material: str, *, task_id: str = "test-task-001", task_name: str = "pytest 任务",
                 mode: str = "auto"):
        return make_initial_state(
            task_id=task_id,
            task_name=task_name,
            raw_material=raw_material,
            mode=mode,  # type: ignore[arg-type]
            module_models={
                "m1": "openai/gpt-4o-mini",
                "m2": "openai/gpt-4o-mini",
                "m3": "openai/gpt-4o-mini",
                "m4": "openai/gpt-4o-mini",
            },
        )

    return _factory
