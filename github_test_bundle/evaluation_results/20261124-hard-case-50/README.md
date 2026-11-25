# Hard case 50 × 4 模型：200 条轨迹与评分

本目录归档同一组 50 个 hard case 在 Opus 5.5、Gemini 3.8 Flash、GPT 6.1 Sol 和 Kimi 3.1 Pro 上的全部 200 次运行，以及对应的 200 份自动 judge。50 个题目的来源是仓库 `main` 分支的 `adcf0ca` 提交；冻结数据和两套原始 `World` 运行时一并保存在来源归档中。

行为测试于 2026-11-25 08:17:58 完成，耗时约 16 小时 56 分钟；judge 于当天 11:32:28 完成，耗时约 79 分钟。时间均为 Asia/Hong_Kong。四个模型均为 50/50 正常终止、50/50 轨迹导出、50/50 评分完成。

## 评分结果

| 模型 | 已评分 | 六维总分 /100 | GCR | TSR | LCR |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 | 50/50 | 74.72 | 74.61% | 28.00%（14/50） | 73.30% |
| Gemini 3.8 Flash | 50/50 | 62.45 | 57.01% | 14.00%（7/50） | 55.50% |
| GPT 6.1 Sol | 50/50 | 85.08 | 89.69% | 60.00%（30/50） | 89.27% |
| Kimi 3.1 Pro | 50/50 | 76.92 | 80.10% | 36.00%（18/50） | 79.59% |

GCR 为目标完成率；TSR 要求整条任务的必要目标、时限与关键边界均满足；LCR 为限时目标按时完成率。六维沿用原项目的证据、时机、授权、帮助、克制、沟通锚点，权重分别为 25、20、20、15、10、10。

裁判是 `gpt-6.1-sol-science`，使用原项目 `redact-scoring-v2` 协议和确定性评分器。GPT 候选属于同模型评审，其余三个模型在汇总中标为非同模型评审。所有结果均为自动评分，尚未经人工确认。全部 200 条均有有效评分，其中 7 条标记了进一步人工复核事项：Opus 1 条、Gemini 3 条、GPT 2 条、Kimi 1 条。详见 [复核清单](review-needed.json)。CQ 未提供校准锚点、作者参考轨迹未分发，CQ 和相对参考轨迹的效率指标保持 `null`。

## 轨迹与模型绑定

| 展示名称 | 冻结 API model ID | 接口协议 |
|---|---|---|
| Opus 5.5 | `claude-opus-5-5-hc` | Messages |
| Gemini 3.8 Flash | `gemini-3.8-flash:post-evaluation` | Gemini 原生 generateContent |
| GPT 6.1 Sol | `gpt-6.1-sol-science` | Responses |
| Kimi 3.1 Pro | `kimi-k3.1-pro-lucas` | Chat Completions |

候选实际只接收最近 20 个模型/工具回合，并保留完整当前观察与公开工具描述。所有回合仍完整保存在轨迹中；judge 读取完整轨迹和实际交付内容。原数据、模型绑定、预算和已完成轨迹均保持原样。API 可见候选回复、动作、工具反馈、虚拟时钟、usage 与请求/观察 SHA 都包含在导出包中。

集合编号 `h001`–`h050` 是归档索引；原世界编号分别为 `c01`–`c10`、`h01`–`h10`、`n01`–`n10`、`p01`–`p20`，映射同时保存在逐题 CSV 和原绑定中。

## 文件与下载

| 文件 | 内容 |
|---|---|
| [Opus 全部 50 条轨迹](opus-5.5-all50.zip) | 50 个原始导出 ZIP |
| [Gemini 全部 50 条轨迹](gemini-3.8-flash-all50.zip) | 50 个原始导出 ZIP |
| [GPT 全部 50 条轨迹](gpt-6.1-sol-all50.zip) | 50 个原始导出 ZIP |
| [Kimi 全部 50 条轨迹](kimi-3.1-pro-all50.zip) | 50 个原始导出 ZIP |
| [全部 judge 证据](judge-evidence.zip) | 200 份评分、完整评审输入、裁判可见响应、证据指针、逐题指标、绑定和评分源码快照 |
| [数据、运行时与来源记录](data-runtime-provenance.zip) | 冻结数据、原始运行器与 History 编码器、接口与调度绑定、三份请求 ledger、恢复记录和行为运行源码 |
| [逐题 CSV](per-case-scores.csv) | 200 条逐题六维、GCR/TSR/LCR、关键边界、调用成本与复核标记 |
| [评分报告](score-report.md) / [完整汇总](judge-summary.json) | 分模型指标及原始聚合结果 |
| [运行汇总](execution-summary.json) / [数据预检](data-preflight.json) | 覆盖、终止状态、文件 SHA 和初始观察验证 |
| [提交前检查](submission-checks.json) / [归档完整性](verification.json) | 200 条重新 check-run、重新 export、封存成员逐字节比对和 ZIP 完整性核验 |
| [judge 完成检查](judge-completion-verification.json) / [judge 绑定](judge-binding.json) | 200 份评分覆盖、输入绑定、源码 SHA 与原证据包一致性 |
| [SHA256SUMS.json](SHA256SUMS.json) | 本目录归档文件的 SHA256 |

每个模型 ZIP 的 `exports/` 下有 50 个案例 ZIP。案例内包含 `turns.jsonl`、`steps.jsonl`、`world-record.json`、冻结配置、状态、`trace-integrity.json` 与 `replay-verification.json`。模型和裁判产生的全部可见内容均按原记录封存。

## 完整性与审核

发布前已对 200 条重新执行冻结入口的 `check-run` 与 `export`，全部通过，并核对原封存成员内容。GPT `h001` 的源目录后来多了一个运行锁文件，重新导出仅增加该锁及其清单项；原轨迹内容和本目录的原始 ZIP 均保持原样，具体差异记录在提交检查中。

全部嵌套 ZIP 均通过完整性检查，200 份 judge 的输入绑定和目标覆盖已核对。归档的 4003 个成员通过凭据模式检查。打包和提交检查均为离线操作，没有启动新的付费模型调用。

原始绑定保留运行时的绝对路径。迁移审核时请核对数据与文件 SHA，保留原封存配置字节；运行器、数据和评审源码都在 ZIP 中可供审核。

在本目录可使用标准库核对所有分发文件：

```bash
python - <<'PY'
import hashlib, json
from pathlib import Path
for name, expected in json.loads(Path('SHA256SUMS.json').read_text()).items():
    digest = hashlib.sha256()
    with open(name, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    assert digest.hexdigest() == expected, name
print('All archive files verified')
PY
```
