# 本机使用笔记

仓库：`git@github.com:qywMichelle/RedActBench.git`

本次学习固定版本：`30b38196ab972c4a81f636c8946ec8272c7923b0`。
以下命令都在 `/data/project/RedActBench/github_test_bundle` 执行。
本机虚拟环境为 `.venv`，使用 Python 3.11.15；系统已有 Cairo。
原 PyPI 在本机连接超时，依赖安装改用阿里云 PyPI 镜像，保留 `requirements.txt` 的版本约束。

## 数据和模型行为

- 默认清单为 400 道英文主情境，T1–T5 各 80 道；结构标签为 medium 227 道、hard 173 道，尚未完成人工难度校准。
- `--paired` 选择 215 对 A/B、共 430 个配置。它与默认主情境有重叠，合并按实际配置去重后共 615 个配置，不能把 830 次运行当成 830 道独立题。
- 204 对 A/B 的初始观察完全相同；后续应根据揭示的条件决定行动。行为是否改变不是通用正确性判据，在两种配置中都合理的策略可以同时通过。
- 包含 37 个图源。模型只看到已揭示观察、完整历史和已揭示图片；图片由运行器发送，SVG 转为 PNG。
- 每轮模型输出一个含 `action` 字段的 JSON 对象；操作及字段以当前观察中的 `tool_protocol` 为准。不是原生 function calling，运行器读取回复文本中的 JSON。
- 题目涉及发布/修订、售后、条件核验、授权撤回、活动协调等多步任务；要处理动态事件、时限、对象权限、外部回执和旧回复维护。
- 模型编写的文本必须为英文。虚拟时间由沙盒动作推进，不是实际 API 延迟。
- 被测模型输入不能包含隐藏世界、评分准则、参考轨迹或 A/B 差异说明。

## 环境检查

```bash
.venv/bin/python redact_bench.py verify
.venv/bin/python redact_bench.py verify --paired
.venv/bin/python -m unittest discover -s tests -v
```

这些检查不调用付费模型 API。集成测试使用本地模拟 HTTP 服务，检查接口、图片、轨迹导出、审核材料准备和断点续跑。

2026-11-19 本机检查结果：主清单 400/400 回放通过，A/B 清单 430/430 回放通过，冻结清单 2793 个文件校验通过；13 项集成测试全部通过。真实模型 API 调用数为 0。
日志和环境记录保存在 `github_test_bundle/output/local-preflight/`（Git 已忽略）。

## API 接入和小范围试跑

API key 从隐藏输入提示或已有 `REDACT_API_KEY` 环境变量读取；也可用 `--api-key-env` 指定已有环境变量名。不把真实密钥写进命令、文件或 Git。

OpenAI 兼容服务：

```bash
.venv/bin/python redact_bench.py run \
  --protocol openai --url https://PROVIDER/v1 \
  --model MODEL_ID --limit 3 --output runs/MODEL_ID-smoke
```

也接受服务根地址或完整 `/chat/completions` 地址。鉴权使用 `Authorization: Bearer`。
请求包含 `max_tokens`、`temperature`、`top_p`、`seed`；返回读取 `choices[0].message.content`。
有图题需要服务支持 `image_url` 中的 PNG data URL。

Gemini/MAAS 服务：

```bash
.venv/bin/python redact_bench.py run \
  --protocol gemini --url https://PROVIDER/v1:generateContent \
  --model MODEL_ID --limit 3 --output runs/MODEL_ID-smoke
```

必须提供完整 `:generateContent` URL。鉴权使用 `api-key`，图片使用 `inlineData`。
返回读取第一条 candidate 的非 thought 文本。服务需要接受请求体中的 `model` 和 `generationConfig`；具体供应商兼容性需实测。
两种模式都不支持在 URL 中嵌入鉴权、query 或 fragment。

默认串行，每题最多 200 次模型请求，单轮输出上限 4096 token，输入上限 200000 字符，temperature=1、top_p=0.95、seed=0、HTTP timeout=180 秒。
字符上限不是 token 上限；输入超限会停止，不截断历史。
429/500/502/503/504 及网络超时最多尝试 3 次；最终接口错误保存前缀并停止后续题。
若供应商不接受某个字段，需要先解决适配并固定版本，再开始正式运行。

默认 `--limit 3` 只是清单前三道，不能代表全部任务类型，也不覆盖所有图片能力。
需要覆盖多个任务类型时，可重复指定 `--case`；例如 `batch_020/t1-01` 至 `batch_020/t5-01` 各取一题，图片能力另用有图题核验。
`--paired --limit 2` 对应清单第一对 A/B；`--limit` 计的是配置数量。
初次运行使用新目录；没有明确范围指令时不直接启动全部 400 道。

## 续跑、检查与导出

```bash
.venv/bin/python redact_bench.py run --resume --output runs/MODEL_ID-smoke
.venv/bin/python redact_bench.py check-run --run runs/MODEL_ID-smoke
.venv/bin/python redact_bench.py export \
  --run runs/MODEL_ID-smoke --output exports/MODEL_ID-smoke.zip
```

续跑绑定原代码、数据 SHA、模型、URL、题目和预算；不能提高旧 run 的请求上限，也不能修改参数后续跑。
已终止题目跳过；基础设施错误和中断从已落盘回合继续。更换配置或代码应另开新目录。
`complete` 只表示运行终止，不代表语义成功。

## 质量评分

```bash
.venv/bin/python redact_bench.py evaluate \
  --run runs/MODEL_ID-smoke --output output/MODEL_ID-review --prepare
```

该命令仅回放、统计成本、生成 `judge-inputs/` 和 `templates/`，不会自动调用裁判或给分。
阅读真实轨迹和冻结准则后，把有证据、有理由且绑定轨迹 SHA 的评阅结果写入 `judgments/` 对应路径，然后执行同一命令去掉 `--prepare`。
不完整审核可加 `--partial`，未审题不会补零。

输出 `metrics-v2.json`、`per-episode-v2.csv`，支持按任务族、难度和批次汇总：

- 六维总分（0–100）：证据 25%、时机 20%、授权 20%、帮助 15%、克制 10%、沟通 10%；各维 0–4。
- GCR：适用目标完成权重占比，再按题平均。
- TSR：必要目标全部完成、必要限时目标全部按时、无关键违规的题占比。
- LCR：按时完成的适用限时目标占比。
- Efficiency：指定参考调用数 / 实际调用数，按题平均；参考不保证最短，数值可能大于 1。
- 请求、工具调用、格式/协议错误、覆盖率；CQ 单独报告。

基础设施失败、输入预算阻断、中断前缀从质量分中单列，已有成本仍统计。
当前数据是 development，`formal_evaluation_ready=false`，成绩应说明本地评阅方式及未完成的人工/裁判校准。

官方说明见 `github_test_bundle/README.md`、`EVALUATION.md` 和 `AGENTS.md`。本笔记位于冻结测试包之外，不修改数据或运行器。
