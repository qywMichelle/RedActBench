# hard_case

最近两批各 10 条的整理包，共 **20 条独立英文情境**。目录参照 `batch_018`；不生成审阅 HTML，不修改原批次，不并入 original400。

统一标记 **hard**（按用户要求，相对原 benchmark）。原始标签保存在每题 `source_structural_difficulty`：18 hard、2 medium（c06、c10）。此次标签整理不代表重新完成了经验难度校准。包仍为 development，`formal_evaluation_ready=false`。

- `manifest.json`：唯一当前入口，逐题输入、rubric、轨迹、SHA256、运行时版本及公开工具协议。
- `visible/`、`hidden/`、`rubrics/`：20 题数据，原文件逐字节保留。
- `trajectories/<case>/`：135 份作者参考、合法替代、边界和反例轨迹。反例不应视为成功答案。
- `runtime/v1/`、`runtime/v2/`：两套原运行时、测试和构造器；按 manifest 选择，不混用通信协议。
- `reviews/`、`historical/`、`construction/`：原验收和历史修订证据。历史快照不计入当前样本。
- `provenance/`：原 manifest、种子哈希、说明和验证报告的原样存档。存档中的相对路径仍指向原批次；当前路径以本包 manifest 为准。
- `case-summary-zh.md`：中文逐题索引；`case-summary.json`：机器可读统计。
- `evaluations/opus_window15/`：既有 Opus 最近 15 轮 history 实测记录、状态、匿名评阅、裁定和结果，与作者轨迹分开保存。完整 API 请求和流式响应保留在 index.json 指向的原 runs 目录。
- `source-path-map.json`、`file-inventory.json`：来源和全包文件哈希。

共 152 个目标、299 个 rubric 检查；参考轨迹总计 929 次工具调用，平均 46.45 次。这是参考路径长度，不是最短合法路径；每题细项见汇总表。

既有 Opus 评测不重新评分：两批合计 10 条确认成功、7 条确认失败、3 条未裁定；严格成功率区间 50%–65%。模型只按网关标签记录，属于单样本开发诊断。

## 使用和核验

模型只接收对应题的公开工具协议与运行时 `World(hidden).observe()` 返回的当前观察。`hidden/`、rubric、参考/反例、来源、历史、评分与模型轨迹均为控制器或离线审阅材料，禁止作为模型输入。

```bash
python data/hard_case/verify.py
python data/hard_case/build.py --out /tmp/hard_case-copy
```

verify 验证哈希及两套运行时的完整轨迹重放，不将程序回放一致冒充语义成功。build 向不存在的新目录复制并验证完整可携带包，不覆盖原包；原构造器也保存在 runtime 各版本下。

整理新增的是统一入口、路径映射、统一 hard 标签和完整性核验；原验收报告与评分保持原状，没有新增构造验收轮次或人工审阅。
