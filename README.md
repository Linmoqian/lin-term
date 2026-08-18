# lin-term

Python 终端语义语言包 V1：业务代码描述事件，模块赋予视觉语义。

```python
from lin_term import term

term.stage("RT2 Analysis")
term.metric("cells", 48)
term.result("Dr", 0.0321, "rad²/s")
term.warn("Too few turning events", cell=18)
term.success("Analysis completed")
```

而不是：

```python
print("cells:", cells)
print("Dr:", Dr)
```

## 设计原则

> 程序负责表达事件，Terminal Language 负责赋予事件视觉语义。

- 业务代码**不出现颜色名**，只出现语义：`success` / `warn` / `result` ...
- 颜色表达状态，符号表达类型，缩进表达层级；去掉颜色仍然可读
- 80% 灰白、20% 彩色的克制基调

## 安装

```bash
pip install -e ./lin-term        # 开发安装（本仓库内）
pip install lin-term             # 或从任意项目安装
```

## API（10 个核心行为）

| 接口 | 符号 | 颜色 | 语义 |
|---|---|---|---|
| `stage(message)` | ▶ | bold blue | 大阶段开始（分隔线） |
| `step(message, **ctx)` | → | blue | 阶段内操作步骤 |
| `info(message, **ctx)` | ● | white | 普通信息 |
| `metric(name, value, unit="")` | │ | cyan | 中间指标 |
| `result(name, value, unit="")` | ◆ | bold cyan | 核心结果 |
| `success(message, **ctx)` | ✓ | green | 成功 |
| `warn(message, **ctx)` | ⚠ | yellow | 可继续的异常 |
| `error(message, **ctx)` | ✗ | bold red | 失败（不自动 raise） |
| `debug(message, **ctx)` | ◇ | dim magenta | 诊断信息，**默认关闭** |
| `exception()` | 面板 | — | 在 except 块输出 traceback（debug 时含 locals） |

辅助：`set_debug(enabled=True)` 开关调试模式；所有接口的上下文参数统一 `key=value` 形式（为未来结构化日志保留形状）。

## 数值格式化

`metric` / `result` / 上下文值统一格式化：

- 整数原样（`12842`）
- 浮点按量级：`0.032948`、`1.2048e-06`
- `NaN` / `Inf` / `-Inf` 大写明确
- numpy 数组摘要为 `ndarray(48, 12842, 2) float64`，避免整数组刷屏
- 其余类型原样 `str()`

## 调试模式

```python
term.set_debug(True)
# 或接入参数
parser.add_argument("--debug", action="store_true")
term.set_debug(args.debug)
```

`python run_analysis.py` 只显示语义输出；`--debug` 时额外显示 `◇` 诊断行，且 `exception()` 面板带局部变量。

## 演示

```bash
python lin-term/examples/demo.py          # 普通模式
python lin-term/examples/demo.py --debug  # 调试模式
```

## V1 边界（明确不做）

JSON 日志、文件日志、网络日志、log rotation、多进程/异步 logger、进度条、Dashboard/Web UI、插件系统、配置化主题、自定义 formatter DSL。

## 路线图

V1 语义终端 → V1.5 Timer/Scope/Progress → V2 文件日志 → V2.5 结构化 JSON → V3 框架适配层。