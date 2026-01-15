from .logger import logger
import csv
import json
import pandas as pd
import os
from tqdm import tqdm
from io import StringIO
from typing import List, Optional, Any
from pathlib import Path

# ========================
# TXT 文件读写
# ========================

def read_txt(file_path, encoding='utf-8', as_lines=True):
    """
    读取 TXT 文件内容。

    参数:
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。
        as_lines (bool): 是否按行读取，默认 True

    返回:
        str 或 list: 文件内容，若 as_lines=True 返回行列表。
    """
    with open(file_path, 'r', encoding=encoding) as f:
        if as_lines:
            content = [line.strip() for line in f.readlines()]
            logger.info(f"Read {len(content)} lines from '{file_path}'")
        else:
            content = f.read()
            logger.info(f"Read {len(content)} characters from '{file_path}'")
        return content


def write_txt(content, file_path, encoding='utf-8', append=False):
    """
    写入 TXT 文件内容。

    参数:
        content (str 或 list): 要写入的内容。
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。
        append (bool): 是否追加写入，默认 False。
    """
    mode = 'a' if append else 'w'
    with open(file_path, mode, encoding=encoding) as f:
        if isinstance(content, list):
            content_ = [line + '\n' for line in content]
            f.writelines(content_)
            logger.info(f"Write {len(content_)} lines to '{file_path}' in {'append' if append else 'write'} mode")
        else:
            f.write(content)
            logger.info(f"Write {len(content)} characters to '{file_path}' in {'append' if append else 'write'} mode")


# ========================
# CSV 文件读写
# ========================

def read_csv(file_path, encoding='utf-8', sep=',', format='dataframe', skip_header=True, **kwargs):
    """
    读取 CSV 文件。

    参数:
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。
        sep (str): 分隔符，默认 ','。
        format (str): 读取格式，'dataframe' 或 'list'，默认 'dataframe'。
        skip_header (bool): 是否跳过第一行，默认 True。
        **kwargs: 传递给 pandas.read_csv 的额外参数。

    返回:
        pd.DataFrame 或 list: 文件内容。
    """

    if format == 'dataframe':
        df = pd.read_csv(file_path, sep=sep, encoding=encoding, **kwargs)
        logger.info(f"CSV file header: {df.columns.tolist()}")
        logger.info(f"Read CSV file '{file_path}' as DataFrame. Shape: {df.shape}")
        return df
    elif format == 'list':
        with open(file_path, 'r', encoding=encoding) as f:
            reader = csv.reader(f, delimiter=sep, **kwargs)
            if skip_header:
                header = next(reader, None)
                if header:
                    logger.info(f"Skipped CSV header: {header}")
            data = list(reader)
            logger.info(f"Read CSV file '{file_path}' as list. Rows: {len(data)}")
            return data
    else:
        raise ValueError(f"Unsupported format: {format}. Choose 'dataframe' or 'list'.")


def write_csv(data, file_path, encoding='utf-8', append=False, sep=',', header: Optional[List[str]] = None, **kwargs):
    """
    写入 CSV 文件。

    参数:
        data (list 或 pd.DataFrame): 要写入的数据。
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。
        append (bool): 是否追加写入，默认 False。
        sep (str): 分隔符，默认 ','。
        format (str): 写入格式，'dataframe' 或 'list'，默认 'dataframe'。
        header (list): 列名，默认 None。
        **kwargs: 传递给 pandas.to_csv 的额外参数。
    """
    mode = 'a' if append else 'w'
    if isinstance(data, dict):
        data = pd.DataFrame(data)
    if isinstance(data, pd.DataFrame):
        data.to_csv(file_path, index=False, sep=sep, mode=mode, encoding=encoding, **kwargs)
        logger.info(f"Write DataFrame to '{file_path}' in {'append' if append else 'write'} mode. Shape: {data.shape}")
    elif isinstance(data, list):
        with open(file_path, mode, newline='', encoding=encoding) as f:
            writer = csv.writer(f, delimiter=sep)
            if header:
                logger.info(f"CSV file header: {header}")
                writer.writerow(header)
            writer.writerows(data)
            logger.info(f"Write {len(data)} rows to '{file_path}' in {'append' if append else 'write'} mode")
    else:
        raise ValueError(f"Unsupported format: {type(data)}. supported: pd.DataFrame, list, dict")


# ========================
# JSON 文件读写
# ========================

def read_json(file_path, encoding='utf-8'):
    """
    读取 JSON 文件。

    参数:
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。

    返回:
        dict: 文件内容。
    """
    with open(file_path, 'r', encoding=encoding) as f:
        data = json.load(f)
        logger.info(f"Read JSON file '{file_path}' successfully, rows: {len(data)}")
        return data


def write_json(data, file_path, encoding='utf-8', ensure_ascii=False, indent=4):
    """
    写入 JSON 文件。

    参数:
        data (dict): 要写入的数据。
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。
        ensure_ascii (bool): 是否确保 ASCII 编码，默认 False。
        indent (int): 缩进空格数，默认 4。
    """
    with open(file_path, 'w', encoding=encoding) as f:
        json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
        logger.info(f"Write JSON data to '{file_path}'")


# ========================
# JSONL 文件读写
# ========================

def read_jsonl(file_path, encoding='utf-8'):
    """
    读取 JSONL 文件（每行一个 JSON 对象）。

    参数:
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。

    返回:
        list: 每行解析后的对象列表。
    """
    with open(file_path, 'r', encoding=encoding) as f:
        data = [json.loads(line) for line in f if line.strip()]
        logger.info(f"Read {len(data)} JSON objects from '{file_path}'")
        return data


def write_jsonl(data, file_path, encoding='utf-8'):
    """
    写入 JSONL 文件（每行一个 JSON 对象）。

    参数:
        data (list): 要写入的对象列表。
        file_path (str): 文件路径。
        encoding (str): 文件编码，默认 utf-8。
    """
    with open(file_path, 'w', encoding=encoding) as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
        logger.info(f"Write {len(data)} JSON objects to '{file_path}'")


# ========================
# Parquet 文件读写
# ========================

def read_parquet(file_root, engine: str = 'auto', ignore=['_SUCCESS'])->pd.DataFrame:
    """
    读取 Parquet 文件。

    参数:
        file_root (str): 文件路径或目录路径。
        header_name (str): 列名，默认 None。

    返回:
        pd.DataFrame 或 list: 文件内容。
    """
    if os.path.isfile(file_root):
        try:
            data = pd.read_parquet(file_root, engine=engine)
            logger.info(f"Successfully read Parquet file from '{file_root}'. Shape: {data.shape}")
            buffer = StringIO()
            data.info(buf=buffer)
            logger.info(f'\n{buffer.getvalue()}')
            return data
        except Exception as e:
            logger.error(f"Error reading {file_root}: {e}")
            return pd.DataFrame()

    elif os.path.isdir(file_root):
        # 尝试使用 Pandas 原生引擎读取整个目录（通常更快）
        try:
            data = pd.read_parquet(file_root, engine=engine)
            logger.info(f"Successfully read Parquet dir from '{file_root}'. Shape: {data.shape}")
            return data
        except Exception:
            file_names = os.listdir(file_root)
            all_chunks = []
            for file_name in tqdm(file_names, desc="Reading Parquet files", leave=False):
                if any(ignore_name in file_name for ignore_name in ignore):
                    continue
                file_path = os.path.join(file_root, file_name)
                try:
                    chunks = pd.read_parquet(file_path)
                    logger.info(f"Read Parquet file from '{file_path}'. Shape: {chunks.shape}")
                    all_chunks.append(chunks)
                    del chunks
                except Exception as e:
                    logger.error(f"Error reading {file_path}: {e}")

            # 将所有块合并成一个 DataFrame
            if all_chunks:
                data = pd.concat(all_chunks, ignore_index=True)
                logger.info(f"Successfully concatenated {len(all_chunks)} Parquet files. Shape: {data.shape}")
                buffer = StringIO()
                data.info(buf=buffer)
                logger.info(f'\n{buffer.getvalue()}')
                return data
            else:
                logger.error(f"No data found in directory {file_root}")
                return pd.DataFrame()


def write_parquet(df:pd.DataFrame, file_path, **kwargs):
    """
    写入 Parquet 文件。

    参数:
        df (pd.DataFrame): 要写入的 DataFrame。
        file_path (str): 文件路径。
        **kwargs: 传递给 DataFrame.to_parquet 的额外参数。
    """
    df.to_parquet(file_path, **kwargs)
    logger.info(f"Write Parquet file '{file_path}'. Shape: {df.shape}")

# ========================
# 统一入口 (Dispatcher)
# ========================

def read_file(file_path, **kwargs) -> Any:
    """
    根据文件后缀自动选择读取函数。
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    dispatcher = {
        '.json': read_json,
        '.jsonl': read_jsonl,
        '.parquet': read_parquet,
        '.csv': read_csv,
        '.txt': read_txt
    }

    if suffix in dispatcher:
        return dispatcher[suffix](path, **kwargs)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def write_file(data: Any, file_path, **kwargs) -> None:
    """
    根据文件后缀自动选择写入函数。
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    dispatcher = {
        '.json': write_json,
        '.jsonl': write_jsonl,
        '.parquet': write_parquet,
        '.csv': write_csv,
        '.txt': write_txt
    }

    if suffix in dispatcher:
        dispatcher[suffix](data, path, **kwargs)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

