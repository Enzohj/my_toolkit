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
from typing import Any, Callable, Sequence

from .logger import init_logger
logger = init_logger(name="benchmark")

__all__ = ["benchmark", "print_report"]


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
    error: str | None = None
    return_value: Any = None


# ═══════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════

_PERCENTILE_KEYS = ("avg", "min", "max", "p50", "p90", "p95", "p99")
_ZERO_LATENCY: dict[str, float] = {k: 0.0 for k in _PERCENTILE_KEYS}


def _percentile(sorted_data: list[float], pct: float) -> float:
    """计算第 pct 百分位（0–100），线性插值。sorted_data 须已升序排列。"""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    k = pct / 100.0 * (n - 1)
    f = int(k)                      # floor（非负数 int 等价 math.floor）
    if f >= n - 1:
        return sorted_data[-1]
    frac = k - f
    return sorted_data[f] + frac * (sorted_data[f + 1] - sorted_data[f])


def _compute_latency_stats(latencies_ms: list[float]) -> dict[str, float]:
    """根据已排序的毫秒级延迟列表，计算 avg / min / max / p50 / p90 / p95 / p99。"""
    if not latencies_ms:
        return dict(_ZERO_LATENCY)
    return {
        "avg": statistics.mean(latencies_ms),
        "min": latencies_ms[0],
        "max": latencies_ms[-1],
        "p50": _percentile(latencies_ms, 50),
        "p90": _percentile(latencies_ms, 90),
        "p95": _percentile(latencies_ms, 95),
        "p99": _percentile(latencies_ms, 99),
    }


# ═══════════════════════════════════════════════
#  模块顶层 worker（支持 ProcessPoolExecutor 的 pickle 要求）
# ═══════════════════════════════════════════════

def _run_one(
    func: Callable[[Any], Any],
    index: int,
    item: Any,
    rnd: int,
    timeout: float | None = None,
) -> _TaskResult:
    """
    在 worker 中执行一次 func(item)，捕获异常并记录耗时。
    此函数定义在模块顶层，以确保 ProcessPoolExecutor 能正确序列化。

    当 timeout 非 None 且实际耗时超过该值时，标记为超时失败。
    """
    t0 = time.perf_counter()
    try:
        ret = func(item)
        latency = time.perf_counter() - t0
        timed_out = timeout is not None and latency > timeout
        return _TaskResult(
            index=index,
            repeat_round=rnd,
            latency=latency,
            success=not timed_out,
            is_timeout=timed_out,
            return_value=None if timed_out else ret,
        )
    except Exception as exc:
        latency = time.perf_counter() - t0
        return _TaskResult(
            index=index,
            repeat_round=rnd,
            latency=latency,
            success=False,
            is_timeout=timeout is not None and latency > timeout,
            error=f"{type(exc).__name__}: {exc}",
        )


# ═══════════════════════════════════════════════
#  进度条（纯标准库实现，线程安全）
# ═══════════════════════════════════════════════

class _ProgressBar:
    """
    线程安全的终端进度条（支持上下文管理器协议）。
    实时显示：完成数/总数、已用时间、成功率、实时 QPS。
    输出到 stderr 以避免干扰 stdout 的正常输出。
    """

    __slots__ = (
        "total", "completed", "success", "fail", "timeout",
        "_lock", "_start", "_closed",
    )

    def __init__(self, total: int) -> None:
        self.total = total
        self.completed = 0
        self.success = 0
        self.fail = 0
        self.timeout = 0
        self._lock = threading.Lock()
        self._start = time.monotonic()
        self._closed = False

    def __enter__(self) -> _ProgressBar:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def _term_width() -> int:
        """获取终端宽度，兼容无终端环境。"""
        try:
            return shutil.get_terminal_size().columns
        except Exception:
            return 80

    def update(self, *, success: bool = True, is_timeout: bool = False) -> None:
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

    def _render(self) -> None:
        elapsed = time.monotonic() - self._start
        pct = self.completed / self.total if self.total else 1.0
        qps = self.completed / elapsed if elapsed > 0 else 0.0

        info = (
            f" {self.completed}/{self.total}"
            f" [{elapsed:.1f}s]"
            f" QPS={qps:.1f}"
            f" ok={self.success} err={self.fail} to={self.timeout}"
        )
        bar_max = max(self._term_width() - len(info) - 2, 10)
        filled = int(bar_max * pct)
        bar = "#" * filled + "-" * (bar_max - filled)
        sys.stderr.write(f"\r[{bar}]{info}")
        sys.stderr.flush()

    def close(self) -> None:
        """压测结束后调用，换行收尾。"""
        if not self._closed:
            sys.stderr.write("\n")
            sys.stderr.flush()
            self._closed = True


# ═══════════════════════════════════════════════
#  核心压测函数
# ═══════════════════════════════════════════════

_EXECUTOR_MAP: dict[str, type] = {
    "thread": ThreadPoolExecutor,
    "process": ProcessPoolExecutor,
}


def benchmark(
    func: Callable[[Any], Any],
    data_list: Sequence[Any],
    *,
    concurrency: int = 10,
    repeat: int = 1,
    timeout: float | None = None,
    executor_type: str = "thread",
    show_progress: bool = True,
) -> dict[str, Any]:
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
        单次调用的超时阈值（秒）。实际耗时超过此值的调用标记为超时失败。
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
        "success_rate": float,      # 成功率百分比
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

    PoolClass = _EXECUTOR_MAP.get(executor_type)
    if PoolClass is None:
        raise ValueError(
            f"executor_type must be one of {list(_EXECUTOR_MAP)}, got '{executor_type}'"
        )

    data_size = len(data_list)
    total_requests = data_size * repeat

    # ── 空数据快速路径 ──
    if total_requests == 0:
        empty_report: dict[str, Any] = {
            "total_requests": 0, "success_count": 0,
            "fail_count": 0, "timeout_count": 0, "success_rate": 100.0,
            "total_time": 0.0, "qps": 0.0,
            "latency_stats": dict(_ZERO_LATENCY),
            "concurrency": concurrency, "repeat": repeat,
            "data_size": data_size, "executor_type": executor_type,
            "results": [], "errors": [],
        }
        print_report(empty_report)
        return empty_report

    task_results: list[_TaskResult] = []
    logger.info(
        f"benchmark: {func.__name__}, {total_requests} requests, "
        f"{concurrency} workers, {repeat} rounds"
    )

    # ── 主调度 ──
    wall_start = time.perf_counter()

    with PoolClass(max_workers=concurrency) as pool:
        future_map: dict[Future, tuple[int, int]] = {}
        for rnd in range(repeat):
            for idx, item in enumerate(data_list):
                fut = pool.submit(_run_one, func, idx, item, rnd, timeout)
                future_map[fut] = (idx, rnd)

        progress = _ProgressBar(total_requests) if show_progress else None
        try:
            for fut in as_completed(future_map):
                idx, rnd = future_map[fut]
                try:
                    result = fut.result()
                except Exception as exc:
                    # 仅捕获 pool 层面异常（序列化失败等），
                    # func 本身的异常已在 _run_one 内部处理
                    result = _TaskResult(
                        index=idx,
                        repeat_round=rnd,
                        latency=timeout or 0.0,
                        success=False,
                        is_timeout=True,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                task_results.append(result)
                if progress:
                    progress.update(success=result.success, is_timeout=result.is_timeout)
        finally:
            if progress:
                progress.close()

    total_time = time.perf_counter() - wall_start

    # ═══════════════════════════════════════════
    #  统计计算
    # ═══════════════════════════════════════════

    success_count = sum(1 for r in task_results if r.success)
    fail_count = total_requests - success_count
    timeout_count = sum(1 for r in task_results if r.is_timeout)

    latencies_ms = sorted(r.latency * 1000.0 for r in task_results)
    latency_stats = _compute_latency_stats(latencies_ms)
    qps = total_requests / total_time if total_time > 0 else 0.0

    # ── 与 data_list 一一对应的返回值列表（取最后一轮 repeat 的结果）──
    last_round = repeat - 1
    results_by_index: dict[int, Any] = {
        r.index: r.return_value
        for r in task_results
        if r.repeat_round == last_round and r.success
    }
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

    report: dict[str, Any] = {
        "total_requests": total_requests,
        "success_count": success_count,
        "fail_count": fail_count,
        "timeout_count": timeout_count,
        "success_rate": round(success_count / total_requests * 100, 2),
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
    print_report(report)
    return report


# ═══════════════════════════════════════════════
#  格式化报告打印
# ═══════════════════════════════════════════════

def print_report(report: dict[str, Any], file: Any = None) -> None:
    """
    将压测报告以可读文本格式打印。

    参数
    ────
    report : dict — 由 benchmark() 返回的结果字典。
    file   : IO   — 输出目标，默认 sys.stdout。
    """
    out = file or sys.stdout
    ls = report["latency_stats"]
    sr = report.get("success_rate", "N/A")

    # 预先格式化，避免 f-string 内嵌反斜杠
    total_time_s = f"{report['total_time']:.4f}s"
    qps_s = f"{report['qps']:.2f}"
    sr_s = f"{sr}%"
    avg_s = f"{ls['avg']:.2f}"
    min_s = f"{ls['min']:.2f}"
    max_s = f"{ls['max']:.2f}"
    p50_s = f"{ls['p50']:.2f}"
    p90_s = f"{ls['p90']:.2f}"
    p95_s = f"{ls['p95']:.2f}"
    p99_s = f"{ls['p99']:.2f}"

    divider = "=" * 58

    lines = [
        "",
        divider,
        "              BENCHMARK  REPORT",
        divider,
        "",
        "  +-- Configuration -----------------------------------+",
        f"  |  Concurrency     : {report['concurrency']:<31}|",
        f"  |  Repeat rounds   : {report['repeat']:<31}|",
        f"  |  Data size       : {report['data_size']:<31}|",
        f"  |  Executor        : {report['executor_type']:<31}|",
        "  +----------------------------------------------------+",
        "",
        "  +-- Summary -----------------------------------------+",
        f"  |  Total requests  : {report['total_requests']:<31}|",
        f"  |  Success         : {report['success_count']:<31}|",
        f"  |  Failures        : {report['fail_count']:<31}|",
        f"  |  Timeouts        : {report['timeout_count']:<31}|",
        f"  |  Success rate    : {sr_s:<31}|",
        f"  |  Total time      : {total_time_s:<31}|",
        f"  |  QPS             : {qps_s:<31}|",
        "  +----------------------------------------------------+",
        "",
        "  +-- Latency (ms) ------------------------------------+",
        f"  |  Avg             : {avg_s:<31}|",
        f"  |  Min             : {min_s:<31}|",
        f"  |  Max             : {max_s:<31}|",
        f"  |  P50 (median)    : {p50_s:<31}|",
        f"  |  P90             : {p90_s:<31}|",
        f"  |  P95             : {p95_s:<31}|",
        f"  |  P99             : {p99_s:<31}|",
        "  +----------------------------------------------------+",
    ]

    # 错误摘要（最多展示前 10 条）
    errors = report.get("errors", [])
    if errors:
        lines.append("")
        lines.append(f"  +-- Errors (first 10 of {len(errors)}) -------------------------+")
        for e in errors[:10]:
            tag = "[TIMEOUT]" if e["is_timeout"] else "[ERROR]  "
            e_idx = e["index"]
            e_rnd = e["round"]
            e_lat = e["latency_ms"]
            lines.append(
                f"  |  {tag} idx={e_idx:>4}  round={e_rnd}  {e_lat:>9.2f}ms"
            )
            msg = (e["error"] or "")[:50]
            lines.append(f"  |    -> {msg}")
        lines.append("  +----------------------------------------------------+")

    lines.append("")
    lines.append(divider)
    lines.append("")

    out.write("\n".join(lines))
    out.flush()
