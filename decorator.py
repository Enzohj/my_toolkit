import time
import traceback
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, TypeVar
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from .logger import logger

F = TypeVar("F", bound=Callable[..., Any])

__all__ = ["timer", "timeout", "retry"]


# ────────────────────────────── timer ──────────────────────────────

def timer(func: F) -> F:
    """记录函数执行耗时（秒），无论成功或异常均会输出。"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            logger.info(f"Function '{func.__name__}' elapsed: {elapsed:.4f}s")

    return wrapper  # type: ignore[return-value]


# ────────────────────────────── timeout ──────────────────────────────

def timeout(seconds: float) -> Callable[[F], F]:
    """
    限制函数执行时间。超时后抛出 TimeoutError。

    注意：底层使用 ThreadPoolExecutor，超时后线程本身不会被强制终止，
    仅在调用侧抛出异常。如需真正中断，请考虑 multiprocessing 方案。
    """
    if seconds <= 0:
        raise ValueError(f"timeout seconds must be positive, got {seconds}")

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=seconds)
                except FutureTimeoutError:
                    future.cancel()
                    raise TimeoutError(
                        f"Function '{func.__name__}' timed out after {seconds}s"
                    )

        return wrapper  # type: ignore[return-value]

    return decorator


# ────────────────────────────── retry ──────────────────────────────

def retry(
    max_attempts: int = 3,
    delay: float = 0.1,
    backoff: float = 1,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    fail_return: Optional[Any] = None,
    raise_on_failure: bool = False,
) -> Callable[[F], F]:
    """
    重试装饰器：在指定异常发生时自动重试。

    参数:
        max_attempts:    最大尝试次数（≥1）
        delay:           初始延迟时间（秒）
        backoff:         退避因子（1=固定间隔，>1=指数退避）
        exceptions:      需要捕获并重试的异常类型元组
        fail_return:     所有尝试失败后的默认返回值（仅 raise_on_failure=False 时生效）
        raise_on_failure: True 时在最终失败后重新抛出异常，False 时返回 fail_return
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception: Optional[BaseException] = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc

                    if attempt < max_attempts:
                        sleep_time = delay * (backoff ** (attempt - 1))
                        logger.debug(
                            f"[retry] '{func.__name__}' attempt {attempt}/{max_attempts} "
                            f"failed: {exc}; retrying in {sleep_time:.2f}s …"
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(
                            f"[retry] '{func.__name__}' exhausted {max_attempts} attempts. "
                            f"Last error: {last_exception}"
                        )
                        logger.error(f"[retry] traceback:\n{traceback.format_exc()}")
                        logger.debug(
                            f"[retry] call args={args}, kwargs={kwargs}"
                        )

            # 所有尝试均失败
            if raise_on_failure:
                raise last_exception  # type: ignore[misc]
            return fail_return

        return wrapper  # type: ignore[return-value]

    return decorator