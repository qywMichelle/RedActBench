# RedActBench

当前可运行的同伴行为测试包位于 [github_test_bundle](github_test_bundle/README.md)。

包含400道英文主情境、215个B配置（共615个可执行配置）、37个图源，以及测试、轨迹检查、导出和负责人统一评分入口。同伴只运行模型行为测试并提交轨迹，语义评测由项目负责人统一执行。

```bash
cd github_test_bundle
python -m pip install -r requirements.txt
python redact_bench.py verify
```

A/B配对测试、API配置和完整操作说明见[使用文档](github_test_bundle/README.md)。密钥不随仓库发布。

`ldm` 分支保存了 [GPT 6.1 Sol 与 Opus 的评测结果和轨迹](github_test_bundle/evaluation_results/20261119/README.md)：各 615 个配置的官方导出、Sol 自动裁判证据和传输版本记录。自动评分尚未人工确认；Opus 已完成行为运行，尚无语义评分。

另有 [Hard case 50 × 4 模型的 200 条轨迹与评分](github_test_bundle/evaluation_results/20261124-hard-case-50/README.md)：Opus 5.5、Gemini 3.8 Flash、GPT 6.1 Sol、Kimi 3.1 Pro 各 50 条，行为轨迹与 judge 全部完成。归档包含原始轨迹 ZIP、完整裁判证据、逐题 CSV、冻结数据与运行时、复核清单和 SHA 校验记录；评分沿用原项目 v2 准则，7 条标记待人工复核，GPT 候选属于同模型评审。

[Gemini 3.8 Flash 全部结果索引](github_test_bundle/evaluation_results/gemini/README.md)汇集 11/23、11/26 两轮常规 615 配置评测及此前 hard50：完整轨迹、A/B 分组评分、逐题 CSV、裁判证据、候选实际看到的 PNG 字节和 SHA 核对记录均已归档。两轮常规六维总分为 80.72、80.95，hard50 为 62.45；各轮分开报告，自动评分尚未人工确认，hard50 原记录保持原样。
