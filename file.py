from .logger import logger
import csv
import json
import pandas as pd
import os
from tqdm import tqdm
from io import StringIO
from typing import List, Optional, Any, Union
from pathlib import Path
import pickle

# ========================
# 内部工具函数
# ========================

def _resolve_write_mode(append: bool) -> str:
    """根据 append 标志返回文件打开模式。"""
    return 'a' if append else 'w'


def _mode_label(append: bool) -> str:
    """返回日志中使用的模式描述文本。"""
    return 'append' if append else 'write'


def _log_dataframe_info(df: pd.DataFrame) -> None:
    """将 DataFrame.info() 输出写入日志。"""
    buffer = StringIO()
    df.info(buf=buffer)
    logger.info(f"\n{buffer.getvalue()}")


def _try_parquet_engines(
    operation: str,
    func,
    engines: tuple = ('fastparquet', 'pyarrow', 'auto'),
    **kwargs,
) -> Any:
    """
    按优先级依次尝试不同 Parquet 引擎执行读写操作。

    优先级: fastparquet → pyarrow → auto（Pandas 默认）

    参数:
        operation (str): 操作描述，用于日志（如 "read" / "write"）。
        func (callable): 实际执行的函数，接受 engine 关键字参数。
        engines (tuple): 引擎优先级列表。
        **kwargs: 透传给 func 的其余参数。

    返回:
        func 的返回值。

    异常:
        RuntimeError: 所有引擎均失败时抛出。
    """
    last_exc: Optional[Exception] = None
    for engine in engines:
        try:
            result = func(engine=engine, **kwargs)
            logger.debug(f"Parquet {operation} succeeded with engine='{engine}'")
            return result
        except ImportError:
            logger.debug(f"Engine '{engine}' is not installed, skipping")
            continue
        except Exception as exc:
            logger.debug(f"Engine '{engine}' Fail for {operation}: {exc}")
            last_exc = exc
            continue

    raise RuntimeError(
        f"All Parquet engines {engines} Fail for {operation}. "
        f"Last error: {last_exc}"
    )


# ========================
# TXT 文件读写
# ========================

def read_txt(
    file_path: Union[str, Path],
    encoding: str = 'utf-8',
    as_lines: bool = True,
) -> Union[str, List[str]]:
    """
    读取 TXT 文件内容。

    参数:
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
        as_lines: 是否按行读取，默认 True。

    返回:
        若 as_lines=True 返回去除首尾空白的行列表，否则返回原始字符串。
    """
    file_path = str(file_path)
    with open(file_path, 'r', encoding=encoding) as f:
        if as_lines:
            content = [line.strip() for line in f.readlines()]
            logger.info(f"Read {len(content)} lines from '{file_path}'")
        else:
            content = f.read()
            logger.info(f"Read {len(content)} characters from '{file_path}'")
        return content


def write_txt(
    content: Union[str, List[str]],
    file_path: Union[str, Path],
    encoding: str = 'utf-8',
    append: bool = False,
) -> None:
    """
    写入 TXT 文件内容。

    参数:
        content: 要写入的内容（字符串或字符串列表）。
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
        append: 是否追加写入，默认 False。
    """
    file_path = str(file_path)
    mode = _resolve_write_mode(append)
    label = _mode_label(append)

    with open(file_path, mode, encoding=encoding) as f:
        if isinstance(content, list):
            lines = [line + '\n' for line in content]
            f.writelines(lines)
            logger.info(f"Write {len(lines)} lines to '{file_path}' in {label} mode")
        else:
            f.write(content)
            logger.info(f"Write {len(content)} characters to '{file_path}' in {label} mode")


# ========================
# CSV 文件读写
# ========================

def read_csv(
    file_path: Union[str, Path],
    encoding: str = 'utf-8',
    sep: str = ',',
    format: str = 'dataframe',
    skip_header: bool = True,
    **kwargs,
) -> Union[pd.DataFrame, List[List[str]]]:
    """
    读取 CSV 文件。

    参数:
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
        sep: 分隔符，默认 ','。
        format: 读取格式，'dataframe' 或 'list'，默认 'dataframe'。
        skip_header: format='list' 时是否跳过首行表头，默认 True。
        **kwargs: 透传给 pandas.read_csv（dataframe 模式）或 csv.reader（list 模式）。

    返回:
        pd.DataFrame 或嵌套列表。
    """
    file_path = str(file_path)

    if format == 'dataframe':
        df = pd.read_csv(file_path, sep=sep, encoding=encoding, **kwargs)
        df = df.where(pd.notnull(df), None)
        logger.info(f"CSV header: {df.columns.tolist()}")
        logger.info(f"Read CSV '{file_path}' as DataFrame. Shape: {df.shape}")
        return df

    if format == 'list':
        with open(file_path, 'r', encoding=encoding) as f:
            reader = csv.reader(f, delimiter=sep, **kwargs)
            if skip_header:
                header = next(reader, None)
                if header:
                    logger.info(f"Skipped CSV header: {header}")
            data = list(reader)
            logger.info(f"Read CSV '{file_path}' as list. Rows: {len(data)}")
            return data

    raise ValueError(f"Unsupported format: '{format}'. Choose 'dataframe' or 'list'.")


def write_csv(
    data: Union[pd.DataFrame, dict, List[list]],
    file_path: Union[str, Path],
    encoding: str = 'utf-8',
    append: bool = False,
    sep: str = ',',
    header: Optional[List[str]] = None,
    **kwargs,
) -> None:
    """
    写入 CSV 文件。

    参数:
        data: 要写入的数据（DataFrame / dict / 嵌套列表）。
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
        append: 是否追加写入，默认 False。
        sep: 分隔符，默认 ','。
        header: 仅 list 模式下使用的列名列表，默认 None。
        **kwargs: 透传给 pandas.to_csv（DataFrame 模式）。
    """
    file_path = str(file_path)
    mode = _resolve_write_mode(append)
    label = _mode_label(append)

    if isinstance(data, dict):
        data = pd.DataFrame(data)

    if isinstance(data, pd.DataFrame):
        data.to_csv(file_path, index=False, sep=sep, mode=mode, encoding=encoding, **kwargs)
        logger.info(f"Write DataFrame to '{file_path}' in {label} mode. Shape: {data.shape}")
    elif isinstance(data, list):
        with open(file_path, mode, newline='', encoding=encoding) as f:
            writer = csv.writer(f, delimiter=sep)
            if header:
                logger.info(f"CSV header: {header}")
                writer.writerow(header)
            writer.writerows(data)
            logger.info(f"Write {len(data)} rows to '{file_path}' in {label} mode")
    else:
        raise TypeError(
            f"Unsupported data type: {type(data).__name__}. "
            "Expected pd.DataFrame, dict, or list."
        )


# ========================
# JSON 文件读写
# ========================

def read_json(
    file_path: Union[str, Path],
    encoding: str = 'utf-8',
) -> Any:
    """
    读取 JSON 文件。

    参数:
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。

    返回:
        反序列化后的 Python 对象（通常为 dict 或 list）。
    """
    file_path = str(file_path)
    with open(file_path, 'r', encoding=encoding) as f:
        data = json.load(f)
        count = len(data) if isinstance(data, (list, dict)) else 1
        logger.info(f"Read JSON '{file_path}' successfully. Top-level items: {count}")
        return data


def write_json(
    data: Any,
    file_path: Union[str, Path],
    encoding: str = 'utf-8',
    ensure_ascii: bool = False,
    indent: int = 4,
) -> None:
    """
    写入 JSON 文件。

    参数:
        data: 要写入的可 JSON 序列化对象。
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
        ensure_ascii: 是否确保 ASCII 编码，默认 False。
        indent: 缩进空格数，默认 4。
    """
    file_path = str(file_path)
    with open(file_path, 'w', encoding=encoding) as f:
        json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
        logger.info(f"Write JSON data to '{file_path}'")


# ========================
# JSONL 文件读写
# ========================

def read_jsonl(
    file_path: Union[str, Path],
    encoding: str = 'utf-8',
) -> List[Any]:
    """
    读取 JSONL 文件（每行一个 JSON 对象）。

    参数:
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。

    返回:
        每行解析后的对象列表。
    """
    file_path = str(file_path)
    with open(file_path, 'r', encoding=encoding) as f:
        data = [json.loads(line) for line in f if line.strip()]
        logger.info(f"Read {len(data)} JSON objects from '{file_path}'")
        return data


def write_jsonl(
    data: List[Any],
    file_path: Union[str, Path],
    encoding: str = 'utf-8',
) -> None:
    """
    写入 JSONL 文件（每行一个 JSON 对象）。

    参数:
        data: 要写入的对象列表。
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
    """
    file_path = str(file_path)
    with open(file_path, 'w', encoding=encoding) as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
        logger.info(f"Write {len(data)} JSON objects to '{file_path}'")


# ========================
# Parquet 文件读写
# ========================

def _read_single_parquet(file_path: str, engine: str) -> pd.DataFrame:
    """读取单个 Parquet 文件，使用 _try_parquet_engines 实现引擎回退。"""
    def _do_read(engine: str) -> pd.DataFrame:
        return pd.read_parquet(file_path, engine=engine)

    return _try_parquet_engines(
        operation=f"read '{file_path}'",
        func=_do_read,
    )


def read_parquet(
    file_root: Union[str, Path],
    engine: str = 'auto',
    ignore: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    读取 Parquet 文件或目录。

    当 file_root 为目录时，先尝试整目录读取；若失败则逐文件读取后合并。
    引擎优先级: fastparquet → pyarrow → auto。

    参数:
        file_root: 文件路径或目录路径。
        engine: 指定引擎（实际会按优先级自动回退）。
        ignore: 需要忽略的文件名关键词列表，默认 ['_SUCCESS']。

    返回:
        pd.DataFrame，读取失败时返回空 DataFrame。
    """
    if ignore is None:
        ignore = ['_SUCCESS']

    file_root = str(file_root)

    # ---------- 单文件 ----------
    if os.path.isfile(file_root):
        try:
            data = _read_single_parquet(file_root, engine)
            logger.info(f"Read Parquet file '{file_root}'. Shape: {data.shape}")
            _log_dataframe_info(data)
            return data
        except Exception as e:
            logger.error(f"Fail to read Parquet file '{file_root}': {e}")
            return pd.DataFrame()

    # ---------- 目录 ----------
    if os.path.isdir(file_root):
        # 先尝试整目录读取
        try:
            data = _try_parquet_engines(
                operation=f"read dir '{file_root}'",
                func=lambda engine: pd.read_parquet(file_root, engine=engine),
            )
            logger.info(f"Read Parquet dir '{file_root}'. Shape: {data.shape}")
            _log_dataframe_info(data)
            return data
        except Exception:
            logger.warning(
                f"Bulk directory read Fail for '{file_root}', "
                "falling back to per-file reading"
            )

        # 逐文件读取
        file_names = os.listdir(file_root)
        all_chunks: List[pd.DataFrame] = []

        for file_name in tqdm(file_names, desc="Reading Parquet files", leave=False):
            if any(ig in file_name for ig in ignore):
                continue
            file_path = os.path.join(file_root, file_name)
            if not os.path.isfile(file_path):
                continue
            try:
                chunk = _read_single_parquet(file_path, engine)
                logger.info(f"Read Parquet file '{file_path}'. Shape: {chunk.shape}")
                all_chunks.append(chunk)
                del chunk
            except Exception as e:
                logger.error(f"Fail to read Parquet file '{file_path}': {e}")

        if all_chunks:
            data = pd.concat(all_chunks, ignore_index=True)
            logger.info(
                f"Concat {len(all_chunks)} Parquet files from '{file_root}'. "
                f"Shape: {data.shape}"
            )
            _log_dataframe_info(data)
            return data

        logger.error(f"No valid Parquet data found in directory '{file_root}'")
        return pd.DataFrame()

    # 路径既不是文件也不是目录
    logger.error(f"Path does not exist or is not accessible: '{file_root}'")
    return pd.DataFrame()


def write_parquet(
    df: pd.DataFrame,
    file_path: Union[str, Path],
    **kwargs,
) -> None:
    """
    写入 Parquet 文件，引擎优先级: fastparquet → pyarrow → auto。

    参数:
        df: 要写入的 DataFrame。
        file_path: 文件路径。
        **kwargs: 透传给 DataFrame.to_parquet 的额外参数（engine 会被自动管理）。
    """
    file_path = str(file_path)

    # 若调用方显式指定了 engine，尊重其选择；否则走回退链
    if 'engine' in kwargs:
        df.to_parquet(file_path, **kwargs)
        logger.info(f"Write Parquet file '{file_path}'. Shape: {df.shape}")
        return

    try:
        _try_parquet_engines(
            operation=f"write '{file_path}'",
            func=lambda engine: df.to_parquet(file_path, engine=engine, **kwargs),
        )
        logger.info(f"Write Parquet file '{file_path}'. Shape: {df.shape}")
    except RuntimeError as e:
        logger.error(f"Fail to write Parquet file '{file_path}': {e}")
        raise


# ========================
# Pickle 文件读写
# ========================

def read_pickle(
    file_path: Union[str, Path],
    **kwargs,
) -> Any:
    """
    读取 Pickle 文件。

    参数:
        file_path: 文件路径。
        **kwargs: 透传给 pickle.load 的额外参数。

    返回:
        从 Pickle 文件中反序列化的对象。
    """
    file_path = str(file_path)
    with open(file_path, 'rb') as f:
        data = pickle.load(f, **kwargs)
        logger.info(f"Read Pickle file '{file_path}'")
        return data


def write_pickle(
    obj: Any,
    file_path: Union[str, Path],
    **kwargs,
) -> None:
    """
    写入 Pickle 文件。

    参数:
        obj: 要序列化的对象。
        file_path: 文件路径。
        **kwargs: 透传给 pickle.dump 的额外参数。
    """
    file_path = str(file_path)
    with open(file_path, 'wb') as f:
        pickle.dump(obj, f, **kwargs)
        logger.info(f"Write Pickle file '{file_path}'")


# ========================
# 统一入口 (Dispatcher)
# ========================

_READ_DISPATCH = {
    '.json': read_json,
    '.jsonl': read_jsonl,
    '.parquet': read_parquet,
    '.csv': read_csv,
    '.txt': read_txt,
    '.pickle': read_pickle,
    '.pkl': read_pickle,
}

_WRITE_DISPATCH = {
    '.json': write_json,
    '.jsonl': write_jsonl,
    '.parquet': write_parquet,
    '.csv': write_csv,
    '.txt': write_txt,
    '.pickle': write_pickle,
    '.pkl': write_pickle,
}


def read_file(file_path: Union[str, Path], **kwargs) -> Any:
    """
    根据文件后缀自动选择读取函数。

    支持: .json / .jsonl / .parquet / .csv / .txt / .pickle / .pkl
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    reader = _READ_DISPATCH.get(suffix)
    if reader is None:
        raise ValueError(
            f"Unsupported file format: '{suffix}'. "
            f"Supported: {sorted(_READ_DISPATCH.keys())}"
        )
    return reader(path, **kwargs)


def write_file(data: Any, file_path: Union[str, Path], **kwargs) -> None:
    """
    根据文件后缀自动选择写入函数。

    支持: .json / .jsonl / .parquet / .csv / .txt / .pickle / .pkl
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    writer = _WRITE_DISPATCH.get(suffix)
    if writer is None:
        raise ValueError(
            f"Unsupported file format: '{suffix}'. "
            f"Supported: {sorted(_WRITE_DISPATCH.keys())}"
        )
    writer(data, path, **kwargs)