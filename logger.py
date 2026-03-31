"""
可复用日志模块 —— 提供彩色控制台输出、可选文件轮转输出。

使用方式：
    # 方式一：开箱即用的默认 logger（INFO 级别，仅控制台输出）
    from logger import logger

    # 方式二：自定义初始化
    from logger import init_logger
    logger = init_logger(log_level="DEBUG", save_to="logs/app.log")

    # 方式三：运行时动态调整级别
    from logger import set_level
    set_level(logger, "DEBUG")
"""

import os
import sys
import logging
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Union

# ============================================================================
# 线程安全锁 & 已初始化 Logger 追踪
# ============================================================================
_lock = threading.Lock()
_initialized: set[str] = set()

# ============================================================================
# 颜色定义 —— ANSI 转义码
# ============================================================================
_COLORS: dict[str, str] = {
    "DEBUG":    "\033[94m",   # 蓝色
    "INFO":     "\033[92m",   # 绿色
    "WARNING":  "\033[93m",   # 黄色
    "ERROR":    "\033[91m",   # 红色
    "CRITICAL": "\033[1;91m", # 高亮红（加粗 + 红色）
}
_RESET = "\033[0m"

# ============================================================================
# 日志格式模板
# ============================================================================
_FILE_FMT = "%(asctime)s │ %(levelname)-8s │ %(name)s │ %(filename)s:%(lineno)d │ %(funcName)s │ %(message)s"
_CONSOLE_FMT    = "%(asctime)s │ %(levelname)-8s │ %(name)s │ %(filename)s:%(lineno)d │ %(message)s"
_DATE_FMT    = "%Y-%m-%d %H:%M:%S"

# ============================================================================
# 文件轮转默认参数
# ============================================================================
_DEFAULT_MAX_BYTES    = 10 * 1024 * 1024  # 单个日志文件上限 10 MB
_DEFAULT_BACKUP_COUNT = 5                  # 保留最近 5 个备份


# ============================================================================
# 终端 ANSI 支持检测
# ============================================================================
def _supports_ansi() -> bool:
    """
    检测当前标准输出是否支持 ANSI 转义码。
    - Windows 10+ 的新版终端支持 ANSI，但 cmd.exe 需额外开启。
    - 非 TTY（如 CI/CD 日志、管道重定向）一律禁用颜色。
    """
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        return os.environ.get("ANSICON") is not None or "WT_SESSION" in os.environ
    return True


_ANSI_ENABLED: bool = _supports_ansi()


# ============================================================================
# 自定义 Formatter —— 为控制台输出注入 ANSI 颜色（预缓存格式串）
# ============================================================================
class _ColorFormatter(logging.Formatter):
    """
    预构建每个日志级别的着色格式串，避免每次 format() 动态拼接。
    在不支持 ANSI 的终端中自动退化为无色输出。
    """

    def __init__(self, fmt: str, datefmt: str) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        if _ANSI_ENABLED:
            self._level_formats: dict[int, logging.Formatter] = {}
            for level_name, color in _COLORS.items():
                colored_fmt = fmt.replace(
                    "%(levelname)-8s",
                    f"{color}%(levelname)-8s{_RESET}",
                )
                level_num = getattr(logging, level_name)
                self._level_formats[level_num] = logging.Formatter(
                    fmt=colored_fmt, datefmt=datefmt
                )
        else:
            self._level_formats = {}

    def format(self, record: logging.LogRecord) -> str:
        formatter = self._level_formats.get(record.levelno)
        if formatter:
            return formatter.format(record)
        return super().format(record)


# ============================================================================
# 工具函数
# ============================================================================
def _resolve_level(level: Union[str, int, None]) -> int:
    """
    将日志级别参数统一解析为 logging 整型常量。
    - 接受字符串（不区分大小写）或整型
    - 无效值自动回退到 INFO 并在 stderr 打印提示
    """
    if level is None:
        return logging.INFO
    if isinstance(level, int):
        return level
    numeric = getattr(logging, str(level).upper(), None)
    if numeric is None:
        print(
            f"[logger] WARNING: 无法识别日志级别 '{level}'，已回退到 INFO",
            file=sys.stderr,
        )
        return logging.INFO
    return numeric


def _resolve_file_path(save_to: Union[bool, str, Path, None]) -> Optional[str]:
    """
    根据 save_to 参数决定日志文件路径：
      - False / None  → 不输出到文件
      - True          → 自动生成 logs/YYYYMMDD_HHMMSS.log
      - str / Path    → 使用指定路径
    自动创建不存在的父目录。
    """
    if not save_to:
        return None

    if save_to is True:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".log"
        return str(log_dir / filename)

    path = Path(save_to)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def set_level(target_logger: logging.Logger, level: Union[str, int]) -> None:
    """
    运行时动态调整 Logger 及其所有 Handler 的日志级别。

    用法：
        set_level(logger, "DEBUG")
        set_level(logger, logging.WARNING)
    """
    resolved = _resolve_level(level)
    target_logger.setLevel(resolved)
    for handler in target_logger.handlers:
        handler.setLevel(resolved)


# ============================================================================
# 核心初始化函数
# ============================================================================
def init_logger(
    name: str = "DefaultLogger",
    log_level: Union[str, int, None] = None,
    save_to: Union[bool, str, Path, None] = False,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    backup_count: int = _DEFAULT_BACKUP_COUNT,
) -> logging.Logger:
    """
    创建并返回一个已完成初始化的 Logger 实例。

    参数：
        name         : Logger 名称，不同名称对应不同 Logger 实例。
        log_level    : 日志级别（str / int），默认读取环境变量 LOG_LEVEL，
                       若未设置则回退到 INFO。
        save_to      : 文件输出控制：
                         - False(default) : 不输出到文件（可通过 LOG_FILE 环境变量覆盖）
                         - True           : 输出到 logs/YYYYMMDD_HHMMSS.log
                         - str / Path     : 输出到指定路径
        max_bytes    : 单个日志文件大小上限（字节），默认 10 MB。
        backup_count : 文件轮转保留的备份数量，默认 5。

    返回：
        配置好的 logging.Logger 实例。

    幂等保证：
        同一 name 仅初始化一次。如需重新配置，请先调用
        `reset_logger(name)` 再重新初始化。
    """
    with _lock:
        # ── 1. 幂等守卫 ──────────────────────────────────────
        if name in _initialized:
            return logging.getLogger(name)

        # ── 2. 确定日志级别 ──────────────────────────────────
        if log_level is not None:
            level = _resolve_level(log_level)
        else:
            env_level = os.environ.get("LOG_LEVEL")
            level = _resolve_level(env_level) if env_level else logging.INFO

        # ── 3. 创建 Logger ───────────────────────────────────
        _logger = logging.getLogger(name)
        _logger.setLevel(level)
        _logger.handlers.clear()

        # ── 4. 控制台 Handler（stdout）───────────────────────
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(
            _ColorFormatter(fmt=_CONSOLE_FMT, datefmt=_DATE_FMT)
        )
        _logger.addHandler(console_handler)

        # ── 5. 文件 Handler（RotatingFileHandler）────────────
        #   优先使用显式 save_to；其次尝试环境变量 LOG_FILE
        effective_save_to = save_to
        if not effective_save_to:
            env_file = os.environ.get("LOG_FILE")
            if env_file:
                effective_save_to = env_file

        file_path = _resolve_file_path(effective_save_to)
        if file_path:
            file_handler = RotatingFileHandler(
                file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(
                logging.Formatter(fmt=_FILE_FMT, datefmt=_DATE_FMT)
            )
            _logger.addHandler(file_handler)

        # ── 6. 阻止向上传播 ─────────────────────────────────
        _logger.propagate = False

        _initialized.add(name)
        return _logger


def reset_logger(name: str) -> None:
    """
    重置指定 Logger，允许下一次 init_logger 重新配置。
    已有的 handler 会被关闭并移除。
    """
    with _lock:
        _initialized.discard(name)
        _logger = logging.getLogger(name)
        for handler in _logger.handlers[:]:
            handler.close()
            _logger.removeHandler(handler)


# ============================================================================
# 模块级默认 logger 实例 —— 开箱即用
# ============================================================================
logger: logging.Logger = init_logger(name="DefaultLogger")


# ============================================================================
# 公开 API
# ============================================================================
__all__ = ["logger", "init_logger", "reset_logger", "set_level"]


# ============================================================================
# 示例 & 自测
# ============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print(" 示例 1：使用默认全局 logger（仅控制台，INFO 级别）")
    print("=" * 70)
    logger.debug("这条 DEBUG 消息默认不会显示（级别低于 INFO）")
    logger.info("应用启动成功")
    logger.warning("磁盘使用率超过 80%%")
    logger.error("数据库连接失败")
    logger.critical("系统内存不足，即将崩溃！")

    print()
    print("=" * 70)
    print(" 示例 2：自定义 logger（DEBUG 级别 + 文件轮转输出）")
    print("=" * 70)
    custom_logger = init_logger(
        name="custom_logger",
        log_level="DEBUG",
        save_to=True,
    )
    custom_logger.debug("自定义 logger 的 DEBUG 消息")
    custom_logger.info("自定义 logger 的 INFO 消息")
    custom_logger.warning("自定义 logger 的 WARNING 消息")
    custom_logger.error("自定义 logger 的 ERROR 消息")
    custom_logger.critical("自定义 logger 的 CRITICAL 消息")

    print()
    print("=" * 70)
    print(" 示例 3：指定日志文件路径")
    print("=" * 70)
    path_logger = init_logger(
        name="path_demo",
        log_level="WARNING",
        save_to="logs/demo.log",
    )
    path_logger.info("这条 INFO 不会显示（低于 WARNING）")
    path_logger.warning("写入指定路径 logs/demo.log")
    path_logger.error("错误信息也会同时写入文件")

    print()
    print("=" * 70)
    print(" 示例 4：运行时动态调整级别")
    print("=" * 70)
    set_level(path_logger, "DEBUG")
    path_logger.debug("调整后，这条 DEBUG 可以显示了")

    print()
    print("=" * 70)
    print(" 示例 5：重置并重新配置 logger")
    print("=" * 70)
    reset_logger("path_demo")
    path_logger = init_logger(name="path_demo", log_level="INFO")
    path_logger.info("重置后重新初始化的 logger")

    print()
    print("日志文件请查看 logs/ 目录。")