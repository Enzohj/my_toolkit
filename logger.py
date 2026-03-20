"""
统一日志模块，自动适配 loguru / logging。

日志级别优先级（从高到低）：
  1. setup_logger(level=...) 显式传参
  2. 环境变量 LOG_LEVEL（不区分大小写）
  3. 默认值 "INFO"

使用方式：
    from logger import logger, setup_logger

    # 可选：手动初始化（不调用也会使用环境变量或默认级别）
    setup_logger(level="DEBUG", output_file="app.log")

    logger.info("Hello {}", "world")   # loguru 风格占位符（有 loguru 时）
    logger.error("oops: %s", err)      # logging 风格占位符（无 loguru 时）
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# 检测 loguru
# ---------------------------------------------------------------------------
try:
    from loguru import logger as _loguru_logger

    HAS_LOGURU = True
except ImportError:
    _loguru_logger = None  # type: ignore[assignment]
    HAS_LOGURU = False

# ---------------------------------------------------------------------------
# logging 后备 logger（仅在无 loguru 时启用）
# ---------------------------------------------------------------------------
_logging_logger: Optional[logging.Logger] = None
if not HAS_LOGURU:
    _logging_logger = logging.getLogger(__name__)
    _logging_logger.propagate = False

# ---------------------------------------------------------------------------
# 有效日志级别集合 & 工具函数
# ---------------------------------------------------------------------------
_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _resolve_level(explicit: Optional[str] = None) -> str:
    """
    按优先级解析最终日志级别：
      显式传参 > 环境变量 LOG_LEVEL > 默认 INFO
    """
    if explicit is not None:
        level = explicit.upper()
    else:
        level = os.environ.get("LOG_LEVEL", "INFO").upper()

    if level not in _VALID_LEVELS:
        fallback = "INFO"
        print(
            f"[logger] Invalid log level '{level}', falling back to '{fallback}'.",
            file=sys.stderr,
        )
        level = fallback
    return level


# ---------------------------------------------------------------------------
# setup_logger
# ---------------------------------------------------------------------------
def setup_logger(
    level: Optional[str] = None,
    output_file: Optional[str] = None,
) -> None:
    """
    配置日志系统，支持 loguru 和 logging。

    :param level:       日志级别字符串（如 "DEBUG"）。
                        为 None 时读取环境变量 LOG_LEVEL，仍无则默认 INFO。
    :param output_file: 日志输出文件路径（可选）。
    """
    resolved = _resolve_level(level)

    if HAS_LOGURU:
        _loguru_logger.remove()
        _loguru_logger.add(sys.stderr, level=resolved)
        if output_file:
            _loguru_logger.add(output_file, level=resolved)
    else:
        assert _logging_logger is not None
        log_level = getattr(logging, resolved, logging.INFO)
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 清除已有 handler
        for handler in _logging_logger.handlers[:]:
            _logging_logger.removeHandler(handler)

        # 控制台
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(fmt)
        console.setLevel(log_level)
        _logging_logger.addHandler(console)

        # 文件（可选）
        if output_file:
            fh = logging.FileHandler(output_file)
            fh.setFormatter(fmt)
            fh.setLevel(log_level)
            _logging_logger.addHandler(fh)

        _logging_logger.setLevel(log_level)


# ---------------------------------------------------------------------------
# _LoggerWrapper —— 统一对外接口
# ---------------------------------------------------------------------------
class _LoggerWrapper:
    """对 loguru / logging 的轻量包装，提供统一调用接口。"""

    _LEVELS = ("debug", "info", "warning", "error", "critical")

    def __getattr__(self, name: str):
        """
        动态分发：logger.info(...) → loguru_logger.opt(depth=1).info(...)
                                   或 logging_logger.log(INFO, ..., stacklevel=2)
        """
        if name in self._LEVELS:
            if HAS_LOGURU:
                return getattr(_loguru_logger.opt(depth=1), name)
            else:
                log_level = getattr(logging, name.upper())

                def _log(msg, *args, **kwargs):
                    _logging_logger.log(log_level, msg, *args, **kwargs, stacklevel=2)

                return _log
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def exception(self, msg, *args, **kwargs):
        """记录 ERROR 级别日志并附带当前异常堆栈。"""
        if HAS_LOGURU:
            _loguru_logger.opt(depth=1).exception(msg, *args, **kwargs)
        else:
            _logging_logger.log(
                logging.ERROR, msg, *args, exc_info=True, **kwargs, stacklevel=2
            )


# ---------------------------------------------------------------------------
# 模块初始化：根据环境变量设置默认级别
# ---------------------------------------------------------------------------
setup_logger()  # 首次 import 时自动按环境变量 / 默认值初始化

# 对外统一接口
logger = _LoggerWrapper()