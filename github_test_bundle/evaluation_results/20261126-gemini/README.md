# Gemini 3.8 Flash 常规评测：2026-11-26 轮次

本轮为同一原始题库的400道主情境及其215个额外B配置，共615次运行：A215、B215、无配对主情境185。行为与自动judge全部完成，32个批次均已官方汇总，评分结束于2026-11-27。

模型路由为`gemini-3.8-flash-lucas`，接口实际报告`gemini-3.8-flash`；使用Gemini原生接口。裁判为`gpt-6.1-sol-science`，沿用原项目v2六维锚点及确定性指标计算。

| 分组 | 数量 | 六维总分 /100 | GCR | TSR | LCR |
|---|---:|---:|---:|---:|---:|
| 总体 | 615 | 80.95 | 72.96% | 32.52% | 73.86% |
| A配置 | 215 | 81.61 | 72.91% | 35.35% | 75.53% |
| B配置 | 215 | 81.39 | 73.76% | 36.28% | 75.59% |
| 无配对主情境 | 185 | 79.67 | 72.09% | 24.86% | 69.21% |

615条均有有效自动评分，其中72条保留待人工复核事项。`scores.json`的partial状态记录这些复核事项，`scoring_complete=true`与615条覆盖已核验。所有评分未经人工确认；CQ没有校准锚点，保持null。

GCR为目标完成率；TSR为整条任务满足全部必要条件的成功率；LCR为限时目标按时完成率。模型回复、失败的格式/动作尝试、工具反馈和恢复记录都保留。

## 归档内容

- [完整615条轨迹ZIP](gemini-3.8-flash-lucas-all615.zip)：32个原始官方导出ZIP，内含全部模型可见回复、动作、工具结果、时钟、配置、输入与图片绑定。
- [评分报告](score-report.md)、[完整汇总](scores.json)、[逐题CSV](per-case-scores.csv)和[复核清单](review-needed.json)。
- [judge证据ZIP](judge-evidence.zip)：615份评分、原始裁判可见响应、实际证据指针、32批官方指标及CSV、源码快照。
- [传输与恢复来源](transport-provenance.zip)、[运行汇总](execution-summary.json)、[原计划](plan.json)、[judge绑定](judge-binding.json)。
- [原judge完成检查](judge-verification.json)、[本次完整性核对](verification.json)、[提交前回放和重新导出样本](submission-checks.json)。
- [候选实际看到的原始PNG](../gemini/revealed-image-pixels.zip)：两轮共享的精确图像字节和逐图SHA绑定。
- [SHA256SUMS.json](SHA256SUMS.json)：本目录归档文件哈希。

全部64个两轮运行ZIP的原回放报告、覆盖和内部SHA已核对；两轮各选一个文本与图像批次重新check-run/export，原封存成员保持一致。所有归档与核对均为离线操作，没有重新调用模型。原配置中的绝对路径保留，迁移审核时请保持封存字节并核对输入、源码和图片SHA。

[返回全部Gemini结果索引](../gemini/README.md)
