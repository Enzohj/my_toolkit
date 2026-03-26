#!/usr/bin/env python3
"""
benchmark.py — 可复用的 Python 并行压测工具

功能：对指定函数在给定数据集上进行并行压测，实时显示进度条，最终生成结构化压测报告。

使用方式：
    from benchmark import benchmark, print_report

    result = benchmark(my_func, data_list, concurrency=20, repeat=3, timeout=5)
    print_report(result)

设计建议：
    - I/O 密集型场景（网络请求、文件读写等）→ executor_type="thread"
    - CPU 密集型场景（数值计算、图像处理等）→ executor_type="process"
      注意：process 模式下 func 和 data_list 元素必须可 pickle
"""

from __future__ import annotations

import math
import os
import shutil
import statistics
import sys
import threading
import time
from concurrent.futures import (
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


# ═══════════════════════════════════════════════
#  内部数据结构
# ═══════════════════════════════════════════════

@dataclass
class _TaskResult:
    """单次调用的结果记录。"""
    index: int              # 对应 data_list 的索引
    repeat_round: int       # 第几轮 repeat
    latency: float          # 耗时（秒）
    success: bool = True
    is_timeout: bool = False
    error: Optional[str] = None
    return_value: Any = None


# ═══════════════════════════════════════════════
#  模块顶层 worker（支持 ProcessPoolExecutor 的 pickle 要求）
# ═══════════════════════════════════════════════

def _run_one(func, index, item, rnd):
    """
    在 worker 中执行一次 func(item)，捕获异常并记录耗时。
    此函数定义在模块顶层，以确保 ProcessPoolExecutor 能正确序列化。
    """
    t0 = time.perf_counter()
    try:
        ret = func(item)
        latency = time.perf_counter() - t0
        return _TaskResult(
            index=index,
            repeat_round=rnd,
            latency=latency,
            success=True,
            return_value=ret,
        )
    except Exception as exc:
        latency = time.perf_counter() - t0
        return _TaskResult(
            index=index,
            repeat_round=rnd,
            latency=latency,
            success=False,
            error=str(exc),
        )


# ═══════════════════════════════════════════════
#  进度条（纯标准库实现，线程安全）
# ═══════════════════════════════════════════════

class _ProgressBar:
    """
    线程安全的终端进度条。
    实时显示：完成数/总数、已用时间、成功率、实时 QPS。
    输出到 stderr 以避免干扰 stdout 的正常输出。
    """

    def __init__(self, total):
        self.total = total
        self.completed = 0
        self.success = 0
        self.fail = 0
        self.timeout = 0
        self._lock = threading.Lock()
        self._start = time.monotonic()
        self._closed = False

    @staticmethod
    def _term_width():
        """获取终端宽度，兼容无终端环境。"""
        try:
            return shutil.get_terminal_size().columns
        except Exception:
            return 80

    def update(self, success=True, is_timeout=False):
        """每完成一个任务后调用，更新计数并重绘进度条。"""
        with self._lock:
            self.completed += 1
            if success:
                self.success += 1
            else:
                self.fail += 1
            if is_timeout:
                self.timeout += 1
            self._render()

    def _render(self):
        elapsed = time.monotonic() - self._start
        pct = self.completed / self.total if self.total else 1.0
        qps = self.completed / elapsed if elapsed > 0 else 0.0

        width = self._term_width()
        # 右侧状态信息
        info = (
            " {done}/{total}"
            " [{elapsed:.1f}s]"
            " QPS={qps:.1f}"
            " ok={ok} err={err} to={to}"
        ).format(
            done=self.completed, total=self.total,
            elapsed=elapsed, qps=qps,
            ok=self.success, err=self.fail, to=self.timeout,
        )
        # 进度条可用宽度 = 终端宽度 - 信息文本 - 方括号
        bar_max = max(width - len(info) - 2, 10)
        filled = int(bar_max * pct)
        bar = "#" * filled + "-" * (bar_max - filled)

        line = "\r[{bar}]{info}".format(bar=bar, info=info)
        sys.stderr.write(line)
        sys.stderr.flush()

    def close(self):
        """压测结束后调用，换行收尾。"""
        if not self._closed:
            sys.stderr.write("\n")
            sys.stderr.flush()
            self._closed = True


# ═══════════════════════════════════════════════
#  核心压测函数
# ═══════════════════════════════════════════════

def benchmark(
    func,           # type: Callable[[Any], Any]
    data_list,      # type: Sequence[Any]
    concurrency=10,     # type: int
    repeat=1,           # type: int
    timeout=None,       # type: Optional[float]
    executor_type="thread",  # type: str
    show_progress=True,      # type: bool
):
    """
    对 func 在 data_list 上进行并行压测，返回结构化报告字典。

    参数
    ────
    func : Callable[[Any], Any]
        待压测的可调用对象，签名为 func(item)。
        item 是 data_list 中的单个元素。
        若需传入多个参数，可在外层包装：
            benchmark(lambda args: my_func(*args), [(a,b), (c,d)])

    data_list : Sequence[Any]
        测试数据列表，每个元素作为一次 func(item) 的输入。

    concurrency : int, default=10
        并发 worker 数量。

    repeat : int, default=1
        对整个 data_list 重复压测的轮次数（≥1）。
        总调用次数 = repeat × len(data_list)。

    timeout : float | None, default=None
        单次调用的超时时间（秒）。超时视为失败。
        设为 None 表示不限时。

    executor_type : str, default="thread"
        "thread" — 线程池，适合 I/O 密集。
        "process" — 进程池，适合 CPU 密集（func 和数据须可 pickle）。

    show_progress : bool, default=True
        是否在 stderr 上实时显示进度条。

    返回
    ────
    dict，结构如下：
    {
        "total_requests": int,
        "success_count": int,
        "fail_count": int,
        "timeout_count": int,
        "total_time": float,        # 秒
        "qps": float,
        "latency_stats": {          # 单位：毫秒
            "avg": float,
            "min": float,
            "max": float,
            "p50": float,
            "p90": float,
            "p95": float,
            "p99": float,
        },
        "concurrency": int,
        "repeat": int,
        "data_size": int,
        "executor_type": str,
        "results": list,            # 与 data_list 一一对应的返回值（最后一轮）
        "errors": list[dict],       # 所有失败调用的摘要
    }
    """

    # ── 参数校验 ──
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if repeat < 1:
        raise ValueError("repeat must be >= 1")

    data_size = len(data_list)
    total_requests = data_size * repeat

    # ── 选择执行器 ──
    if executor_type == "process":
        PoolClass = ProcessPoolExecutor
    else:
        PoolClass = ThreadPoolExecutor

    task_results = []       # type: List[_TaskResult]
    progress = _ProgressBar(total_requests) if show_progress else None

    # ── 主调度 ──
    wall_start = time.perf_counter()

    with PoolClass(max_workers=concurrency) as pool:
        # 一次性提交 repeat 轮 × data_size 条任务
        future_map = {}     # type: Dict[Future, Tuple[int, int]]
        for rnd in range(repeat):
            for idx, item in enumerate(data_list):
                fut = pool.submit(_run_one, func, idx, item, rnd)
                future_map[fut] = (idx, rnd)

        # 按完成顺序收集结果
        for fut in as_completed(future_map):
            idx, rnd = future_map[fut]
            try:
                result = fut.result(timeout=timeout)
                # _run_one 内部已经捕获了 func 的异常，这里正常拿到 _TaskResult
            except Exception as exc:
                # fut.result() 超时 或 序列化异常（进程池场景）
                result = _TaskResult(
                    index=idx,
                    repeat_round=rnd,
                    latency=timeout if timeout else 0.0,
                    success=False,
                    is_timeout=True,
                    error=str(exc),
                )

            task_results.append(result)
            if progress:
                progress.update(success=result.success, is_timeout=result.is_timeout)

    wall_end = time.perf_counter()
    if progress:
        progress.close()

    total_time = wall_end - wall_start

    # ═══════════════════════════════════════════
    #  统计计算
    # ═══════════════════════════════════════════

    success_count = sum(1 for r in task_results if r.success)
    fail_count = total_requests - success_count
    timeout_count = sum(1 for r in task_results if r.is_timeout)

    # ── 延迟分位数（毫秒）──
    latencies_ms = sorted(r.latency * 1000.0 for r in task_results)

    def _percentile(sorted_data, pct):
        """第 pct 百分位（0-100），线性插值。"""
        if not sorted_data:
            return 0.0
        n = len(sorted_data)
        k = (pct / 100.0) * (n - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_data[int(k)]
        return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)

    if latencies_ms:
        latency_stats = {
            "avg": statistics.mean(latencies_ms),
            "min": latencies_ms[0],
            "max": latencies_ms[-1],
            "p50": _percentile(latencies_ms, 50),
            "p90": _percentile(latencies_ms, 90),
            "p95": _percentile(latencies_ms, 95),
            "p99": _percentile(latencies_ms, 99),
        }
    else:
        latency_stats = {k: 0.0 for k in ("avg", "min", "max", "p50", "p90", "p95", "p99")}

    qps = total_requests / total_time if total_time > 0 else 0.0

    # ── 与 data_list 一一对应的返回值列表（取最后一轮 repeat 的结果）──
    last_round = repeat - 1
    results_by_index = {}   # type: Dict[int, Any]
    for r in task_results:
        if r.repeat_round == last_round:
            results_by_index[r.index] = r.return_value if r.success else None
    results_list = [results_by_index.get(i) for i in range(data_size)]

    # ── 错误摘要 ──
    errors_summary = [
        {
            "index": r.index,
            "round": r.repeat_round,
            "error": r.error,
            "is_timeout": r.is_timeout,
            "latency_ms": round(r.latency * 1000, 2),
        }
        for r in task_results
        if not r.success
    ]

    result_dict = {
        "total_requests": total_requests,
        "success_count": success_count,
        "fail_count": fail_count,
        "timeout_count": timeout_count,
        "total_time": round(total_time, 4),
        "qps": round(qps, 2),
        "latency_stats": {k: round(v, 2) for k, v in latency_stats.items()},
        "concurrency": concurrency,
        "repeat": repeat,
        "data_size": data_size,
        "executor_type": executor_type,
        "results": results_list,
        "errors": errors_summary,
    }
    print_report(result_dict)
    return result_dict


# ═══════════════════════════════════════════════
#  格式化报告打印
# ═══════════════════════════════════════════════

def print_report(report, file=None):
    """
    将压测报告以可读文本格式打印。

    参数
    ────
    report : dict — 由 benchmark() 返回的结果字典。
    file   : IO   — 输出目标，默认 sys.stdout。
    """
    out = file or sys.stdout
    ls = report["latency_stats"]

    divider = "=" * 58

    lines = [
        "",
        divider,
        "              BENCHMARK  REPORT",
        divider,
        "",
        "  +-- Configuration -----------------------------------+",
        "  |  Concurrency     : {:<31}|".format(report["concurrency"]),
        "  |  Repeat rounds   : {:<31}|".format(report["repeat"]),
        "  |  Data size       : {:<31}|".format(report["data_size"]),
        "  |  Executor        : {:<31}|".format(report["executor_type"]),
        "  +----------------------------------------------------+",
        "",
        "  +-- Summary -----------------------------------------+",
        "  |  Total requests  : {:<31}|".format(report["total_requests"]),
        "  |  Success         : {:<31}|".format(report["success_count"]),
        "  |  Failures        : {:<31}|".format(report["fail_count"]),
        "  |  Timeouts        : {:<31}|".format(report["timeout_count"]),
        "  |  Total time      : {:<31}|".format("{:.4f}s".format(report["total_time"])),
        "  |  QPS             : {:<31}|".format("{:.2f}".format(report["qps"])),
        "  +----------------------------------------------------+",
        "",
        "  +-- Latency (ms) ------------------------------------+",
        "  |  Avg             : {:<31}|".format("{:.2f}".format(ls["avg"])),
        "  |  Min             : {:<31}|".format("{:.2f}".format(ls["min"])),
        "  |  Max             : {:<31}|".format("{:.2f}".format(ls["max"])),
        "  |  P50 (median)    : {:<31}|".format("{:.2f}".format(ls["p50"])),
        "  |  P90             : {:<31}|".format("{:.2f}".format(ls["p90"])),
        "  |  P95             : {:<31}|".format("{:.2f}".format(ls["p95"])),
        "  |  P99             : {:<31}|".format("{:.2f}".format(ls["p99"])),
        "  +----------------------------------------------------+",
    ]

    # 错误摘要（最多展示前 10 条）
    errors = report.get("errors", [])
    if errors:
        lines.append("")
        lines.append("  +-- Errors (first 10 of {}) -------------------------+".format(len(errors)))
        for e in errors[:10]:
            tag = "[TIMEOUT]" if e["is_timeout"] else "[ERROR]  "
            lines.append(
                "  |  {} idx={:>4}  round={}  {:>9.2f}ms".format(
                    tag, e["index"], e["round"], e["latency_ms"]
                )
            )
            msg = (e["error"] or "")[:50]
            lines.append("  |    -> {}".format(msg))
        lines.append("  +----------------------------------------------------+")

    lines.append("")
    lines.append(divider)
    lines.append("")

    out.write("\n".join(lines))
    out.flush()