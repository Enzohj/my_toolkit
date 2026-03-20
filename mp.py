"""
mp.py - 并行处理工具模块

multi_thread
    受 GIL（全局解释器锁）限制。
    在 Python 中，同一时间只有一个线程能执行 Python 字节码。
    因此，不适合 CPU 密集型任务（如大量计算）。
    适合 I/O 密集型任务（如网络请求、文件读写、数据库操作）。

multi_process
    每个进程有独立的 Python 解释器和内存空间，因此不受 GIL 影响。
    可以真正实现并行计算。
    适合 CPU 密集型任务（如图像处理、数学计算、数据压缩等）。

提供 apply_parallel 函数，支持多线程/多进程并行处理，并保证结果顺序与输入一致。
"""

from __future__ import annotations

import os
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    Literal,
    Optional,
    Union,
)
from concurrent.futures import (
    ThreadPoolExecutor,
    ProcessPoolExecutor,
    Future,
    as_completed,
)

from .logger import logger
import pandas as pd
try:
    from tqdm.auto import tqdm  # auto 可自动适配 notebook / terminal
except ImportError:
    tqdm = None

# ---------------------------------------------------------------------------
# 常量与默认配置
# ---------------------------------------------------------------------------
_VALID_METHODS = ("thread", "process")

_EXECUTOR_MAP = {
    "thread": ThreadPoolExecutor,
    "process": ProcessPoolExecutor,
}

NUM_WORKERS: int = int(
    os.environ.get("NUM_WORKERS", min(os.cpu_count() or 1, 8))
)


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------
def _call_func(func: Callable, element: Any) -> Any:
    """根据 element 的类型选择调用方式：

    - dict        → func(**element)
    - tuple / list → func(*element)
    - 其他         → func(element)
    """
    if isinstance(element, dict):
        return func(**element)
    if isinstance(element, (tuple, list)):
        return func(*element)
    return func(element)


def _resolve_iterable(iterable: Any) -> tuple[list, Optional[int]]:
    """将各种可迭代类型统一转为 list，并在遇到 DataFrame 时转为 records。"""
    if isinstance(iterable, pd.DataFrame):
        iterable = iterable.to_dict(orient="records")
    if hasattr(iterable, "__len__"):
        return iterable, len(iterable)
    else:
        logger.warning(f"!!! pay attention: iterable type is {type(iterable)}, convert to list...")
        iterable = list(iterable)
        return iterable, len(iterable)


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------
def apply_parallel(
    iterable: Iterable,
    func: Callable,
    method: Literal["thread", "process"] = "thread",
    num_workers: int = NUM_WORKERS,
    show_progress: bool = True,
    total_num: Optional[int] = None,
    error_policy: Literal["store", "raise", "ignore"] = "store",
    progress_desc: Optional[str] = None,
) -> List[Any]:
    """对 *iterable* 中的每个元素并行调用 *func*，返回与输入顺序严格一致的结果列表。

    Parameters
    ----------
    iterable : Iterable
        任意可迭代对象（列表、元组、生成器、``pandas.DataFrame`` 等）。
        当传入 DataFrame 时，自动按行转为 ``dict`` 列表。
    func : callable
        对每个元素执行的函数。根据元素类型自动选择解包方式：
    method : ``"thread"`` | ``"process"``, default ``"thread"``
        并行方式。传入其他值将抛出 ``ValueError``。
    num_workers : int, default ``NUM_WORKERS``
        最大并行工作者数量。会被自动裁剪为 ``[1, total_num]`` 范围。
    show_progress : bool, default ``True``
        是否通过 ``tqdm`` 显示进度条（未安装 tqdm 时自动跳过）。
    total_num : int | None, default ``None``
        总任务数。为 ``None`` 时自动推断。
    error_policy : ``"store"`` | ``"raise"`` | ``"ignore"``, default ``"store"``
        任务异常处理策略：
        - ``"store"``  — 将异常对象存入结果列表对应位置（默认，向后兼容）。
        - ``"raise"``  — 遇到第一个异常立即取消剩余任务并抛出。
        - ``"ignore"`` — 记录日志，结果位置填 ``None``。
    progress_desc : str | None, default ``None``
        自定义进度条描述文字。为 ``None`` 时使用默认格式。

    Returns
    -------
    list
        结果列表，第 *i* 个元素对应 ``iterable`` 中第 *i* 个输入。

    Raises
    ------
    ValueError
        当 ``method`` 不是 ``"thread"`` 或 ``"process"`` 时。
    RuntimeError
        当 ``error_policy="raise"`` 且有任务抛出异常时（封装原始异常）。

    Examples
    --------
    >>> from mp import apply_parallel
    >>> results = apply_parallel(range(10), lambda x: x ** 2, method="thread")
    >>> assert results == [i ** 2 for i in range(10)]
    """

    # ---- 1. 参数校验 -----------------------------------------------------
    if method not in _VALID_METHODS:
        raise ValueError(
            f"method 参数仅支持 {_VALID_METHODS!r}，收到: {method!r}"
        )
    if error_policy not in ("store", "raise", "ignore"):
        raise ValueError(
            f"error_policy 参数仅支持 'store' / 'raise' / 'ignore'，收到: {error_policy!r}"
        )

    # ---- 2. 物化可迭代对象并构建索引 -------------------------------------
    items, count_num = _resolve_iterable(iterable)
    total_num = total_num or count_num 

    # 裁剪 num_workers 到合理范围
    if total_num is not None:
        num_workers = max(1, min(num_workers, total_num))

    # ---- 3. 选择执行器 ---------------------------------------------------
    executor_cls = _EXECUTOR_MAP[method]

    # ---- 4. 进度条准备 ---------------------------------------------------
    use_tqdm = show_progress and tqdm is not None
    if show_progress and tqdm is None:
        logger.warning(
            "show_progress=True 但 tqdm 未安装，将跳过进度条显示。"
            "可通过 `pip install tqdm` 安装。"
        )

    logger.info(
        f"apply_parallel 启动 | method={method}, num_workers={num_workers}, total_num={total_num}, error_policy={error_policy}",
    )

    # ---- 5. 提交与收集 ---------------------------------------------------
    results: list = [None] * total_num
    error_count = 0

    with executor_cls(max_workers=num_workers) as executor:
        future_to_idx: dict[Future, int] = {
            executor.submit(_call_func, func, elem): idx
            for idx, elem in enumerate(items)
        }

        iterator = as_completed(future_to_idx)
        if use_tqdm:
            iterator = tqdm(
                iterator,
                total=total_num,
                desc=progress_desc,
                unit="task",
                dynamic_ncols=True,
            )

        for future in iterator:
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                error_count += 1
                logger.error(
                    f"任务 #{idx} 执行失败: {exc}",
                )
                if error_policy == "raise":
                    # 取消尚未开始的任务
                    for f in future_to_idx:
                        f.cancel()
                    raise RuntimeError(
                        f"任务 #{idx} 执行失败: {exc}"
                    ) from exc
                elif error_policy == "store":
                    results[idx] = exc
                # error_policy == "ignore" → results[idx] 保持 None

    # ---- 6. 日志汇总 -----------------------------------------------------
    if error_count:
        logger.warning(
            f"共有 {error_count} / {total_num} 个任务执行失败",
        )
    else:
        logger.info(f"全部 {total_num} 个任务执行完成")

    return results