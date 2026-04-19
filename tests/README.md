# tests · 自动化测试

本目录使用 **pytest** 对业务智能体后端进行自动化测试。所有测试**不调用真实 LLM**，通过在 `conftest.py` 里对 `invoke_llm` 打 monkeypatch 注入合法的 mock 返回值，测试可在 CI 中稳定、快速地运行。

## 依赖安装

```powershell
pip install -r requirements-test.txt
```

## 运行方式

```powershell
# 跑全部测试
pytest -v

# 跑某个文件
pytest tests/test_graph.py -v

# 带覆盖率
pytest --cov=src --cov-report=term-missing

# 跑某一条 case（端到端中的某份素材）
pytest -v -k "carbon_ceramic_brake"
```

## 文件组织

| 文件 | 覆盖范围 | 依赖 |
| --- | --- | --- |
| `conftest.py` | 共享 fixtures：素材加载 / mock LLM / 临时 outputs 目录 / state 工厂 | — |
| `test_io_utils.py` | `read_material`、`save_task` / `load_task` / `list_tasks` / `delete_task`、Markdown 渲染 | 不依赖 LLM |
| `test_llm_utils.py` | `load_config`、`list_models`、`load_prompt`、`render_prompt`、`_extract_json` | 不依赖 LLM |
| `test_graph.py` | `build_graph` 双模式编译、四节点流转、model 传递、异常路径、`interrupt_after` | 依赖 `patch_llm` |
| `test_end_to_end.py` | 真实汽车零部件素材端到端走完 4 模块 + 落盘 + 回读 | 依赖 `patch_llm` + `test_materials/` |

## Mock LLM 的工作机制

`conftest.py::patch_llm` 做了两件事：

1. 把 `src.llm.invoke_llm` 替换为 `fake_invoke_llm`；
2. **同时**把 `src.nodes._helpers.invoke_llm` 替换（因为 `_helpers.py` 里 `from ..llm import invoke_llm` 已把对象绑进本地命名空间，只 patch `src.llm` 不够）。

`fake_invoke_llm` 根据 Prompt 顶部的角色标识（`M1` / `M2` / `M3` / `M4`）路由到不同的 mock 输出，避免不同模块共用的字段名导致串位（这是过往踩过的坑，见 `RETROSPECTIVE.md`）。

## 测试素材

端到端测试使用 `test_materials/` 下的 4 份真实汽车零部件公开技术资料 + 1 份极短边界样本。详见 [`test_materials/README.md`](../test_materials/README.md)。

## 与已有 `scripts/smoke_backend.py` 的关系

| 维度 | `scripts/smoke_backend.py` | `tests/` |
| --- | --- | --- |
| 定位 | 手动冒烟脚本 | 自动化回归测试 |
| 运行方式 | `python scripts/smoke_backend.py` | `pytest` |
| 覆盖粒度 | 1 条主路径 | 40+ 条细粒度 case |
| CI 友好 | 否（需人工看输出） | 是（退出码 + 结构化报告） |

未来建议：保留 smoke_backend 用于本地快速自测，把 `tests/` 作为 CI 准入门槛。
