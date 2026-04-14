"""test/decorator.py

对 `my_toolkit.decorator` 的最小可运行测试脚本（timer/timeout/retry）。
"""

from __future__ import annotations

import asyncio
import time
import unittest
from pathlib import Path
import sys
import importlib


def _import_module():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root.parent))
    return importlib.import_module("my_toolkit.decorator")


decorator_mod = _import_module()


class TestTimer(unittest.TestCase):
    def test_timer_decorator_sync_preserves_name(self):
        @decorator_mod.timer
        def foo(x: int) -> int:
            return x + 1

        self.assertEqual(foo.__name__, "foo")
        self.assertEqual(foo(1), 2)

    def test_timer_context_manager_elapsed(self):
        with decorator_mod.timer("block") as t:
            time.sleep(0.02)
            self.assertGreater(t.elapsed, 0)

    def test_timer_decorator_async(self):
        @decorator_mod.timer
        async def bar(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        self.assertEqual(asyncio.run(bar(3)), 6)


class TestTimeout(unittest.TestCase):
    def test_timeout_invalid_seconds(self):
        with self.assertRaises(ValueError):
            decorator_mod.timeout(0)

    def test_timeout_sync_raises(self):
        @decorator_mod.timeout(0.05)
        def slow():
            time.sleep(0.2)
            return 1

        t0 = time.perf_counter()
        with self.assertRaises(TimeoutError):
            slow()
        self.assertLess(time.perf_counter() - t0, 1.0)

    def test_timeout_async_raises(self):
        @decorator_mod.timeout(0.05)
        async def slow_async():
            await asyncio.sleep(0.2)
            return 1

        with self.assertRaises(TimeoutError):
            asyncio.run(slow_async())


class TestRetry(unittest.TestCase):
    def test_retry_eventually_success(self):
        calls = {"n": 0}

        @decorator_mod.retry(max_attempts=3, delay=0.0)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ValueError("boom")
            return "ok"

        self.assertEqual(flaky(), "ok")
        self.assertEqual(calls["n"], 3)

    def test_retry_fail_return_default_none(self):
        calls = {"n": 0}

        @decorator_mod.retry(max_attempts=2, delay=0.0, raise_on_failure=False)
        def always_fail():
            calls["n"] += 1
            raise RuntimeError("no")

        self.assertIsNone(always_fail())
        self.assertEqual(calls["n"], 2)

    def test_retry_raise_on_failure(self):
        @decorator_mod.retry(max_attempts=2, delay=0.0, raise_on_failure=True)
        def always_fail2():
            raise KeyError("x")

        with self.assertRaises(KeyError):
            always_fail2()

    def test_retry_async_success(self):
        calls = {"n": 0}

        @decorator_mod.retry(max_attempts=3, delay=0.0)
        async def flaky_async():
            calls["n"] += 1
            if calls["n"] < 2:
                raise ValueError("boom")
            return 42

        self.assertEqual(asyncio.run(flaky_async()), 42)


if __name__ == "__main__":
    unittest.main(verbosity=2)

