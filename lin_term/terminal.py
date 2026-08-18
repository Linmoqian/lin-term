"""终端语义语言核心：Terminal 类与视觉主题。

三层分离：业务代码只调用语义接口（stage / info / result ...），
颜色、符号、对齐全部收敛在本模块的表现层。
"""

from __future__ import annotations

import math
import numbers
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.theme import Theme


# 视觉映射：颜色表达状态，符号表达类型，缩进表达层级。
# 去掉颜色后，符号（▶ → ● │ ◆ ✓ ⚠ ✗ ◇）仍能完整表达语义。
TERMINAL_THEME = Theme(
    {
        "stage": "bold blue",
        "step": "blue",
        "info": "white",
        "metric.name": "cyan",
        "metric.value": "white",
        "metric.unit": "dim",
        "result.name": "bold cyan",
        "result.value": "bold white",
        "result.unit": "dim",
        "success": "green",
        "warn": "yellow",
        "error": "bold red",
        "debug": "dim magenta",
        # 文本标签与语义同色：标签 + 符号 + 消息三段同色，扫视更直接
        "tag.stage": "bold blue",
        "tag.step": "blue",
        "tag.info": "white",
        "tag.metric": "cyan",
        "tag.result": "bold cyan",
        "tag.success": "green",
        "tag.warn": "yellow",
        "tag.error": "bold red",
        "tag.debug": "dim magenta",
        "context.key": "dim cyan",
        "context.value": "dim white",
    }
)


def _format_value(value: Any) -> str:
    """统一数值/值的展示格式（metric / result / context 共用）。

    - 整数原样；浮点按量级选择定点或科学计数法；
    - NaN / Inf 明确大写；
    - numpy 数组输出 shape + dtype 摘要，避免整数组刷屏。
    """

    # bool 优先于 Integral（bool 是 int 子类）
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, numbers.Integral):
        return str(value)
    if isinstance(value, numbers.Real):
        number = float(value)
        if math.isnan(number):
            return "NaN"
        if math.isinf(number):
            return "Inf" if number > 0 else "-Inf"
        if number == 0 or 1e-4 <= abs(number) < 1e5:
            return f"{number:.5g}"
        return f"{number:.4e}"

    # 不引入 numpy 硬依赖，按所属模块识别数组类型
    module = type(value).__module__.split(".")[0]
    if module == "numpy":
        shape = getattr(value, "shape", None)
        if shape == ():  # numpy 标量（如 np.complex128）
            return str(value)
        dtype = getattr(value, "dtype", None)
        if shape is not None and dtype is not None:
            return f"ndarray{shape} {dtype}"

    return str(value)


# 语义 → 文本标签：输出行前缀，与符号互补（符号扫视、颜色表状态、标签可 grep）
TAG_TEXT = {
    "stage": "[stage]",
    "step": "[step]",
    "info": "[info]",
    "metric": "[metric]",
    "result": "[result]",
    "success": "[success]",
    "warn": "[warn]",
    "error": "[error]",
    "debug": "[debug]",
}


class Terminal:
    """终端语义语言入口。每个进程共享一个实例：``from lin_term import term``。"""

    def __init__(self, *, debug: bool = False):
        self.console = Console(theme=TERMINAL_THEME)
        self.debug_enabled = debug

    def set_debug(self, enabled: bool = True) -> None:
        self.debug_enabled = enabled

    # ---- 阶段与操作 ----

    def stage(self, message: str) -> None:
        """一个大的程序阶段开始：分隔线 + 标题。只用于大分区，不应频繁出现。"""
        self.console.print()
        self.console.rule(
            f"[tag.stage]{escape(TAG_TEXT['stage'])}[/tag.stage] "
            f"[stage]▶ {escape(message)}[/stage]",
            align="left",
        )

    def step(self, message: str, **context: Any) -> None:
        """阶段内部的一个操作步骤。"""
        self._line("step", "→", message, **context)

    def info(self, message: str, **context: Any) -> None:
        """普通信息，程序的背景声音，不抢视觉注意力。"""
        self._line("info", "●", message, **context)

    # ---- 数值 ----

    def metric(self, name: str, value: Any, unit: str = "") -> None:
        """中间指标（样本量、帧数、阈值……），视觉等级低于 result。"""
        self._kv_line("│", "metric", name, value, unit)

    def result(self, name: str, value: Any, unit: str = "") -> None:
        """程序真正计算出的重要结果，视觉等级高于 metric。"""
        self._kv_line("◆", "result", name, value, unit)

    def _kv_line(self, symbol: str, role: str, name: str, value: Any, unit: str) -> None:
        line = (
            f"[tag.{role}]{escape(TAG_TEXT[role])}[/tag.{role}] "
            f"[{role}.name]{symbol} {escape(name):<18}[/{role}.name]"
            f"[{role}.value]{escape(_format_value(value))}[/{role}.value]"
        )
        if unit:
            line += f"[{role}.unit] {escape(unit)}[/{role}.unit]"
        self.console.print(line)

    # ---- 程序状态 ----

    def success(self, message: str, **context: Any) -> None:
        """操作成功完成。"""
        self._line("success", "✓", message, **context)

    def warn(self, message: str, **context: Any) -> None:
        """存在异常但程序可继续（数据不足、采用默认参数、已过滤 NaN……）。"""
        self._line("warn", "⚠", message, **context)

    def error(self, message: str, **context: Any) -> None:
        """某项操作失败。只输出错误，不自动 raise。"""
        self._line("error", "✗", message, **context)

    def debug(self, message: str, **context: Any) -> None:
        """诊断信息，默认关闭，set_debug(True) 后输出。"""
        if not self.debug_enabled:
            return
        self._line("debug", "◇", message, **context)

    def exception(self) -> None:
        """在 except 块中调用，输出 Rich traceback 面板。

        不全局替换 sys.excepthook：由业务代码在需要的地方显式调用，
        locals 是否显示随 debug 开关实时生效。
        """
        self.console.print_exception(show_locals=self.debug_enabled)

    # ---- 内部 ----

    def _line(self, role: str, symbol: str, message: str, **context: Any) -> None:
        """统一消息行：标签 + 符号 + 消息（同语义色），再带可选上下文。"""
        self.console.print(
            f"[tag.{role}]{escape(TAG_TEXT[role])}[/tag.{role}] "
            f"[{role}]{symbol} {escape(message)}[/{role}]"
        )
        self._context(**context)

    def _context(self, **kwargs: Any) -> None:
        """统一 key=value 上下文行；所有值走数值格式化。"""
        if not kwargs:
            return

        parts = []
        for key, value in kwargs.items():
            parts.append(
                f"[context.key]{escape(key)}[/context.key]="
                f"[context.value]{escape(_format_value(value))}[/context.value]"
            )
        self.console.print("  " + "  ".join(parts))