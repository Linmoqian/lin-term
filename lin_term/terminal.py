"""终端语义语言核心：Terminal 类与视觉主题。

三层分离：业务代码只调用语义接口（stage / info / result ...），
颜色、符号、对齐全部收敛在本模块的表现层。
"""

from __future__ import annotations

import math
import numbers
import os
import select
import sys
import termios
import tty
from typing import Any, Iterable, Iterator

from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Prompt
from rich.theme import Theme


# 视觉映射：对齐全局工程规范（颜色表达状态，符号表达类型）。
# 绿=成功 黄=警告 红=错误 青=交互提示 蓝=高亮 灰=次要信息；
# 去掉颜色后，标签与符号（[info] ▶ → ● │ ◆ ✓ ⚠ ✗ ◇）仍能完整表达语义。
TERMINAL_THEME = Theme(
    {
        # 状态三色
        "success": "green",
        "warn": "yellow",
        "error": "bold red",
        # 高亮与进行（蓝）
        "stage": "bold blue",
        "step": "blue",
        "result.name": "bold blue",
        "result.value": "bold white",
        "result.unit": "dim",
        # 次要信息（灰）
        "info": "grey70",
        "metric.name": "grey70",
        "metric.value": "white",
        "metric.unit": "dim",
        "debug": "grey50",
        "context.key": "dim grey70",
        "context.value": "dim grey70",
        # 交互提示（青）
        "input": "cyan",
        "select": "cyan",
        "select.option": "grey70",
        "select.highlight": "bold cyan",
        "select.value": "white",
        # 进度（进行中=蓝，完成由 BarColumn finished_style 转绿）
        "progress": "blue",
        "progress.percentage": "white",
        "progress.download": "dim",
        # 文本标签与语义同色：标签 + 符号 + 消息三段同色，扫视更直接
        "tag.stage": "bold blue",
        "tag.step": "blue",
        "tag.info": "grey70",
        "tag.metric": "grey70",
        "tag.result": "bold blue",
        "tag.success": "green",
        "tag.warn": "yellow",
        "tag.error": "bold red",
        "tag.debug": "grey50",
        "tag.input": "cyan",
        "tag.select": "cyan",
        "tag.progress": "blue",
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
    "input": "[input]",
    "select": "[select]",
    "progress": "[progress]",
}


class _ProgressTask:
    """进度条句柄：progress() 返回的轻量对象，绑定一个 rich 任务。"""

    def __init__(self, progress: Progress, task_id: int):
        self._progress = progress
        self._task_id = task_id
        self._progress.start()

    def advance(self, advance: float = 1.0) -> None:
        """推进进度（默认 1 步）。"""
        self._progress.advance(self._task_id, advance)

    def update(
        self,
        *,
        completed: float | None = None,
        total: float | None = None,
        description: str | None = None,
    ) -> None:
        """直接设置进度/总量/描述；描述文本会自动转义。"""
        fields: dict[str, Any] = {}
        if completed is not None:
            fields["completed"] = completed
        if total is not None:
            fields["total"] = total
        if description is not None:
            fields["description"] = escape(description)
        self._progress.update(self._task_id, **fields)

    def __enter__(self) -> _ProgressTask:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self._progress.stop()


class Terminal:
    """终端语义语言入口。每个进程共享一个实例：``from lin_term import term``。"""

    def __init__(self, *, debug: bool = False):
        self.console = Console(theme=TERMINAL_THEME)
        self.debug_enabled = debug

    def set_debug(self, enabled: bool = True) -> None:
        self.debug_enabled = enabled

    # ---- 阶段与操作 ----

    def stage(self, message: str) -> None:
        """一个大的程序阶段开始：空行 + 蓝色标题。不输出装饰性分隔线。"""
        self.console.print()
        self.console.print(
            f"[tag.stage]{escape(TAG_TEXT['stage'])}[/tag.stage] "
            f"[stage]▶ {escape(message)}[/stage]"
        )

    def step(self, message: str, **context: Any) -> None:
        """阶段内部的一个操作步骤。"""
        self._line("step", "→", message, **context)

    def info(self, message: str, **context: Any) -> None:
        """普通信息，程序的背景声音，不抢视觉注意力。"""
        self._line("info", "●", message, **context)

    # ---- 进度 ----

    def progress(self, description: str, *, total: int | None = None) -> _ProgressTask:
        """实时进度条（进行中=蓝，完成=绿）。

        TTY 下原地刷新一行（与 step 同语义色）；非 TTY（管道 / 重定向 / CI）
        静默不渲染、任务照常推进，保证输出稳定可日志化。

        用法:
            with term.progress("Analyzing cells", total=48) as bar:
                for cell in cells:
                    bar.advance()
        """
        progress = Progress(
            TextColumn(
                f"[tag.progress]{escape(TAG_TEXT['progress'])}[/tag.progress] "
                "[progress]{task.description}[/progress]",
                justify="left",
            ),
            BarColumn(
                bar_width=24,
                style="grey37",
                complete_style="bold blue",
                finished_style="green",
            ),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self.console,
        )
        task_id = progress.add_task(escape(description), total=total)
        return _ProgressTask(progress, task_id)

    def track(
        self,
        sequence: Iterable[Any],
        description: str,
        *,
        total: int | None = None,
    ) -> Iterator[Any]:
        """遍历序列并显示进度条（progress 的便捷形态，循环内自动推进）。

        total 缺省时尝试取 len(sequence)，不可取则显示为不确定进度。
        """
        if total is None:
            try:
                total = len(sequence)  # type: ignore[arg-type]
            except (TypeError, AttributeError):
                total = None

        with self.progress(description, total=total) as bar:
            for item in sequence:
                yield item
                bar.advance()

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

    def input(self, prompt: str, *, default: str | None = None) -> str | None:
        """等待用户输入自由文本（交互提示，青色）。

        无交互终端（重定向 / CI / 管道）时不阻塞，直接返回 default；
        Ctrl+C 由调用方决定是否捕获。
        """
        if not self.console.is_terminal:
            return default

        suffix = f" [dim](default: {escape(str(default))})[/dim]" if default is not None else ""
        answer = Prompt.ask(
            f"[tag.input]{escape(TAG_TEXT['input'])}[/tag.input] "
            f"[input]? {escape(prompt)}[/input]{suffix}"
        )
        return answer if answer else default

    def select(
        self,
        prompt: str,
        choices: list[str],
        *,
        default: str | None = None,
    ) -> str | None:
        """方向键菜单：给定选项后用 ↑/↓ 移动高亮、Enter 确认（交互提示，青色）。

        - 初始高亮停在 default 所在项；
        - ↑/↓ 循环移动，Enter 确认；q / Esc 取消返回 None；Ctrl+C 抛出（调用方可捕获）；
        - 无交互终端（重定向 / CI / 管道）时不阻塞，直接返回 default。
        - 仅支持 POSIX（macOS / Linux）；非 POSIX 平台直接返回 default。
        """
        choices = [str(choice) for choice in choices]
        if not choices:
            return default

        if not self.console.is_terminal or os.name != "posix":
            return default

        index = 0
        if default is not None and str(default) in choices:
            index = choices.index(str(default))
        height = len(choices)

        self.console.print(
            f"[tag.select]{escape(TAG_TEXT['select'])}[/tag.select] "
            f"[select]? {escape(prompt)}[/select] "
            f"[dim](↑/↓ 选择, Enter 确认, q 取消)[/dim]"
        )
        self._draw_menu(choices, index)

        fd = sys.stdin.fileno()
        old_attrs = termios.tcgetattr(fd)
        try:
            # TCSADRAIN 而非默认的 TCSAFLUSH：不丢弃切换前已排队的按键输入
            tty.setraw(fd, termios.TCSADRAIN)
            while True:
                key = self._read_key(fd)
                if key == "up":
                    index = (index - 1) % height
                elif key == "down":
                    index = (index + 1) % height
                elif key == "enter":
                    break
                elif key in ("cancel", "escape"):
                    self._clear_menu(height)
                    self.console.print(
                        f"[tag.select]{escape(TAG_TEXT['select'])}[/tag.select] "
                        f"[select]? {escape(prompt)}[/select]: "
                        f"[dim](cancelled)[/dim]"
                    )
                    return None
                else:
                    continue
                self._redraw_menu(choices, index, height)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)

        self._clear_menu(height)
        chosen = choices[index]
        self.console.print(
            f"[tag.select]{escape(TAG_TEXT['select'])}[/tag.select] "
            f"[select]? {escape(prompt)}[/select]: "
            f"[select.value]{escape(chosen)}[/select.value]"
        )
        return chosen

    def _draw_menu(self, choices: list[str], index: int) -> None:
        """首次绘制选项列表，光标停在列表末行（与 _redraw/_clear 约定一致）。"""
        for i, choice in enumerate(choices):
            if i == index:
                self.console.print(f"  [select.highlight]❯ {escape(choice)}[/select.highlight]")
            else:
                self.console.print(f"  [select.option]  {escape(choice)}[/select.option]")

    def _redraw_menu(self, choices: list[str], index: int, height: int) -> None:
        """按键后整块重绘：光标在末行→上行到首行，逐行清写，光标回到末行。"""
        self.console.file.write(f"\x1b[{height}A")
        for i, choice in enumerate(choices):
            self.console.file.write("\x1b[2K")
            if i == index:
                line = f"  [select.highlight]❯ {escape(choice)}[/select.highlight]"
            else:
                line = f"  [select.option]  {escape(choice)}[/select.option]"
            self.console.print(line)
        self.console.file.flush()

    def _clear_menu(self, height: int) -> None:
        """清除提示行与选项列表：光标在末行→上行到提示行，逐行清除。"""
        self.console.file.write(f"\x1b[{height}A")
        for i in range(height + 1):
            self.console.file.write("\x1b[2K")
            if i < height:
                self.console.file.write("\r\n")
        self.console.file.flush()

    def _read_key(self, fd: int) -> str:
        """raw mode 下读一个按键：方向键识别为转义序列。"""
        first = os.read(fd, 1)
        if first == b"\x1b":
            ready, _, _ = select.select([fd], [], [], 0.15)
            if ready:
                rest = os.read(fd, 2)
                if rest in (b"[A", b"[B", b"[C", b"[D"):
                    return {b"[A": "up", b"[B": "down", b"[C": "right", b"[D": "left"}[rest]
            return "escape"
        if first in (b"\r", b"\n"):
            return "enter"
        if first == b"\x03":
            raise KeyboardInterrupt
        if first in (b"q", b"Q"):
            return "cancel"
        return "ignore"

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