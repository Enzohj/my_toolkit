"""
file.py — 统一的文件读写工具模块

支持格式: TXT / CSV / TSV / JSON / JSONL / Parquet / Pickle
提供 read_file / write_file 两个统一入口，根据后缀自动分发。
"""

from .logger import init_logger
logger = init_logger(name="file")

import csv
import json
import os
import pickle
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import pandas as pd
from tqdm import tqdm

__all__ = [
    # TXT
    "read_txt", "write_txt",
    # CSV
    "read_csv", "write_csv",
    # JSON
    "read_json", "write_json",
    # JSONL
    "read_jsonl", "write_jsonl",
    # Parquet
    "read_parquet", "write_parquet",
    # Pickle
    "read_pickle", "write_pickle",
    # Dispatcher
    "read_file", "write_file",
]

PathLike = Union[str, Path]


# ========================
# 内部工具
# ========================

def _ensure_parent(file_path: Path) -> None:
    """若父目录不存在则自动创建。"""
    file_path.parent.mkdir(parents=True, exist_ok=True)


def _to_path(file_path: PathLike) -> Path:
    """统一转换为 Path 对象。"""
    return Path(file_path) if not isinstance(file_path, Path) else file_path


# ========================
# TXT 文件读写
# ========================

def read_txt(
    file_path: PathLike,
    encoding: str = "utf-8",
    as_lines: bool = True,
) -> Union[str, List[str]]:
    """
    读取 TXT 文件内容。

    参数:
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
        as_lines: 是否按行读取，默认 True。

    返回:
        若 as_lines=True 返回去除首尾空白的行列表，否则返回完整字符串。
    """
    file_path = _to_path(file_path)
    with open(file_path, "r", encoding=encoding) as f:
        if as_lines:
            content = [line.strip() for line in f]
            logger.info(f"Read {len(content)} lines from '{file_path}'")
        else:
            content = f.read()
            logger.info(f"Read {len(content)} characters from '{file_path}'")
    return content


def write_txt(
    content: Union[str, List[str]],
    file_path: PathLike,
    encoding: str = "utf-8",
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
    file_path = _to_path(file_path)
    _ensure_parent(file_path)
    mode = "a" if append else "w"
    with open(file_path, mode, encoding=encoding) as f:
        if isinstance(content, list):
            f.writelines(line + "\n" for line in content)
            logger.info(
                f"Write {len(content)} lines to '{file_path}' "
                f"in {'append' if append else 'write'} mode"
            )
        else:
            f.write(content)
            logger.info(
                f"Write {len(content)} characters to '{file_path}' "
                f"in {'append' if append else 'write'} mode"
            )


# ========================
# CSV 文件读写
# ========================

def read_csv(
    file_path: PathLike,
    encoding: str = "utf-8",
    sep: str = ",",
    format: Literal["dataframe", "list"] = "dataframe",
    skip_header: bool = True,
    replace_na: bool = True,
    **kwargs: Any,
) -> Union[pd.DataFrame, List[List[str]]]:
    """
    读取 CSV 文件。

    参数:
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
        sep: 分隔符，默认 ','。
        format: 读取格式，'dataframe' 或 'list'，默认 'dataframe'。
        skip_header: format='list' 时是否跳过首行表头，默认 True。
        replace_na: 是否替换缺失值，默认 True。
        **kwargs: 传递给 pandas.read_csv 或 csv.reader 的额外参数。

    返回:
        pd.DataFrame 或嵌套列表。
    """
    file_path = _to_path(file_path)

    if format == "dataframe":
        df = pd.read_csv(file_path, sep=sep, encoding=encoding, **kwargs)
        if replace_na:
            df = df.where(pd.notnull(df), None)
        logger.info(f"Read CSV '{file_path}' as DataFrame. Shape: {df.shape}, header: {df.columns.tolist()}")
        return df

    if format == "list":
        with open(file_path, "r", encoding=encoding) as f:
            reader = csv.reader(f, delimiter=sep, **kwargs)
            if skip_header:
                header = next(reader, None)
                if header:
                    logger.info(f"Skipped CSV header: {header}")
            data = list(reader)
            logger.info(f"Read CSV '{file_path}' as list. Rows: {len(data)}")
            return data

    raise ValueError(f"Unsupported format: {format!r}. Choose 'dataframe' or 'list'.")


def write_csv(
    data: Union[pd.DataFrame, Dict[str, Any], List[List[Any]]],
    file_path: PathLike,
    encoding: str = "utf-8",
    append: bool = False,
    sep: str = ",",
    header: Optional[List[str]] = None,
    **kwargs: Any,
) -> None:
    """
    写入 CSV 文件。

    参数:
        data: 要写入的数据（DataFrame / dict / 二维列表）。
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
        append: 是否追加写入，默认 False。
        sep: 分隔符，默认 ','。
        header: format='list' 时的列名列表，默认 None。
        **kwargs: 传递给 pandas.to_csv 或 csv.writer 的额外参数。
    """
    file_path = _to_path(file_path)
    _ensure_parent(file_path)
    mode = "a" if append else "w"

    if isinstance(data, dict):
        data = pd.DataFrame(data)

    if isinstance(data, pd.DataFrame):
        # 追加模式下不重复写入 header
        write_header = not append or not file_path.exists() or file_path.stat().st_size == 0
        data.to_csv(
            file_path, index=False, sep=sep, mode=mode,
            encoding=encoding, header=write_header, **kwargs,
        )
        logger.info(
            f"Write DataFrame to '{file_path}' "
            f"in {'append' if append else 'write'} mode. Shape: {data.shape}"
        )
    elif isinstance(data, list):
        with open(file_path, mode, newline="", encoding=encoding) as f:
            writer = csv.writer(f, delimiter=sep)
            if header:
                logger.info(f"CSV header: {header}")
                writer.writerow(header)
            writer.writerows(data)
            logger.info(
                f"Write {len(data)} rows to '{file_path}' "
                f"in {'append' if append else 'write'} mode"
            )
    else:
        raise TypeError(
            f"Unsupported data type: {type(data).__name__}. "
            "Expected pd.DataFrame, dict, or list."
        )


# ========================
# JSON 文件读写
# ========================

def read_json(file_path: PathLike, encoding: str = "utf-8") -> Any:
    """
    读取 JSON 文件。

    参数:
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。

    返回:
        反序列化后的 Python 对象（通常为 dict 或 list）。
    """
    file_path = _to_path(file_path)
    with open(file_path, "r", encoding=encoding) as f:
        data = json.load(f)
    logger.info(f"Read JSON '{file_path}' successfully. Top-level length: {len(data)}")
    return data


def write_json(
    data: Any,
    file_path: PathLike,
    encoding: str = "utf-8",
    ensure_ascii: bool = False,
    indent: int = 4,
) -> None:
    """
    写入 JSON 文件。

    参数:
        data: 可序列化为 JSON 的 Python 对象。
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
        ensure_ascii: 是否确保 ASCII 编码，默认 False。
        indent: 缩进空格数，默认 4。
    """
    file_path = _to_path(file_path)
    _ensure_parent(file_path)
    with open(file_path, "w", encoding=encoding) as f:
        json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
    logger.info(f"Write JSON data to '{file_path}'")


# ========================
# JSONL 文件读写
# ========================

def read_jsonl(file_path: PathLike, encoding: str = "utf-8") -> List[Any]:
    """
    读取 JSONL 文件（每行一个 JSON 对象）。

    参数:
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。

    返回:
        每行解析后的对象列表。
    """
    file_path = _to_path(file_path)
    with open(file_path, "r", encoding=encoding) as f:
        data = [json.loads(line) for line in f if line.strip()]
    logger.info(f"Read {len(data)} JSON objects from '{file_path}'")
    return data


def write_jsonl(
    data: List[Any],
    file_path: PathLike,
    encoding: str = "utf-8",
    append: bool = False,
) -> None:
    """
    写入 JSONL 文件（每行一个 JSON 对象）。

    参数:
        data: 要写入的对象列表。
        file_path: 文件路径。
        encoding: 文件编码，默认 utf-8。
        append: 是否追加写入，默认 False。
    """
    file_path = _to_path(file_path)
    _ensure_parent(file_path)
    mode = "a" if append else "w"
    with open(file_path, mode, encoding=encoding) as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    logger.info(f"Write {len(data)} JSON objects to '{file_path}'")


# ========================
# Parquet 文件读写
# ========================

def read_parquet(
    file_root: PathLike,
    engine: str = "auto",
    ignore: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    读取 Parquet 文件或目录。

    参数:
        file_root: 文件路径或包含多个 Parquet 分片的目录路径。
        engine: Parquet 引擎，默认 'auto'。
        ignore: 目录模式下需要忽略的文件名关键词列表，默认 ['_SUCCESS']。

    返回:
        合并后的 DataFrame；读取失败时返回空 DataFrame。
    """
    if ignore is None:
        ignore = ["_SUCCESS"]

    file_root = _to_path(file_root)

    # ---------- 单文件 ----------
    if file_root.is_file():
        try:
            data = pd.read_parquet(file_root, engine=engine)
            logger.info(f"Read Parquet file '{file_root}'. Shape: {data.shape}")
            _log_dataframe_info(data)
            return data
        except Exception as e:
            logger.error(f"Error reading '{file_root}': {e}")
            return pd.DataFrame()

    # ---------- 目录 ----------
    if file_root.is_dir():
        # 优先尝试引擎原生目录读取
        try:
            data = pd.read_parquet(file_root, engine=engine)
            logger.info(f"Read Parquet dir '{file_root}'. Shape: {data.shape}")
            _log_dataframe_info(data)
            return data
        except Exception as e:
            logger.error(
                f"Error: {e}, falling back to per-file reading."
            )

        # 逐文件读取并拼接
        chunks: List[pd.DataFrame] = []
        for name in tqdm(
            sorted(os.listdir(file_root)),
            desc="Reading Parquet files",
            leave=False,
        ):
            if any(kw in name for kw in ignore):
                continue
            part_path = file_root / name
            if not part_path.is_file():
                continue
            try:
                chunk = pd.read_parquet(part_path, engine=engine)
                logger.info(f"Read '{name}'. Shape: {chunk.shape}")
                chunks.append(chunk)
            except Exception as e:
                logger.error(f"Error reading '{part_path}': {e}")

        if chunks:
            data = pd.concat(chunks, ignore_index=True)
            logger.info(
                f"Concatenated {len(chunks)} Parquet files. Shape: {data.shape}"
            )
            _log_dataframe_info(data)
            return data

        logger.warning(f"No valid Parquet data found in '{file_root}'")
        return pd.DataFrame()

    raise FileNotFoundError(f"Path does not exist: {file_root}")


def write_parquet(df: pd.DataFrame, file_path: PathLike, **kwargs: Any) -> None:
    """
    写入 Parquet 文件。

    参数:
        df: 要写入的 DataFrame。
        file_path: 文件路径。
        **kwargs: 传递给 DataFrame.to_parquet 的额外参数。
    """
    file_path = _to_path(file_path)
    _ensure_parent(file_path)
    df.to_parquet(file_path, **kwargs)
    logger.info(f"Write Parquet '{file_path}'. Shape: {df.shape}")


def _log_dataframe_info(df: pd.DataFrame) -> None:
    """将 DataFrame.info() 输出写入日志。"""
    buf = StringIO()
    df.info(buf=buf)
    logger.info(f"\n{buf.getvalue()}")


# ========================
# Pickle 文件读写
# ========================

def read_pickle(file_path: PathLike, **kwargs: Any) -> Any:
    """
    读取 Pickle 文件。

    参数:
        file_path: 文件路径。
        **kwargs: 传递给 pickle.load 的额外参数。

    返回:
        反序列化后的 Python 对象。
    """
    file_path = _to_path(file_path)
    with open(file_path, "rb") as f:
        data = pickle.load(f, **kwargs)
    logger.info(f"Read Pickle '{file_path}'")
    return data


def write_pickle(obj: Any, file_path: PathLike, **kwargs: Any) -> None:
    """
    写入 Pickle 文件。

    参数:
        obj: 要序列化的 Python 对象。
        file_path: 文件路径。
        **kwargs: 传递给 pickle.dump 的额外参数。
    """
    file_path = _to_path(file_path)
    _ensure_parent(file_path)
    with open(file_path, "wb") as f:
        pickle.dump(obj, f, **kwargs)
    logger.info(f"Write Pickle '{file_path}'")


# ========================
# 统一入口 (Dispatcher)
# ========================

_READ_DISPATCH = {
    ".json": read_json,
    ".jsonl": read_jsonl,
    ".parquet": read_parquet,
    ".csv": read_csv,
    ".tsv": lambda p, **kw: read_csv(p, sep="\t", **kw),
    ".txt": read_txt,
    ".pickle": read_pickle,
    ".pkl": read_pickle,
}

_WRITE_DISPATCH = {
    ".json": write_json,
    ".jsonl": write_jsonl,
    ".parquet": write_parquet,
    ".csv": write_csv,
    ".tsv": lambda d, p, **kw: write_csv(d, p, sep="\t", **kw),
    ".txt": write_txt,
    ".pickle": write_pickle,
    ".pkl": write_pickle,
}


def read_file(file_path: PathLike, **kwargs: Any) -> Any:
    """
    根据文件后缀自动选择读取函数。

    支持: .json / .jsonl / .parquet / .csv / .tsv / .txt / .pickle / .pkl
    """
    path = _to_path(file_path)
    suffix = path.suffix.lower()
    reader = _READ_DISPATCH.get(suffix)
    if reader is None:
        raise ValueError(
            f"Unsupported file format: {suffix!r}. "
            f"Supported: {sorted(_READ_DISPATCH.keys())}"
        )
    return reader(path, **kwargs)


def write_file(data: Any, file_path: PathLike, **kwargs: Any) -> None:
    """
    根据文件后缀自动选择写入函数。

    支持: .json / .jsonl / .parquet / .csv / .tsv / .txt / .pickle / .pkl
    """
    path = _to_path(file_path)
    suffix = path.suffix.lower()
    writer = _WRITE_DISPATCH.get(suffix)
    if writer is None:
        raise ValueError(
            f"Unsupported file format: {suffix!r}. "
            f"Supported: {sorted(_WRITE_DISPATCH.keys())}"
        )
    writer(data, path, **kwargs)