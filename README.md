# RedActBench

当前可运行的同伴行为测试包位于 [github_test_bundle](github_test_bundle/README.md)。

包含400道英文主情境、215个B配置（共615个可执行配置）、37个图源，以及测试、轨迹检查、导出和负责人统一评分入口。同伴只运行模型行为测试并提交轨迹，语义评测由项目负责人统一执行。

```bash
cd github_test_bundle
python -m pip install -r requirements.txt
python redact_bench.py verify
```

A/B配对测试、API配置和完整操作说明见[使用文档](github_test_bundle/README.md)。密钥、模型测试轨迹及本地审核输出不随仓库发布。

## Hard-case data

[50 道 hard-case 数据](data/hard_case_50/)位于仓库根目录的 `data/hard_case_50/`，与默认400题主清单分开。按要求只上传数据，**不包含 `trajectories/` 或测试轨迹**；其余290份源文件保持原字节。具体文件及SHA见 [DISTRIBUTION.json](data/hard_case_50/DISTRIBUTION.json)。

原目录的 manifest、file-inventory、verification 和 verify.py 保留为完整本地集合的来源记录，其中的作者轨迹引用不代表文件已随本次上传；全量轨迹重放仍需原本地集合。本次没有新增模型测试、评分或轨迹重放。
