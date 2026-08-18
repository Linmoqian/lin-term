"""lin-term 演示脚本：覆盖全部 10 个语义接口与数值格式化规则。

用法:
    python examples/demo.py            # 普通模式（debug 关闭）
    python examples/demo.py --debug    # 调试模式（debug 开启，exception 带 locals）
"""

from __future__ import annotations

import argparse

import numpy as np

from lin_term import term


def demo_dataset() -> np.ndarray:
    """阶段一：加载数据——stage / step / metric / info / debug。"""

    term.stage("RT2 Analysis")

    term.step("Loading dataset")
    data = np.random.default_rng(0).normal(size=(48, 12842, 2)) * 0.1

    term.metric("cells", 48)
    term.metric("frames", 12842)
    term.metric("dt", 0.1, "s")

    term.info(
        "Processing cell",
        cell=18,
        frames=2381,
    )

    # debug 默认关闭：普通模式不显示，--debug 时才输出
    term.debug(
        "Trajectory properties",
        shape=data.shape,
        dtype=data.dtype,
    )

    return data


def demo_analysis(data: np.ndarray) -> None:
    """阶段二：旋转动力学——step / debug / result / error / warn / success。"""

    term.stage("Rotational Dynamics")

    term.step("Curve fitting")

    # 含方括号的值已自动转义，不会破坏输出
    term.debug(
        "Fitting parameters",
        p0=[0.1, 3.0],
        bounds=(0, 10),
        threshold=0.35,
    )

    term.result("Dr", 0.0329482384234, "rad²/s")
    term.result("tau_turn", 4.8217, "s")
    term.result("omega", 1.20482738492384e-06, "rad/s")

    # error 只输出错误，不自动 raise，程序可以继续
    term.error(
        "Curve fitting failed",
        cell=3,
        reason="singular matrix",
    )
    term.info("Skipping cell", cell=3)

    term.warn(
        "Too few turning events",
        cell=18,
        events=2,
    )

    # numpy 标量 / NaN / Inf 自动格式化
    term.info(
        "Fit diagnostics",
        r2=np.float64(0.9821),
        bad_values=float("nan"),
        max_abs=float("inf"),
        shape=data.shape,
    )

    term.success(
        "Analysis completed",
        cells=48,
        valid=46,
    )


def demo_formatting() -> None:
    """数值格式化规则一览（metric 与 result 共用同一格式化器）。"""

    term.stage("Value Formatting")

    term.metric("int", 12842)
    term.metric("float", 0.0329482384234)
    term.metric("sci", 1.20482738492384e-06, "rad/s")
    term.metric("zero", 0.0)
    term.metric("nan", float("nan"))
    term.metric("inf", float("inf"), "s")
    term.metric("neg_inf", float("-inf"))
    term.metric("bool", True)
    term.metric("tuple", (0, 10))
    term.metric("array", np.array([[1.0, 2.0], [3.0, 4.0]]))
    term.metric("complex", np.complex128(0.1 + 0.2j))


def demo_exception() -> None:
    """exception() 演示：traceback 面板（debug 模式含局部变量）。"""

    term.stage("Exception")

    term.step("Running an operation that will fail")

    data = np.array([np.nan, 1.0, 2.0])

    try:
        if np.isnan(data).any():
            raise ValueError("array must not contain NaNs")
    except ValueError:
        term.exception()


def demo_interactive() -> None:
    """交互演示：input / select（青色交互提示）。

    无交互终端（重定向 / CI / 管道）时自动返回默认值，不会阻塞。
    """

    term.stage("Interactive")

    output = term.input("Enter output filename", default="results.csv")
    term.info("Output file", path=output)

    model = term.select(
        "Choose fitting model",
        ["exponential", "power", "sinusoid"],
        default="exponential",
    )
    term.result("model", model)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="开启调试输出")
    args = parser.parse_args()

    term.set_debug(args.debug)

    data = demo_dataset()
    demo_analysis(data)
    demo_formatting()
    demo_exception()
    demo_interactive()

    term.stage("Done")


if __name__ == "__main__":
    main()