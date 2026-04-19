# test_materials · 测试素材库

本目录存放用于**自动化测试**（`tests/`）和**手动功能验证**的原始技术资料。

所有资料取自公开的汽车零部件技术专利、百科与行业媒体报道，经摘录整理，**仅用于测试智能体流水线的数据合理性**，不代表任何商业立场或产品推广。

## 文件清单

| 文件 | 主题 | 场景价值 |
| --- | --- | --- |
| `01_carbon_ceramic_brake.md` | 碳陶瓷刹车盘（碳纤维增强陶瓷基复合材料） | 材料学 + 制造工艺 + 性能参数，类比"医用导管 vs 普通水管"适合 M1 翻译 |
| `02_ctb_battery_body.md` | CTB 电池车身一体化（比亚迪 Cell-to-Body） | 系统集成 + 安全/操控数据，富含可对齐用户痛点的量化指标 |
| `03_4d_imaging_radar.md` | 4D 毫米波成像雷达（ADAS 感知） | 硬核电子/信号处理参数，测试模型能否把难懂概念讲清楚 |
| `04_air_suspension_cdc.md` | 空气悬架 + CDC 连续阻尼控制 | 机电一体化，含三套竞品方案（CDC / MRC / 空气），测试 M2 差异化提炼 |
| `05_minimal_edge_case.txt` | 极短文本（<100 字） | 边界用例：材料不足时模型是否会臆造 / 节点是否会崩 |

## 资料来源

- Google Patents（CN102661342A / CN115823151B / WO2017107735A1）
- 汽车之家 · 车家号（CTB 技术解读）
- CSDN / 搜狐汽车（4D 毫米波雷达专题）
- ATC 汽车技术平台 / 和利时自控（悬架技术解读）

如需新增素材，建议每份控制在 600–1500 字，包含：
1. **原理** — 模型需要的技术底座
2. **关键参数** — M1 抽取、M2 包装、M3/M4 引用用数字
3. **对比/竞品** — 让 M2 有"差异化点"可写

## 如何被测试使用

```python
# tests/conftest.py 中的 fixture 自动加载本目录
from pathlib import Path
MATERIALS = Path(__file__).resolve().parent.parent / "test_materials"
brake_text = (MATERIALS / "01_carbon_ceramic_brake.md").read_text("utf-8")
```

端到端测试会将每份素材作为 `raw_material` 灌入 `build_graph("auto")`，并断言四个模块输出的结构完整性。
