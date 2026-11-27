# Gemini 3.8 Flash：全部轨迹与评分索引

本索引收集两轮常规615配置评测与此前hard50结果，共1280次已完成的配置运行记录。两轮常规测试使用同一400道主情境及215个B配置；每轮和hard50分别报告。历史结果原样归档，没有重新测题或重新judge。

| 轮次 / 数据集 | 轨迹与评分覆盖 | 六维总分 /100 | GCR | TSR | LCR | 待人工复核 |
|---|---:|---:|---:|---:|---:|---:|
| [11/23常规轮](../20261123-gemini/README.md) | 615/615 | 80.72 | 72.52% | 31.71% | 73.81% | 76 |
| [11/26常规轮](../20261126-gemini/README.md) | 615/615 | 80.95 | 72.96% | 32.52% | 73.86% | 72 |
| [11/24 hard50](hard50-scores.json) | 50/50 | 62.45 | 57.01% | 14.00% | 55.50% | 3 |

裁判均为`gpt-6.1-sol-science`，使用原项目v2准则；所有结果为自动评分，未经人工确认。常规轮次的A/B各215条、无配对主情境185条。各轮详细分组、源码绑定、逐题证据和不确定性保留在对应报告中。

## 下载

- [11/26最新常规轮615条轨迹](../20261126-gemini/gemini-3.8-flash-lucas-all615.zip) · [评分报告](../20261126-gemini/score-report.md) · [逐题CSV](../20261126-gemini/per-case-scores.csv) · [judge证据](../20261126-gemini/judge-evidence.zip)。
- [11/23历史常规轮615条轨迹](../20261123-gemini/gemini-3.8-flash-lucas-all615.zip) · [评分报告](../20261123-gemini/score-report.md) · [逐题CSV](../20261123-gemini/per-case-scores.csv) · [judge证据](../20261123-gemini/judge-evidence.zip)。
- [此前Gemini hard50原轨迹](../20261124-hard-case-50/gemini-3.8-flash-all50.zip) · [Gemini专用评分](hard50-scores.json) · [逐题CSV](hard50-per-case-scores.csv) · [专用judge证据](hard50-judge-evidence.zip)。
- [候选可见PNG原始字节](revealed-image-pixels.zip)：72份两轮实际输入图像绑定，按PNG SHA去重保留35个原始PNG；所有轨迹引用的PNG SHA均能匹配归档字节。
- [完整目录信息](catalog.json)、[归档核对记录](verification.json)与[SHA256SUMS.json](SHA256SUMS.json)。

hard50原轨迹和原200条共享judge包已在`d9d7bef`提交上传，本次保持原文件SHA。Gemini专用hard50 judge包按字节提取该原包的Gemini分区与共享评分源码，不改评分或证据；共享原绑定保留其200条来源范围。hard50使用此前固定的`gemini-3.8-flash:post-evaluation`路由，常规两轮为`gemini-3.8-flash-lucas`，实际报告版本均为Gemini 3.8 Flash。

全部轨迹以API可见模型回复、动作和工具反馈为准，包含冻结输入、时钟、图片与请求SHA及恢复记录。常规轮采用原官方History编码和200000字符输入上限；hard50使用最近20个回合窗口。源运行、评分和图片文件保持原字节。凭据不随归档发布。

本次完整性核对覆盖1230条常规轨迹、1230份judge、hard50原包与50份逐字节提取的Gemini评分；文本/图像回放和重新导出样本通过，全部新文件低于GitHub单文件100 MiB限制。
