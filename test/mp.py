"""test/mp.py

对 `my_toolkit.mp.apply_parallel` 的最小可运行测试脚本。
"""

from __future__ import annotations

import unittest
from pathlib import Path
import sys
import importlib


def _import_module():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root.parent))
    return importlib.import_module("my_toolkit.mp")


mp_mod = _import_module()


def add(a: int, b: int) -> int:
    return a + b


class TestApplyParallel(unittest.TestCase):
    def test_thread_keeps_order(self):
        out = mp_mod.apply_parallel(range(10), lambda x: x * x, method="thread", show_progress=False)
        self.assertEqual(out, [i * i for i in range(10)])

    def test_call_func_unpacking(self):
        items = [(1, 2), (3, 4)]
        out = mp_mod.apply_parallel(items, add, method="thread", show_progress=False)
        self.assertEqual(out, [3, 7])

        items2 = [{"a": 1, "b": 2}, {"a": 10, "b": 20}]
        out2 = mp_mod.apply_parallel(items2, add, method="thread", show_progress=False)
        self.assertEqual(out2, [3, 30])

    def test_generator_iterable(self):
        out = mp_mod.apply_parallel((i for i in range(5)), lambda x: x + 1, method="thread", show_progress=False)
        self.assertEqual(out, [1, 2, 3, 4, 5])

    def test_invalid_method(self):
        with self.assertRaises(ValueError):
            mp_mod.apply_parallel([1, 2], lambda x: x, method="bad", show_progress=False)

    def test_error_policy_store(self):
        def f(x: int) -> int:
            if x == 2:
                raise ValueError("boom")
            return x

        out = mp_mod.apply_parallel([1, 2, 3], f, method="thread", show_progress=False, error_policy="store")
        self.assertEqual(out[0], 1)
        self.assertIsInstance(out[1], Exception)
        self.assertEqual(out[2], 3)

    def test_error_policy_ignore(self):
        def f(x: int) -> int:
            if x == 2:
                raise ValueError("boom")
            return x

        out = mp_mod.apply_parallel([1, 2, 3], f, method="thread", show_progress=False, error_policy="ignore")
        self.assertEqual(out, [1, None, 3])

    def test_error_policy_raise(self):
        def f(x: int) -> int:
            if x == 2:
                raise ValueError("boom")
            return x

        with self.assertRaises(RuntimeError):
            mp_mod.apply_parallel([1, 2, 3], f, method="thread", show_progress=False, error_policy="raise")


if __name__ == "__main__":
    unittest.main(verbosity=2)

