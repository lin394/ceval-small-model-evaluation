---
name: ceval-team-workflow
description: Apply the C-Eval course team's boundaries when editing this repository, implementing directions A through D, running evaluations, or preparing Git commits and pull requests. Use the assigned direction to scope changes and preserve the shared evaluation protocol.
---

# C-Eval 组内协作边界

## 开工前

在项目根目录检查 `git status --short --branch`，读根目录 `README.md` 的协作规则。根据需求或当前实验分支确定成员方向。若两者矛盾，先核实；若方向不明，继续只读检查，在涉及归属的改动前确认。保留已有的暂存和未提交改动，包括同一文件里与本次任务无关的修改。

| 方向 | 实验分支 | 可写目录 |
|---|---|---|
| A 提示词设计 | `exp/a/<task>` | `experiments/A_prompt/`、`analysis/A_prompt/` |
| B 少样本示例 | `exp/b/<task>` | `experiments/B_few_shot/`、`analysis/B_few_shot/` |
| C 自检与修正 | `exp/c/<task>` | `experiments/C_self_check/`、`analysis/C_self_check/` |
| D 多次生成与答案选择 | `exp/d/<task>` | `experiments/D_multi_generation/`、`analysis/D_multi_generation/` |

## 文件与分支边界

- 实验任务的代码、配置、测试和分析都放在对应的两个目录中。可读取公共代码、复用现有接口、写入被 Git 忽略的运行输出目录 `runs/`。已有的 `D_batch_inference` 是历史目录，D 的新工作使用 `D_multi_generation`。
- 公共推理、评分、题单、环境依赖和仓库规则的变更走独立的 `common/<task>` 分支与 PR。实验遇到公共接口缺口时，先完成范围内能做的部分，并说明需要哪一项公共变更。只有任务已授权公共变更时才实施，分支名称本身不提供授权。
- 安装或切换环境按 `environment/README.md` 操作。优先复用已验证的解释器和 PyTorch，项目依赖单独安装。成员实验引入需要全组安装的依赖时，按公共变更处理。

## 保持实验可比

- 正式对照复用 `evaluate_ceval.py --variant strict-prompt` 的共享基线、Qwen2.5-0.5B-Instruct 固定版本以及 `data/ceval/` 的题目、答案、清单。基线与对应方案用同一台机器、同一题单和同一评分规则，仅改变本项研究因素。联调可用 `--smoke`，正式结果使用完整固定题单。
- 参考答案只在评分时使用。A 只改提示词，保持现有解析规则。B 的示例来自评测子集之外，记录来源、数量和顺序并排除重复题。C 的自检输入只使用题目、模型作答及允许的上下文。D 的选择或投票只使用模型生成结果，先确定采样次数、无效输出与平票处理规则，并记录调用次数和代价。
- 保留原始输出及每题状态。无法提取唯一最终选项按共享规则计错并计入分母。发现公共评分或题单错误时，记录影响并走公共 PR，按一致口径重评受影响的配置。结果只能来自实际运行，失败和负结果照实报告。

## 提交与验收

- 模型权重、环境和缓存、原始数据下载、逐题日志和凭据留在 Git 之外。提交小型分析与复现记录，注明实验编号、基线 commit、配置、命令和原始结果位置。单个 Git 文件不得超过 5 MiB。
- 提交前核对工作区、暂存区和分支。按路径暂存本次文件，运行项目的提交检查。使用 `tools/check_repo.py --staged` 时，须在合法任务分支上以 Python 执行。保留 Git 钩子和 CI，检查失败时修复原因。
- 在已授权的范围内提交或推送任务分支。通过 PR 合并到 `main`，遵守 README 里的审核及状态检查要求。直接更新 `main`、强推、绕过检查和覆盖他人改动均超出常规实验任务范围。
- 完成后说明改动文件、运行命令、实测结果与未验证项。公共评测改动至少尝试严格基线的 5 题验收；没有 CUDA 或必要文件时，记录缺失条件及可复跑命令。
