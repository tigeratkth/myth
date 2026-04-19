# 协作复盘笔记（Retrospective Log）

> 本文件用于积累 **用户 ↔ Cursor（AI 助手）** 协作过程中的经验教训。
> 重点记录：**用户纠正我的地方、我踩过的坑、有效的工作模式**。
> 每条记录应具体、可操作，避免空话。

---

## 使用约定

- **触发时机**
  1. 用户明确纠正 / 否定我的做法时 → 立即追加一条"纠正记录"
  2. 长任务的阶段性节点、或对话接近尾声 → 追加一条"阶段复盘"
  3. 新会话开始 → 先读取本文件，避免重复犯错
- **记录格式**：使用下方模板，保持条目精简（3-8 行）。
- **语言**：与用户保持一致，使用中文。
- **禁止**：不要记流水账、不要复述显而易见的事实。

---

## 记录模板

```md
### YYYY-MM-DD HH:MM — <一句话标题>
- **场景**：用户想做什么 / 我在做什么
- **问题**：我做错了什么 / 用户如何纠正
- **教训**：下次遇到类似情况应如何处理
- **标签**：#纠正 / #复盘 / #工作流 / #工具使用 / #沟通
```

---

## 通用经验（从所有条目中提炼的稳定规律）

<!-- 当同类教训出现 ≥ 2 次时，将其提炼到这里，便于快速查阅 -->

- _（暂无，待积累）_

---

## 纠正 & 复盘记录（按时间倒序，新的在上）

### 2026-04-19 — 自动化测试套件交付复盘
- **场景**：为四模块智能体写 pytest 测试套件（`tests/`）与汽车零部件真实素材库（`test_materials/`），覆盖 IO / LLM 工具 / 图编译 / 端到端 5 类共 66 个用例。
- **问题 1**：Mock LLM 按 `"M1"` / `"M2"` 裸标识路由 → M2/M3/M4 的 Prompt 正文都会引用 M1 的输出作为变量，导致下游 prompt 同时命中多个 marker，按顺序误路由到 M1。现象：`m2_output.core_claim is None`、测试断言 `markers == ['M1','M1','M1','M2']`。
- **问题 2**：测试自身的"按 prompt 判断模块"断言犯了同样的错，必须同步修复为"最早出现位置优先"策略。
- **教训**：
  1. mock 路由键必须选**足够独特的完整标识**（如 `"M1 技术翻译官"`），不要用可能在模块间被引用/传递的短串。这是 `smoke_backend.py` 已经踩过的同一个坑，**测试 fixture 里应该直接复用那套"完整角色名"判定**，而不是重新发明短串。
  2. `monkeypatch.setattr(src.llm, "invoke_llm", ...)` 不够，还要 patch `src.nodes._helpers.invoke_llm`——因为后者已用 `from ..llm import invoke_llm` 把对象绑进本地命名空间。
  3. Windows 控制台跑 pytest 要 `$env:PYTHONIOENCODING="utf-8"`，否则中文 assert 报错输出全是乱码。
- **标签**：#复盘 #工具使用 #工作流

### 2026-04-19 — Track B 前端 5 页交付阶段复盘
- **场景**：作为子 agent 完成 Streamlit 前端 5 页脚手架（app.py + 4 个 pages），纯 mock 数据。
- **问题**：Streamlit `st.navigation` 新 API 与 `st.set_page_config` 调用时机冲突——如果 app.py 已调用过 set_page_config，pages/*.py 再调用就会报错。
- **教训**：
  1. 对混用 `pages/` 自动发现 + 自定义中文导航，最稳的做法是 `st.page_link` 手写导航 + CSS 隐藏默认 nav（`[data-testid="stSidebarNav"]{display:none}`），每页各自 `set_page_config`。
  2. `st.button(type="tertiary")` 需要 Streamlit ≥ 1.34；prompt 已说明 1.40 支持，放心用。
  3. 跨页状态优先走 `st.session_state`（如 `current_state`、`viewing_task_id`），不要依赖 URL query 参数。
  4. 渲染 HTML 时别在字符串里用 f-string 嵌入多层引号；必要时用 `st.markdown(..., unsafe_allow_html=True)` 拼接。
- **标签**：#复盘 #工具使用

### 2026-04-19 — Track A 后端首次交付 & 踩坑

- **场景**：后端子 agent 实现 `src/llm.py`、4 个 node、`graph.py`、`io_utils.py`、`prompts/*.md`，并跑 `scripts/smoke_backend.py` 冒烟。
- **问题 1**：`src/ui/mocks.py` 第 69 行 `"用户希望设备"听得懂、看得清""` 存在未转义的双引号导致 `SyntaxError`；任务规则禁止我改 ui 层，只能在 smoke 脚本里内嵌一份精简 mock 绕过。
- **问题 2**：Windows 控制台默认 cp1252 编码导致中文 print 报 `UnicodeEncodeError` → 在脚本入口用 `sys.stdout.reconfigure(encoding="utf-8")` 兜底。
- **问题 3**：初版 mock 路由按字段名匹配（`tech_points`/`selling_points` 等），但下游 prompt 把上游 JSON 整体拼进模板，导致 m2 的 prompt 也含 `tech_points` → 误路由到 m1 样本。改为按 prompt 顶部的角色标识 `M1/M2/M3/M4` 精确匹配。
- **教训**：
  1. 写 mock 时要选**单向不变、不会被上游内容污染**的识别键（角色名、专属标题），不要用可能在多模块间传递的字段名。
  2. Windows 路径 + 中文输出默认会掉编码，脚本入口显式 reconfigure stdout 已成常规动作。
  3. 在"不能改 X 模块"的硬约束下遇到 X 本身有 bug 时，绕开 + 汇报是最合规的选择。
- **标签**：#工具使用 #复盘 #工作流

### 2026-04-19 — 初始化本文件
- **场景**：用户要求我"每10分钟复盘，并把纠正过我的经验写入 workspace 级 md 文件"。
- **问题**：我无法真正按定时器自动运行；初次回答若只是机械地"好的"，会让规则形同虚设。
- **教训**：
  1. 明确告知用户我的运行边界（只在被调用时有行动机会）。
  2. 用"事件触发 + 会话启动时必读"来近似实现"定时复盘"。
  3. 用 Cursor 规则把"每次会话先读此文件"固化下来。
- **标签**：#工作流 #沟通
