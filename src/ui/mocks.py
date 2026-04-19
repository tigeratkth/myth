"""
Mock 数据集合 · 供前端在后端就绪前独立开发使用

设计原则：
1. 所有数据结构严格对齐 src/state.py 的 TypedDict 契约
2. 覆盖 5 个页面需要的全部场景（空态 / 进行中 / 完成 / 失败 / 中断）
3. 真实落盘版本（outputs/{task_id}/meta.json 与 m*.md）同步演示

集成阶段（phase 2）会把这里的函数替换为真实的数据读写，但函数签名保持不变。
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Literal, Optional

from ..state import WorkflowState


# ============================================================
# 基础示例：芯片X 技术IP 的一次完整人工审核运行
# ============================================================
_M1_OUTPUT = {
    "tech_points": [
        {
            "original": "采用 7nm FinFET 制程工艺",
            "plain": "用的是目前主流手机芯片都在用的顶尖工艺",
            "analogy": "就像从普通水管换成精密医用导管，能效大幅提升",
            "params": "7nm / FinFET",
        },
        {
            "original": "内置 8 核 ARM Cortex-A78 CPU + 独立 NPU",
            "plain": "8 个核心协同工作，还单独配了一颗专门跑 AI 的芯片",
            "analogy": "好比厨房里除了 8 个厨师，还专门请了一位只管做招牌菜的大厨",
            "params": "8 核 / NPU 算力 4 TOPS",
        },
        {
            "original": "支持 LPDDR5X-8533 内存接口",
            "plain": "内存读写速度是上一代的近两倍",
            "analogy": "相当于仓库和生产线之间的传送带变宽变快了",
            "params": "LPDDR5X / 8533 MT/s",
        },
    ],
    "capabilities": [
        "高能效比，长续航",
        "原生 AI 加速能力",
        "高速内存响应",
    ],
    "boundaries": [
        "需要配套 LPDDR5X 内存才能发挥全部性能",
        "NPU 仅支持 INT8/INT16 量化模型",
    ],
}

_M2_OUTPUT = {
    "core_claim": "用上旗舰级工艺与 AI 专芯,让你的智能设备既能跑得快,又能用得久。",
    "selling_points": [
        {
            "name": "旗舰级工艺 · 省电不烫手",
            "user_description": "跟最新旗舰手机用的是同一级工艺，续航更长、发热更低",
            "user_need": "用户怕耗电快、担心设备发烫",
            "supporting_points": ["7nm FinFET"],
            "differentiation": "同价位产品多为 12nm/14nm 工艺",
        },
        {
            "name": "AI 专芯 · 智能更聪明",
            "user_description": "单独一颗 AI 专芯，语音识别/图像处理反应更快、更准",
            "user_need": "用户希望设备"听得懂、看得清"",
            "supporting_points": ["独立 NPU"],
            "differentiation": "竞品多以 CPU 模拟 AI 计算，功耗高且响应慢",
        },
        {
            "name": "急速内存 · 切换不卡顿",
            "user_description": "多任务切换、大文件加载几乎没有等待感",
            "user_need": "用户反感卡顿和转圈",
            "supporting_points": ["LPDDR5X-8533"],
            "differentiation": "比主流 LPDDR4X 带宽提升约 90%",
        },
    ],
    "target_user_hypothesis": [
        "智能家居品牌的产品经理（选型决策）",
        "中高端 IoT 设备的终端消费者",
        "对续航与 AI 体验敏感的极客用户",
    ],
    "filtered_points": [
        "内存仅支持 LPDDR5X——属于技术前提，非卖点",
        "NPU 量化限制——偏技术细节，用户不关心",
    ],
}

_M3_OUTPUT = {
    "target_audiences": [
        {
            "segment": "智能家居品牌产品经理",
            "description": "25-40岁，负责新品选型与成本核算的 B 端决策者",
            "pain_points": ["选芯片时要在性能、功耗、价格三角间取舍", "担心供应链稳定性"],
            "preferred_channels": ["行业展会", "知乎/垂直论坛", "微信视频号"],
        },
        {
            "segment": "极客 / 开发者",
            "description": "关注 AIoT 的技术爱好者，喜欢拆解评测",
            "pain_points": ["买到的设备 AI 能力达不到宣传", "对参数和真实表现的差距敏感"],
            "preferred_channels": ["B 站", "少数派", "小红书"],
        },
    ],
    "core_channels": ["微信公众号", "知乎机构号", "B站测评合作", "小红书种草", "行业展会"],
    "content_matrix": [
        {
            "phase": "awareness",
            "key_selling_points": ["旗舰级工艺 · 省电不烫手"],
            "content_types": ["科普长图文", "30秒短视频"],
            "sample_angles": ["一张图看懂为什么省电", "同门级别对比"],
        },
        {
            "phase": "seeding",
            "key_selling_points": ["AI 专芯 · 智能更聪明", "急速内存 · 切换不卡顿"],
            "content_types": ["深度测评", "用户案例"],
            "sample_angles": ["上手一周体感总结", "与竞品盲测视频"],
        },
        {
            "phase": "conversion",
            "key_selling_points": ["旗舰级工艺 · 省电不烫手", "AI 专芯 · 智能更聪明", "急速内存 · 切换不卡顿"],
            "content_types": ["限时活动", "开发者福利包"],
            "sample_angles": ["预订享开发板套装", "品牌联合发布会"],
        },
    ],
    "phases": [
        "冷启动（2 周）：技术科普 + 首批 KOC 合作建立口碑",
        "爬坡（4 周）：深度测评 + 行业会议背书",
        "放量（持续）：开发者生态活动 + 客户案例展示",
    ],
    "kpis": [
        "冷启动结束时文章阅读 10w+",
        "爬坡期 B 站测评合计播放 50w+",
        "季度结束前获取 20 家意向客户",
    ],
}

_M4_OUTPUT = {
    "campaign_theme": "芯·有力量 — 让每一个智能设备都更聪明",
    "slogan": "一颗芯,省心省电还更懂你",
    "video_scripts": [
        {
            "title": "30 秒看懂芯片X 的三大进化",
            "duration_sec": 30,
            "hook": "同样是智能音箱,为什么有的能陪你聊一整天,有的不到半天就没电?",
            "body": "答案藏在一颗芯片里——更省电的工艺、独立的 AI 专芯、更快的内存……",
            "cta": "关注我们,第一时间拿到开发者套件",
        },
    ],
    "article": (
        "# 芯·有力量 — 为什么我们说芯片X 是智能设备的新标杆\n\n"
        "当你选购一款智能家居设备时,最在意的是什么?……（完整公众号长文）"
    ),
    "social_posts": [
        {
            "platform": "小红书",
            "title": "姐妹们！家里的智能音箱终于不烫手了",
            "body": "最近体验了搭载芯片X 的新款设备,续航肉眼可见地提升……",
            "hashtags": ["#智能家居", "#科技好物", "#续航怪兽"],
        },
    ],
    "posters": [
        {
            "headline": "一颗芯,让智能更懂你",
            "subline": "7nm 工艺 · AI 专芯 · 极速内存",
            "visual_keywords": ["科技蓝渐变", "芯片微观特写", "电路光效"],
        },
    ],
    "offline_event": {
        "theme": "芯·有力量 开发者 Meetup",
        "flow": [
            "14:00 签到与破冰",
            "14:30 主题分享：芯片X 架构深度解读",
            "15:30 圆桌：AIoT 场景落地案例",
            "17:00 动手环节 + 开发套件派发",
        ],
        "materials": ["主题海报", "开发板礼盒", "技术白皮书", "签到伴手礼"],
        "budget_framework": "单场 8-12 万（场地 / 嘉宾 / 物料 / 直播）",
    },
}


# ============================================================
# 三种典型 State 样本
# ============================================================
def _meta(
    status: str,
    model: str = "openai/gpt-4o",
    duration_ms: int = 18000,
    tokens_in: int = 2400,
    tokens_out: int = 1200,
) -> dict:
    return {
        "status": status,
        "model": model,
        "started_at": "2026-04-19T15:22:00",
        "finished_at": "2026-04-19T15:22:18",
        "duration_ms": duration_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }


def sample_state_completed() -> WorkflowState:
    """完整跑完四模块的 State。"""
    return WorkflowState(
        task_id="20260419-152200-chipx",
        task_name="芯片X 技术IP 包装",
        created_at="2026-04-19T15:22:00",
        raw_material="（此处为原始技术资料全文,示例省略）",
        source_type="paste",
        mode="human_review",
        module_models={
            "m1": "deepseek/deepseek-chat",
            "m2": "openai/gpt-4o",
            "m3": "openai/gpt-4o",
            "m4": "anthropic/claude-sonnet-4-5",
        },
        temperature=0.7,
        m1_output=_M1_OUTPUT,
        m2_output=_M2_OUTPUT,
        m3_output=_M3_OUTPUT,
        m4_output=_M4_OUTPUT,
        m1_meta=_meta("completed", "deepseek/deepseek-chat", 12000, 3000, 1500),
        m2_meta=_meta("completed", "openai/gpt-4o", 18000, 3200, 1400),
        m3_meta=_meta("completed", "openai/gpt-4o", 22000, 3500, 1700),
        m4_meta=_meta("completed", "anthropic/claude-sonnet-4-5", 38000, 2700, 3400),
        current_module="m4",
        overall_status="completed",
        logs=[
            "[15:22:00] 任务开始",
            "[15:22:12] 模块1 完成",
            "[15:22:30] 模块2 完成",
            "[15:22:52] 模块3 完成",
            "[15:23:30] 模块4 完成, 任务结束",
        ],
    )


def sample_state_awaiting_review() -> WorkflowState:
    """模块2 已完成,等待人工审核的 State。"""
    state = sample_state_completed()
    state["m3_output"] = {}
    state["m4_output"] = {}
    state["m3_meta"] = {"status": "pending"}
    state["m4_meta"] = {"status": "pending"}
    state["m2_meta"]["status"] = "awaiting_review"
    state["current_module"] = "m2"
    state["overall_status"] = "awaiting_review"
    state["task_id"] = "20260419-141000-motor"
    state["task_name"] = "电机Y 推广 IP"
    return state


def sample_state_running() -> WorkflowState:
    """模块3 正在运行的 State。"""
    state = sample_state_completed()
    state["m4_output"] = {}
    state["m4_meta"] = {"status": "pending"}
    state["m3_meta"] = {"status": "running"}
    state["current_module"] = "m3"
    state["overall_status"] = "running"
    state["task_id"] = "20260419-160500-sensor"
    state["task_name"] = "传感器Z 策略"
    state["mode"] = "auto"
    return state


def sample_state_idle() -> WorkflowState:
    """刚创建,未开始运行。"""
    return WorkflowState(
        task_id="",
        task_name="",
        raw_material="",
        source_type="paste",
        mode="human_review",
        module_models={
            "m1": "deepseek/deepseek-chat",
            "m2": "openai/gpt-4o",
            "m3": "openai/gpt-4o",
            "m4": "anthropic/claude-sonnet-4-5",
        },
        temperature=0.7,
        m1_meta={"status": "pending"},
        m2_meta={"status": "pending"},
        m3_meta={"status": "pending"},
        m4_meta={"status": "pending"},
        current_module="m1",
        overall_status="idle",
        logs=[],
    )


# ============================================================
# 历史记录 Mock（对应 outputs/*/meta.json）
# ============================================================
def sample_history_list() -> list[dict]:
    """历史任务列表（已按时间倒序）。

    字段与 outputs/{task_id}/meta.json 对齐:
    { task_id, task_name, mode, status, created_at, completed_at,
      duration_ms, models: {m1,m2,m3,m4}, current_stage }
    """
    return [
        {
            "task_id": "20260419-152200-chipx",
            "task_name": "芯片X 技术IP 包装",
            "mode": "human_review",
            "status": "completed",
            "created_at": "2026-04-19T15:22:00",
            "completed_at": "2026-04-19T15:25:12",
            "duration_ms": 192000,
            "models": {
                "m1": "deepseek/deepseek-chat",
                "m2": "openai/gpt-4o",
                "m3": "openai/gpt-4o",
                "m4": "anthropic/claude-sonnet-4-5",
            },
            "current_stage": "m4",
        },
        {
            "task_id": "20260419-141000-motor",
            "task_name": "电机Y 推广 IP",
            "mode": "human_review",
            "status": "interrupted",
            "created_at": "2026-04-19T14:10:00",
            "completed_at": None,
            "duration_ms": 65000,
            "models": {
                "m1": "deepseek/deepseek-chat",
                "m2": "openai/gpt-4o",
                "m3": "openai/gpt-4o",
                "m4": "anthropic/claude-sonnet-4-5",
            },
            "current_stage": "m2",
        },
        {
            "task_id": "20260419-160500-sensor",
            "task_name": "传感器Z 策略",
            "mode": "auto",
            "status": "running",
            "created_at": "2026-04-19T16:05:00",
            "completed_at": None,
            "duration_ms": 0,
            "models": {
                "m1": "deepseek/deepseek-chat",
                "m2": "deepseek/deepseek-chat",
                "m3": "deepseek/deepseek-chat",
                "m4": "deepseek/deepseek-chat",
            },
            "current_stage": "m3",
        },
        {
            "task_id": "20260418-103000-radar",
            "task_name": "雷达模组 A 推广",
            "mode": "auto",
            "status": "failed",
            "created_at": "2026-04-18T10:30:00",
            "completed_at": "2026-04-18T10:30:45",
            "duration_ms": 45000,
            "models": {
                "m1": "openai/gpt-4o-mini",
                "m2": "openai/gpt-4o-mini",
                "m3": "openai/gpt-4o-mini",
                "m4": "openai/gpt-4o-mini",
            },
            "current_stage": "m1",
        },
    ]


# ============================================================
# 环境状态 Mock（首页卡片）
# ============================================================
def sample_env_status() -> dict:
    """首页 3 个状态卡片的数据。

    完整版本由 phase 2 替换为真实的 .env 扫描 + config.yaml 读取。
    """
    return {
        "api_keys": {
            "configured_count": 3,
            "total_providers": 4,
            "providers": ["OpenAI", "Anthropic", "DeepSeek"],
        },
        "default_model": {
            "all_module_same": False,
            "summary": "分模块配置 · 4 个模型",
        },
        "default_mode": "human_review",
    }


# ============================================================
# 工具
# ============================================================
def format_duration(ms: int) -> str:
    """把毫秒格式化为 3m12s / 45s 这种阅读友好格式。"""
    if ms < 1000:
        return f"{ms}ms"
    total_sec = ms // 1000
    if total_sec < 60:
        return f"{total_sec}s"
    m, s = divmod(total_sec, 60)
    return f"{m}m{s:02d}s"


def format_datetime(iso_str: Optional[str]) -> str:
    """ISO 时间字符串格式化为 2026-04-19 15:22。"""
    if not iso_str:
        return "--"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str


STATUS_TO_CHIP = {
    "completed": "completed",
    "running": "running",
    "awaiting_review": "awaiting",
    "interrupted": "awaiting",
    "failed": "failed",
    "pending": "pending",
    "idle": "pending",
}
