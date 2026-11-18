# RedAct Bench 同伴行为测试包

把这个文件夹单独复制到其他机器即可运行。包含当前 400 道英文主情境、215 个 B 配置、对应图片、运行器、评分准则和 615 条指定参考轨迹。测试同伴填写 URL、API key 和模型名，运行并提交轨迹；项目负责人统一评阅实际轨迹。`complete` 仅表示执行终止，不表示任务合格。

## 安装与离线检查

需要 Python 3.11+。建议 Linux/macOS；Windows 可使用 WSL。SVG 渲染依赖 Cairo 系统库（Ubuntu 可安装 `libcairo2`），然后执行：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python redact_bench.py verify
python redact_bench.py verify --paired
python -m unittest discover -s tests -v
```

`verify` 检查文件 SHA、初始输入投影、图片及参考轨迹精确回放，不调用 API。默认主配置 400 条；`--paired` 为 215 对的 430 条 A/B 配置。两者合并去重是 615 个配置。参考回放只检查环境一致性，不代替语义评测，也不证明参考是最短解。

## 同伴：调用自己的模型

OpenAI 兼容接口（URL 可以是服务根地址、`/v1` 或完整的 `/chat/completions`）：

```bash
python redact_bench.py run \
  --protocol openai --url https://your-provider.example/v1 \
  --model YOUR_MODEL --limit 3 --output runs/my-model-smoke
```

Google `generateContent` / MAAS 接口：

```bash
python redact_bench.py run \
  --protocol gemini --url https://your-provider.example/v1:generateContent \
  --model 'Gemini 3.8 Flash' --limit 3 --output runs/gemini-smoke
```

启动后会隐藏提示输入 API key，不回显、不写入结果。也可从预先配置的 `REDACT_API_KEY` 环境变量读取，或用 `--api-key-env VARIABLE_NAME` 指定已有变量。OpenAI 模式使用 `Authorization: Bearer`，Gemini 模式使用 `api-key`。无鉴权本地服务可使用 `--no-auth`。

默认串行运行，参数为 temperature=1、max output tokens=4096、topP=0.95、seed=0、每题最多 200 次模型请求、输入最多 200000 字符。使用 `--max-requests`、`--max-tokens`、`--max-prompt-chars` 等显式调整。输入超限停止，不截断历史。接口需接受对应模式中的这些字段；OpenAI 图片使用 `image_url`，Gemini 图片使用 `inlineData`，SVG 保留完整画布转为 PNG。不会把模型的私有推理字段当作动作。

选择题目：

```bash
python redact_bench.py list --limit 10
python redact_bench.py list --paired --limit 4
python redact_bench.py run --protocol openai --url http://127.0.0.1:8000/v1 \
  --model my-model --no-auth --case batch_020/t1-01 --output runs/one-case
```

不加 `--limit` / `--case` 会运行所选清单全部题目并产生模型调用费用。首次运行使用新的输出目录。遇到接口/预算错误会保存已完成前缀并停止后续题目；不会自动换 key 或重新采样已终止的题。

## 断点续跑

首次运行仍使用上面的命令。中断或接口恢复后，在**同一版本**的测试包中执行：

```bash
python redact_bench.py run --resume --output runs/my-model-smoke
```

模型、URL、A/B 选择、题目范围、采样参数、输入上限和总请求预算都从原 `run_config.json`、`frozen-manifest.json` 读取，无需重新填写。也可以在原命令后添加 `--resume`，但显式提供的配置必须与原来一致。可以更新 API key，或用 `--api-key-env NEW_VARIABLE` 改用另一个已有凭据环境变量；密钥仍不写入文件。

- `run-binding.json` 绑定原配置和冻结清单的文件 SHA，手工修改 URL、预算或其他配置也会拒绝恢复。先校验原数据、运行器、客户端代码和文件清单 SHA，再逐轮重建观察、完整历史、图片及请求体，核对哈希和工具结果。任何不一致都在发请求前拒绝恢复。
- `complete`、`request_limit`、`action_budget_exhausted`、`input_budget_exceeded` 已终止题目直接跳过，不重写其轨迹、不重发请求。请求预算以已保存请求总数累计，不因续跑清零，也不能提高旧 run 的上限。
- `running`、`infrastructure_error`、`user_stopped` 的题从已落盘回合继续；尚未开始的题随后正常启动。A、B 分别恢复各自状态和历史。
- Ctrl+C 或 SIGTERM 会保存中断前缀并停止后续题目；进程被强制结束时，恢复最近一次完整原子落盘。中断时尚未落盘的在途请求无法确认服务端是否已执行，恢复时可能重新发送这一轮；已落盘请求不重发。
- 续跑前保存原配置、统计和未完成题目的字节副本到 `resume-backups/`，并写入 `resume-log.json`。已终止题目保持原文件和 SHA。写入锁防止两个进程同时使用同一输出目录，进程退出或被杀后锁由操作系统释放。
- 从 ZIP 恢复时先验证原导出校验表，随后将旧校验表归档到备份；下一次导出生成新的完整校验表，备份和恢复日志一起交付。

长期测试请固定 Git commit，不要更新程序后继续旧检查点。此功能只支持新的 **v2 行为测试 run**；之前 `aa9c58e` 版本产生的 v1 轨迹保持原样，需使用其原冻结版本检查和评阅，不能用新版续跑。完整结束的旧样例不会为了验证续跑重新调用模型。

## 保存并提交测试轨迹

```bash
python redact_bench.py check-run --run runs/my-model-smoke
python redact_bench.py export --run runs/my-model-smoke --output exports/my-model-smoke.zip
```

把 ZIP 交给项目负责人。内容包括：

- `run_config.json`：模型、非敏感 URL、采样参数、协议、代码清单及输入绑定。
- `frozen-manifest.json`：这次实际选择的题目和数据/运行器 SHA。
- `run-binding.json`：v2 原配置及冻结清单的 SHA，防止修改配置后意外接着旧轨迹运行。
- `trajectories/<batch>/<case>.json`：每轮原始动作文本、可见观察哈希、实际工具结果、协议错误、时间、状态快照、图片绑定、用量和延迟。
- `execution-summary.json`：执行覆盖、终止状态和调用统计，不包含语义成绩。
- `resume-log.json`、`resume-backups/`：若发生续跑，包含恢复记录、原未完成轨迹及原配置/校验表快照。
- `trace-integrity.json`、`replay-verification.json`：导出文件校验和回放检查。

已揭示观察可以从冻结初始状态和每轮动作/工具结果无损重建；`check-run` 会逐轮重建观察及完整模型 prompt，并核对 SHA、动作解析、工具结果和最终状态。ZIP 不含 API key。`runs/`、`output/`、`exports/` 已被 Git 忽略。

## 负责人：统一评测轨迹

将 ZIP 解压到独立目录后先执行 `check-run`。必须使用相同 `SHA256SUMS.json` 版本的数据包，不能把旧轨迹套在新输入上。

```bash
python redact_bench.py evaluate --run runs/received-run --output output/received-review --prepare
```

这一步只做 CPU 回放、成本统计、生成 `judge-inputs/` 和空白 `templates/`，不调用模型裁判，不自动给分。负责人阅读真实文本、对象、权限、完成状态与时间后，将审核结果填写到 `judgments/` 下对应路径；然后执行：

```bash
python redact_bench.py evaluate --run runs/received-run --output output/received-review
```

输出六维质量总分、GCR、严格 TSR、LCR、Efficiency、调用次数及覆盖率。`--partial` 可汇总不完整审核，但不会给未审项目补零。评分口径见 [EVALUATION.md](EVALUATION.md)。入口上的“负责人”是协作分工，不是本地访问控制；同伴持有沙盒控制器文件，但只有你确认的评阅结果作为正式交付。

## 数据与协议

`data/` 含 `visible/hidden/rubrics/runtime/variants/trajectories/assets` 等必要文件。数据、运行器、图片和参考轨迹保持原 SHA；发布清单经过重新整理，移除了来源映射、历史构造材料和离线答案页，分发清单 SHA 因而不同，原始入口 SHA 保存在 `release.json`。

所有任务通过同一个 CLI 运行；每题工具说明由该题观察提供。历史题存在 `COMMIT.operations` 和独立 `WRITE/PATCH/OPERATE` 两种协议，`WAIT` 参数也以题目说明为准。测试包保留这些既有协议，不改变题意和旧版本绑定。

模型只接收已揭示观察、历史交互和已揭示图片，不接收隐藏世界、评分准则、未来事件、配对差异说明或参考轨迹。真实平台不会被操作。当前是 development 数据；`formal_evaluation_ready=false`，人审、难度和裁判校准尚未完成。原始帖子、身份/来源映射、历史模型成绩、模型权重和本机服务均未包含。

`tools/refresh_from_source.py --source SOURCE_REPO` 用于在包含当前客户端代码、但尚无数据和 release.json 的脚手架中重新导出数据；`tools/freeze_inventory.py` 冻结文件清单。已有冻结包不应修改后继续用于同一轮测试。仓库入口为 [RedActBench](https://github.com/qywMichelle/RedActBench)。
