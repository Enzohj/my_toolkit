"""test/benchmark.py

对 `my_toolkit.benchmark` 的最小可运行测试脚本。
"""

from __future__ import annotations

import contextlib
import io
import time
import unittest
from pathlib import Path
import sys
import importlib


def _import_module():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root.parent))
    return importlib.import_module("my_toolkit.benchmark")


bench_mod = _import_module()


def inc(x: int) -> int:
    return x + 1


def slow(x: int) -> int:
    time.sleep(0.02)
    return x


class TestBenchmark(unittest.TestCase):
    def test_basic_report_structure(self):
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            report = bench_mod.benchmark(
                inc,
                [1, 2, 3],
                concurrency=2,
                repeat=2,
                timeout=None,
                executor_type="thread",
                show_progress=False,
            )

        self.assertEqual(report["total_requests"], 6)
        self.assertEqual(report["data_size"], 3)
        self.assertEqual(report["repeat"], 2)
        self.assertIn("latency_stats", report)
        self.assertEqual(report["results"], [2, 3, 4])

    def test_empty_data_fast_path(self):
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            report = bench_mod.benchmark(inc, [], concurrency=1, repeat=1, show_progress=False)
        self.assertEqual(report["total_requests"], 0)
        self.assertEqual(report["results"], [])

    def test_invalid_executor_type(self):
        with self.assertRaises(ValueError):
            bench_mod.benchmark(inc, [1], executor_type="bad", show_progress=False)

    def test_timeout_count(self):
        # 注意：这里的 timeout 仅做“标记”，不会中断实际执行
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            report = bench_mod.benchmark(
                slow,
                [1, 2, 3, 4],
                concurrency=4,
                repeat=1,
                timeout=0.001,
                executor_type="thread",
                show_progress=False,
            )
        self.assertEqual(report["timeout_count"], report["total_requests"])
        self.assertEqual(report["success_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

