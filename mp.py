from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp
from tqdm import tqdm
from .logger import logger

# multi_thread
# 受 GIL（全局解释器锁） 限制。
# 在 Python 中，同一时间只有一个线程能执行 Python 字节码。
# 因此，不适合 CPU 密集型任务（如大量计算）。
# 适合 I/O 密集型任务（如网络请求、文件读写、数据库操作）。

# multi_process
# 每个进程有独立的 Python 解释器和内存空间，因此不受 GIL 影响。
# 可以真正实现并行计算。
# 适合 CPU 密集型任务（如图像处理、数学计算、数据压缩等）。

NUM_WORKERS = mp.cpu_count()

def apply_multi_thread(func, iterable, num_workers=NUM_WORKERS, show_progess=True, total_num=None):
    """
    使用多线程对 iterable 中的每个元素应用 func，并显示进度条。
    
    参数:
        func: 要应用的函数
        iterable: 可迭代对象（如 list, tuple 等）
        num_workers: 线程数，默认为 cpu 核心数
        show_progess: 是否显示进度条，默认为 True
        total_num: 总任务数，默认为 None
    
    返回:
        list: func 应用于每个元素后的结果列表
    """
    if total_num is None:
        try:
            total_num = len(iterable)
        except:
            show_progess = False
    logger.info(f"apply_multi_thread! total sample: {total_num}, num worker: {num_workers}")

    def wrapper(args):
        if isinstance(args, tuple):
            return func(*args)
        else:
            return func(args)
        
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        if show_progess:
            results = list(tqdm(executor.map(wrapper, iterable), total=total_num))
        else:
            results = list(executor.map(wrapper, iterable))
    return results

def apply_multi_process(func, iterable, num_workers=NUM_WORKERS, show_progess=True, total_num=None, use_starmap=False):
    """
    使用多进程对 iterable 中的每个元素应用 func，并显示进度条。
    
    参数:
        iterable: 可迭代对象（如 list, tuple 等）
        func: 要应用的函数
        num_workers: 进程数，默认为 cpu 核心数
        show_progess: 是否显示进度条，默认为 True
        total_num: 总任务数，默认为 None
    
    返回:
        list: func 应用于每个元素后的结果列表
    """
    if total_num is None:
        try:
            total_num = len(iterable)
        except:
            show_progess = False
    logger.info(f"apply_multi_process! total sample: {total_num}, num worker: {num_workers}")

    with mp.Pool(num_workers) as pool:
        pool_map = pool.starmap if use_starmap else pool.imap
        if show_progess:
            results = list(tqdm(pool_map(func, iterable), total=total_num))
        else:
            results = list(pool_map(func, iterable))
    return results

