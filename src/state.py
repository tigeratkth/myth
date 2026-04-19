"""
WorkflowState 数据契约

业务智能体 4 模块工作流的共享状态定义，是前后端两个 Track 的唯一"合同"。
任何改动必须同时考虑：
  - 后端节点（src/nodes/*.py）的读写
  - 前端页面（app.py、pages/*.py）的展示
  - Mock 数据（src/ui/mocks.py）的同步更新
  - 持久化（src/io_utils.py 读写 outputs/*/meta.json）
"""
from __future__ import annotations

from typing import Annotated, Literal, TypedDict
from operator import add


# ============================================================
# 模块 1 · 技术翻译官 输出
# ============================================================
class TechPoint(TypedDict):
    """单个技术要点：从原始技术资料中抽取并用用户语言重写"""
    original: str          # 原始表述（保留以便溯源）
    plain: str             # 通俗/用户语言表述
    analogy: str           # 类比举例（"这就好比..."）
    params: str            # 相关参数/量化指标，无则空串


class TranslatorOutput(TypedDict):
    tech_points: list[TechPoint]     # 技术要点列表
    capabilities: list[str]          # 关键能力清单
    boundaries: list[str]            # 能力边界/前提条件


# ============================================================
# 模块 2 · 技术卖点包装师（产出"技术IP"）
# ============================================================
class SellingPoint(TypedDict):
    name: str                        # 卖点名称
    user_description: str            # 用户语言的一句话描述
    user_need: str                   # 对应的用户需求/痛点
    supporting_points: list[str]     # 引用模块1 tech_points 中哪些（name or index）
    differentiation: str             # 差异化点


class IPOutput(TypedDict):
    """技术IP = 基于原始技术包装出来的、用户可理解 + 用户需要的技术卖点集合"""
    core_claim: str                          # 核心技术IP主张（一句话）
    selling_points: list[SellingPoint]       # 技术卖点列表
    target_user_hypothesis: list[str]        # 目标用户假设（供模块3细化）
    filtered_points: list[str]               # 不建议对外强调的技术点（供人工复核）


# ============================================================
# 模块 3 · 推广策略规划师
# ============================================================
class AudiencePersona(TypedDict):
    segment: str                     # 人群标签
    description: str                 # 画像描述
    pain_points: list[str]           # 对应的痛点
    preferred_channels: list[str]    # 他们常出现的渠道


class ContentMatrix(TypedDict):
    phase: Literal["awareness", "seeding", "conversion"]  # 认知/种草/转化
    key_selling_points: list[str]    # 本阶段主打的卖点名称
    content_types: list[str]         # 内容形态
    sample_angles: list[str]         # 示例切入角度


class StrategyOutput(TypedDict):
    target_audiences: list[AudiencePersona]
    core_channels: list[str]
    content_matrix: list[ContentMatrix]
    phases: list[str]                # 冷启动/爬坡/放量 的节奏描述
    kpis: list[str]                  # 关键 KPI


# ============================================================
# 模块 4 · 营销内容策划师
# ============================================================
class VideoScript(TypedDict):
    title: str
    duration_sec: int
    hook: str                        # 开场钩子
    body: str                        # 主体脚本
    cta: str                         # 行动号召


class SocialPost(TypedDict):
    platform: str                    # 小红书/微博/朋友圈 等
    title: str
    body: str
    hashtags: list[str]


class PosterCopy(TypedDict):
    headline: str
    subline: str
    visual_keywords: list[str]


class OfflineEvent(TypedDict):
    theme: str
    flow: list[str]                  # 活动流程
    materials: list[str]             # 物料清单
    budget_framework: str            # 预算框架描述


class MarketerOutput(TypedDict):
    campaign_theme: str              # 活动主题与传播语
    slogan: str                      # 一句 slogan 化的传播语
    video_scripts: list[VideoScript]
    article: str                     # 公众号长文（Markdown）
    social_posts: list[SocialPost]   # 小红书/短图文
    posters: list[PosterCopy]
    offline_event: OfflineEvent


# ============================================================
# 审核与元信息
# ============================================================
ModuleKey = Literal["m1", "m2", "m3", "m4"]
ModuleStatus = Literal["pending", "running", "awaiting_review", "approved", "completed", "failed"]
RunMode = Literal["auto", "human_review"]


class ModuleMeta(TypedDict, total=False):
    """每个模块的运行元信息"""
    status: ModuleStatus
    model: str                       # 实际使用的模型 id
    started_at: str                  # ISO 时间
    finished_at: str
    duration_ms: int
    tokens_in: int
    tokens_out: int
    error: str                       # 失败时的错误信息
    reviewed_at: str                 # 人工审核通过时间
    review_action: Literal["approved", "edited", "rerun"]


class ReviewFeedback(TypedDict, total=False):
    """人工审核动作（前端 → 后端）"""
    action: Literal["approve", "edit", "rerun"]
    edited_output: dict              # 修改后的模块输出（仅 edit 时有）
    comment: str                     # 备注


# ============================================================
# 顶层工作流状态
# ============================================================
class WorkflowState(TypedDict, total=False):
    """
    LangGraph 共享状态。各模块节点读取前序字段，写入自己的 output/meta。
    """
    # ---- 任务基本信息 ----
    task_id: str                     # 唯一 id（时间戳+slug）
    task_name: str                   # 用户填写或自动生成
    created_at: str

    # ---- 输入 ----
    raw_material: str                # 原始技术资料（已合并为纯文本）
    source_type: Literal["upload", "paste"]
    source_filename: str             # 若为上传

    # ---- 运行配置 ----
    mode: RunMode
    module_models: dict              # {"m1": "...", "m2": "...", ...}
    temperature: float

    # ---- 各模块产出 ----
    m1_output: TranslatorOutput
    m2_output: IPOutput
    m3_output: StrategyOutput
    m4_output: MarketerOutput

    # ---- 各模块元信息 ----
    m1_meta: ModuleMeta
    m2_meta: ModuleMeta
    m3_meta: ModuleMeta
    m4_meta: ModuleMeta

    # ---- 审核反馈（当前节点使用后清空） ----
    review: ReviewFeedback

    # ---- 运行时进度 ----
    current_module: ModuleKey        # 当前活跃模块
    overall_status: Literal["idle", "running", "awaiting_review", "completed", "failed", "interrupted"]

    # ---- 日志（追加式合并） ----
    logs: Annotated[list[str], add]


# ============================================================
# 工厂函数
# ============================================================
def make_initial_state(
    *,
    task_id: str,
    task_name: str,
    raw_material: str,
    mode: RunMode,
    module_models: dict,
    source_type: Literal["upload", "paste"] = "paste",
    source_filename: str = "",
    temperature: float = 0.7,
) -> WorkflowState:
    """构造初始 State。"""
    from datetime import datetime

    return WorkflowState(
        task_id=task_id,
        task_name=task_name,
        created_at=datetime.now().isoformat(timespec="seconds"),
        raw_material=raw_material,
        source_type=source_type,
        source_filename=source_filename,
        mode=mode,
        module_models=module_models,
        temperature=temperature,
        m1_meta={"status": "pending"},
        m2_meta={"status": "pending"},
        m3_meta={"status": "pending"},
        m4_meta={"status": "pending"},
        current_module="m1",
        overall_status="idle",
        logs=[],
    )


MODULE_KEYS: tuple[ModuleKey, ...] = ("m1", "m2", "m3", "m4")
MODULE_LABELS: dict[ModuleKey, str] = {
    "m1": "技术翻译",
    "m2": "技术IP",
    "m3": "推广策略",
    "m4": "营销内容",
}
MODULE_DESCRIPTIONS: dict[ModuleKey, str] = {
    "m1": "抽取技术要点并翻译为用户语言",
    "m2": "包装为用户可理解+用户需要的技术卖点",
    "m3": "围绕技术IP制定推广策略",
    "m4": "产出营销内容与活动方案",
}
