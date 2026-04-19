"""后端冒烟测试

目标：在**不调用真实 LLM** 的前提下，验证：
  1. 四个 Prompt 模板存在且可加载
  2. 图构造与节点连接正确（auto 模式）
  3. 每个节点都能把 mock 输出写回 state
  4. 全流程跑完后可以落盘，outputs/{task_id}/ 目录结构正确
  5. list_tasks / load_task / delete_task 链路通

用法：
    python scripts/smoke_backend.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

# Windows 控制台默认可能是 cp1252，这里强制 stdout/stderr 用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 先 monkeypatch invoke_llm —— 必须在导入节点之前完成
from src import llm as _llm_mod  # noqa: E402

# 注意：src/ui/mocks.py 当前有一处 SyntaxError（user_need 字段内双引号未转义），
# 无法直接 import，因此这里内嵌一份精简样本供冒烟测试用。结构与 state.py 的
# TypedDict 对齐即可。
_M1_OUTPUT = {
    "tech_points": [
        {
            "original": "7nm FinFET 工艺",
            "plain": "用的是最新旗舰手机的制造工艺",
            "analogy": "就像从普通水管换成精密医用导管",
            "params": "7nm / FinFET",
        }
    ],
    "capabilities": ["高能效比"],
    "boundaries": ["需配 LPDDR5X 内存"],
}

_M2_OUTPUT = {
    "core_claim": "用旗舰工艺 + AI 专芯,让设备既省电又聪明。",
    "selling_points": [
        {
            "name": "旗舰级工艺 · 省电不烫手",
            "user_description": "跟旗舰手机同级工艺,续航更长",
            "user_need": "耗电快 / 发烫",
            "supporting_points": ["7nm FinFET"],
            "differentiation": "同价位多为 12nm",
        }
    ],
    "target_user_hypothesis": ["智能家居品牌产品经理"],
    "filtered_points": ["NPU 量化限制 — 过细技术细节"],
}

_M3_OUTPUT = {
    "target_audiences": [
        {
            "segment": "智能家居品牌产品经理",
            "description": "B 端选型决策者",
            "pain_points": ["性能功耗价格三角"],
            "preferred_channels": ["行业展会", "知乎"],
        }
    ],
    "core_channels": ["微信公众号", "知乎机构号", "B站"],
    "content_matrix": [
        {
            "phase": "awareness",
            "key_selling_points": ["旗舰级工艺 · 省电不烫手"],
            "content_types": ["科普长图文"],
            "sample_angles": ["一张图看懂为什么省电"],
        },
        {
            "phase": "seeding",
            "key_selling_points": ["旗舰级工艺 · 省电不烫手"],
            "content_types": ["深度测评"],
            "sample_angles": ["上手一周体感"],
        },
        {
            "phase": "conversion",
            "key_selling_points": ["旗舰级工艺 · 省电不烫手"],
            "content_types": ["限时活动"],
            "sample_angles": ["预订享开发板"],
        },
    ],
    "phases": ["冷启动(2周)", "爬坡(4周)", "放量(持续)"],
    "kpis": ["冷启动结束文章阅读 10w+"],
}

_M4_OUTPUT = {
    "campaign_theme": "芯·有力量",
    "slogan": "一颗芯,省心省电还更懂你",
    "video_scripts": [
        {
            "title": "30秒看懂芯片X",
            "duration_sec": 30,
            "hook": "为什么有的音箱能陪你一整天?",
            "body": "答案藏在一颗芯片里。",
            "cta": "关注我们",
        }
    ],
    "article": "# 芯·有力量\n\n正文...",
    "social_posts": [
        {
            "platform": "小红书",
            "title": "家里的音箱终于不烫手了",
            "body": "体验了搭载芯片X的新款...",
            "hashtags": ["#智能家居"],
        }
    ],
    "posters": [
        {
            "headline": "一颗芯,让智能更懂你",
            "subline": "7nm · AI 专芯 · 极速内存",
            "visual_keywords": ["科技蓝渐变"],
        }
    ],
    "offline_event": {
        "theme": "芯·有力量 开发者 Meetup",
        "flow": ["签到", "主题分享", "动手环节"],
        "materials": ["海报", "开发板礼盒"],
        "budget_framework": "单场 8-12 万",
    },
}


# 用 prompt 中角色标识符（prompts/*.md 顶部的"M1 技术翻译官"等）识别模块
_ROLE_TO_SAMPLE = [
    ("M1 技术翻译官", _M1_OUTPUT),
    ("M2 技术卖点包装师", _M2_OUTPUT),
    ("M3 推广策略规划师", _M3_OUTPUT),
    ("M4 营销内容策划师", _M4_OUTPUT),
]


def _fake_invoke_llm(model, prompt, *, system="", temperature=0.7, response_format="json", **kw):
    for marker, sample in _ROLE_TO_SAMPLE:
        if marker in prompt:
            return {
                "content": sample,
                "raw": json.dumps(sample, ensure_ascii=False),
                "tokens_in": 1000,
                "tokens_out": 500,
                "model": model,
            }
    raise RuntimeError(f"无法根据 prompt 识别模块；前 200 字符：{prompt[:200]}")


_llm_mod.invoke_llm = _fake_invoke_llm  # type: ignore[assignment]

# 同步 patch 到 nodes._helpers 已绑定的名字
from src.nodes import _helpers as _helpers_mod  # noqa: E402

_helpers_mod.invoke_llm = _fake_invoke_llm  # type: ignore[assignment]


# 现在才导入 graph / io_utils
from src.graph import build_graph  # noqa: E402
from src.io_utils import delete_task, list_tasks, load_task, save_task  # noqa: E402
from src.state import make_initial_state  # noqa: E402


def main() -> int:
    print("=" * 60)
    print("业务智能体后端冒烟测试")
    print("=" * 60)

    state = make_initial_state(
        task_id="smoke-test-001",
        task_name="冒烟测试 · 芯片X",
        raw_material="芯片X 采用 7nm FinFET 工艺, 内置 8 核 Cortex-A78 + NPU, 支持 LPDDR5X-8533 内存。",
        mode="auto",
        module_models={
            "m1": "openai/gpt-4o-mini",
            "m2": "openai/gpt-4o-mini",
            "m3": "openai/gpt-4o-mini",
            "m4": "openai/gpt-4o-mini",
        },
    )

    print("\n[1/4] 构造全自动图...")
    graph = build_graph("auto")
    print("    OK")

    print("\n[2/4] 运行图（mock LLM）...")
    final_state = graph.invoke(state)
    print("    OK ·", f"overall_status={final_state.get('overall_status')}")

    for key in ("m1", "m2", "m3", "m4"):
        output = final_state.get(f"{key}_output") or {}
        meta = final_state.get(f"{key}_meta") or {}
        first_field = next(iter(output), "-") if isinstance(output, dict) else "-"
        print(
            f"    [{key}] status={meta.get('status')}  model={meta.get('model')}  "
            f"duration={meta.get('duration_ms')}ms  first_field={first_field}"
        )

    print("\n[3/4] 落盘到 outputs/ ...")
    out_dir = save_task(final_state, outputs_dir=str(ROOT / "outputs"))
    print(f"    OK · {out_dir}")
    for name in ("meta.json", "state.json", "m1.md", "m2.md", "m3.md", "m4.md", "report.md"):
        p = Path(out_dir) / name
        assert p.exists(), f"缺失文件：{p}"
        print(f"    ✓ {name}  ({p.stat().st_size} bytes)")

    print("\n[4/4] 历史任务读取 / 删除 ...")
    all_tasks = list_tasks(outputs_dir=str(ROOT / "outputs"))
    matching = [t for t in all_tasks if t["task_id"] == "smoke-test-001"]
    assert matching, "list_tasks 未找到 smoke-test-001"
    print(f"    list_tasks 返回 {len(all_tasks)} 条，冒烟任务已收录")

    reloaded = load_task("smoke-test-001", outputs_dir=str(ROOT / "outputs"))
    assert reloaded.get("task_id") == "smoke-test-001"
    assert reloaded.get("m2_output", {}).get("core_claim")
    print("    load_task OK · core_claim 已回读")

    delete_task("smoke-test-001", outputs_dir=str(ROOT / "outputs"))
    assert not (Path(ROOT) / "outputs" / "smoke-test-001").exists()
    print("    delete_task OK · 目录已清理")

    print("\n✅ 冒烟测试全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
