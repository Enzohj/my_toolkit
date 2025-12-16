import time
from functools import wraps
from .logger import logger
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import traceback
from io import StringIO

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()  # 记录开始时间
        result = func(*args, **kwargs)  # 执行原函数
        end_time = time.time()  # 记录结束时间
        elapsed_time = end_time - start_time  # 计算耗时
        logger.info(f"function: '{func.__name__}', latency: {elapsed_time:.4f} s")
        return result
    return wrapper

def timeout(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    result = future.result(timeout=seconds)
                except FutureTimeoutError:
                    raise TimeoutError(f"Function '{func.__name__}' timed out after {seconds} seconds.")
                return result
        return wrapper
    return decorator

def retry(max_attempts=3, delay=0.1, backoff=1):
    """
    装饰器：最多尝试 max_attempts 次，失败后等待 delay * (backoff ** 尝试次数) 秒

    参数:
        max_attempts (int): 最大尝试次数（至少 1）
        delay (float): 初始延迟时间（秒）
        backoff (float): 退避因子（1 表示固定间隔，>1 表示指数退避）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        sleep_time = delay * (backoff ** (attempt - 1))
                        logger.debug(f"function '{func.__name__}' failed, attempt {attempt}: {e}")
                        logger.debug(f"will retry in {sleep_time:.2f} seconds...")
                        time.sleep(sleep_time)
                    else:
                        # 最后一次失败，打印详细 traceback
                        logger.error(f"function '{func.__name__}' failed in {max_attempts} attempts.")
                        logger.error("Detailed error information:")
                        buffer = StringIO()
                        buffer.write(traceback.format_exc())
                        logger.error(f'\n{buffer.getvalue()}')
                        logger.error(f"input args: {args}, input kwargs: {kwargs}")
                        # raise last_exception  # 重新抛出最后一次异常
                        return None  # 理论上不会执行到这里
        return wrapper
    return decorator
