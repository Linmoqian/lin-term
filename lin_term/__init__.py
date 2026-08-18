"""lin-term：Python 终端语义语言包 V1。

设计原则：业务代码描述事件（success / warn / result ...），
本包负责符号、颜色、对齐等全部表现层细节。

用法::

    from lin_term import term

    term.stage("RT2 Analysis")
    term.result("Dr", 0.0321, "rad²/s")
"""

from lin_term.terminal import Terminal

term = Terminal()

__all__ = ["Terminal", "term"]