"""lin-term 演示脚本：覆盖全部 10 个语义接口与数值格式化规则。

用法:
    python examples/demo.py            # 普通模式（debug 关闭）
    python examples/demo.py --debug    # 调试模式（debug 开启，exception 带 locals）
"""

from __future__ import annotations

import argparse

import numpy as np

from lin_term import term


def demo_normal() -> None:
    """模拟一个真实科研分析流程（普通模式）。"""

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

    term.step("Calculating rotational dynamics")
    dr = 0.0329482384234
    tau = 4.8217

    term.result("Dr", dr, "rad²/s")
    term.result("tau_turn", tau, "s")
    term.result("omega", 1.20482738492384e-06, "rad/s")

    term.debug(
        "Curve fitting parameters",
        p0=[0.1, 3.0],
        bounds=(0, 10),
        threshold=0.35,
    )

    term.info(
        "Fitting diagnostics",
        shape=data.shape,
        dtype=data.dtype,
        bad_values=float("nan"),
        max_abs=float("inf"),
    )

    term.warn(
        "Too few turning events",
        cell=18,
        events=2,
    )

    term.success(
        "Analysis completed",
        cells=48,
        valid=46,
    )


def demo_exception() -> None:
    """exception() 演示：traceback 面板（debug 模式含局部变量）。"""

    term.step("Running an operation that will fail")

    data = np.array([np.nan, 1.0, 2.0])

    try:
        if np.isnan(data).any():
            raise ValueError("array must not contain NaNs")
    except ValueError:
        term.exception()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="开启调试输出")
    args = parser.parse_args()

    term.set_debug(args.debug)

    demo_normal()
    demo_exception()

    term.stage("Done")


if __name__ == "__main__":
    main()