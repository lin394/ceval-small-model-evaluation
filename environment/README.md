# 组员运行环境安装说明

本目录随项目一起复制或克隆。安装脚本、依赖版本和模型校验清单都在这里。首次安装需要联网下载依赖和模型，安装完成后可以离线运行推理和正式题单。

## 1 准备软件

- 使用 **64 位 Windows 10 或 11、Python 3.11 和 Git**。可以使用现有 Conda 环境的 Python，也可以单独安装 Python 3.11。先运行 `python --version` 和 `git --version` 检查命令是否可用。
- 正式基线使用 **NVIDIA GPU、CUDA 和 FP16**。运行 `nvidia-smi` 检查显卡和驱动。新建环境使用 PyTorch 2.11.0 的 CUDA 12.8 wheel，自带所需的 CUDA 运行库。没有 NVIDIA GPU 的组员可用 CPU 验证模型加载，并在组内共用 CUDA 机器运行正式对照。
- 建议项目所在磁盘预留 **10 GB**，用于模型、PyTorch、虚拟环境和安装缓存。安装默认写入项目目录，不需要管理员权限。
- 包安装可直接使用 Python 自带的 pip。电脑已装 uv 时，脚本会优先用 uv 并复用项目内的下载缓存。

参考 [Python 3.11 安装包](https://www.python.org/downloads/windows/) 和 [PyTorch 2.11.0 官方安装索引](https://pytorch.org/get-started/previous-versions/#v2110)。

## 2 选择一种方式安装

在项目根目录打开 PowerShell，按本机情况选择一条命令。

**已有可用的 CUDA 版 PyTorch**

```powershell
# 将路径换成自己的 Conda 或已有 Python 环境
.\environment\install.ps1 -Python "D:\Anaconda3\envs\warehouse-gpu\python.exe" -ReuseTorch
```

脚本会检查 PyTorch 能否调用 CUDA。新增依赖安装在本项目的 `environment/.runtime/.qwen-deps/`，原 Python 环境继续提供 PyTorch。

**还没有 PyTorch**

```powershell
.\environment\install.ps1 -Python python
```

脚本会在 `environment/.runtime/cuda/.venv/` 中新建环境，安装 `torch==2.11.0+cu128` 和 `requirements.txt` 中的依赖。若 `python` 命令指向其他版本或 Microsoft Store，改用 Python 3.11 的 `python.exe` 完整路径。

**没有 NVIDIA GPU，只做本地试跑**

```powershell
.\environment\install.ps1 -Python python -Device cpu
```

CPU 模式安装 `torch==2.11.0+cpu`。使用已有的 CPU 版 PyTorch 时，也可同时指定 `-ReuseTorch` 和已有解释器路径。

三个方式都会安装 Transformers 4.57.6、NumPy 1.26.4、PyArrow 22.0.0 等依赖，并按 `model.json` 从 Qwen 官方仓库获取固定版本模型。模型写入项目的 `models/Qwen2.5-0.5B-Instruct/`，模型权重约 0.99 GB。安装会校验每个文件的 SHA-256，已有且校验通过的文件直接复用。下载受限时，可以先从组员处复制完整的模型目录到上述位置，再执行安装。 [Qwen 官方模型版本](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/tree/7ae557604adf67be50417f59c2c2f167def9a775)

## 3 验收和复跑

先确认模型联网安装后的离线推理可用。

```powershell
.\environment\run.ps1
```

正常时会输出设备、运行精度和回答。默认问题是“中国的首都是哪里？”，预期输出“北京”。然后由有 CUDA 的组员运行正式入口的 5 题验收。

```powershell
.\environment\run.ps1 evaluate_ceval.py --variant strict-prompt --smoke --owner "姓名"
```

检查终端输出的目录，其中应有 `config.json`、5 条逐题记录的 `predictions.jsonl` 和 `summary.json`。正式跑固定 200 道题时去掉 `--smoke`。

```powershell
.\environment\run.ps1 evaluate_ceval.py --variant strict-prompt --owner "姓名"
```

固定题单、答案和清单已随项目提供，基线直接从 `data/ceval/` 读取。各方向可用同一个 `run.ps1` 运行自己的 Python 入口，在命令后填写脚本路径和参数。正式比较时记录实际的 PyTorch 版本、设备和精度，同一项对照在同一套环境中完成。

## 常见问题

| 现象 | 处理 |
|---|---|
| PowerShell 禁止运行脚本 | 如果电脑允许，可在当前终端执行 `Set-ExecutionPolicy -Scope Process Bypass` 后重试。 |
| 安装时提示 CUDA unavailable | 用 `nvidia-smi` 检查驱动，再检查所选解释器的 PyTorch 是否为 CUDA 版。已有 CPU 版 PyTorch 时可去掉 `-ReuseTorch` 新建 CUDA 环境，或先用 CPU 模式验收。 |
| 下载中断或模型校验失败 | 检查网络后重新运行安装命令。校验通过的文件会自动跳过。 |
| 换电脑、移动目录或更换 Python | 在新路径重新执行安装。运行脚本读取当前电脑的本地安装记录。 |

`environment/.runtime/` 和 `models/` 是每台机器的本地安装产物，由 Git 忽略。共享这个目录时只分发安装文件和依赖清单。
