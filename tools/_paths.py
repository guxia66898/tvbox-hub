"""tools 脚本的公共路径基座：无论从哪个目录运行都指向项目根。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DIST = os.path.join(ROOT, "dist")
HISTORY = os.path.join(ROOT, "history")
SEEDS = os.path.join(ROOT, "seeds")


def p(*parts: str) -> str:
    """拼出项目根下的绝对路径。"""
    return os.path.join(ROOT, *parts)


def dist(*parts: str) -> str:
    return os.path.join(DIST, *parts)


def history(*parts: str) -> str:
    return os.path.join(HISTORY, *parts)


def seeds(*parts: str) -> str:
    return os.path.join(SEEDS, *parts)
