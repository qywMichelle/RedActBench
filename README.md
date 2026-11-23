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
