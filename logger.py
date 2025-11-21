import sys
import logging

try:
    from loguru import logger as loguru_logger
    HAS_LOGURU = True
except ImportError:
    HAS_LOGURU = False

# 如果没有 loguru，使用 logging 作为后备
if not HAS_LOGURU:
    logging_logger = logging.getLogger(__name__)
    logging_logger.propagate = False
else:
    logging_logger = None


def setup_logger(level="INFO", output_file=None):
    """
    配置日志系统，支持 loguru 和 logging。
    :param level: 日志级别（字符串，如 "DEBUG", "INFO"）
    :param output_file: 日志输出文件路径
    """
    level = level.upper()
    if HAS_LOGURU:
        # 清除所有已有 sink
        loguru_logger.remove()

        # 添加控制台 sink
        loguru_logger.add(
            sys.stderr,
            level=level
        )

        # 添加文件 sink（如果提供）
        if output_file:
            loguru_logger.add(
                output_file,
                level=level
            )
    else:
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        log_level = level_map.get(level.upper(), logging.INFO)
        # fmt = logging.Formatter('%(asctime)s - %(name)s[%(lineno)d] - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fmt = logging.Formatter('%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        # 清除已有 handler
        for handler in logging_logger.handlers[:]:
            logging_logger.removeHandler(handler)

        # 添加控制台 handler
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(fmt)
        console_handler.setLevel(log_level)
        logging_logger.addHandler(console_handler)

        # 添加文件 handler（如果提供）
        if output_file:
            file_handler = logging.FileHandler(output_file)
            file_handler.setFormatter(fmt)
            file_handler.setLevel(log_level)
            logging_logger.addHandler(file_handler)

        # 设置 logger 的最低级别
        logging_logger.setLevel(log_level)


class _LoggerWrapper:
    def debug(self, msg, *args, **kwargs):
        if HAS_LOGURU:
            loguru_logger.opt(depth=1).debug(msg, *args, **kwargs)
        else:
            logging_logger.log(logging.DEBUG, msg, *args, **kwargs, stacklevel=2)

    def info(self, msg, *args, **kwargs):
        if HAS_LOGURU:
            loguru_logger.opt(depth=1).info(msg, *args, **kwargs)
        else:
            logging_logger.log(logging.INFO, msg, *args, **kwargs, stacklevel=2)

    def warning(self, msg, *args, **kwargs):
        if HAS_LOGURU:
            loguru_logger.opt(depth=1).warning(msg, *args, **kwargs)
        else:
            logging_logger.log(logging.WARNING, msg, *args, **kwargs, stacklevel=2)

    def error(self, msg, *args, **kwargs):
        if HAS_LOGURU:
            loguru_logger.opt(depth=1).error(msg, *args, **kwargs)
        else:
            logging_logger.log(logging.ERROR, msg, *args, **kwargs, stacklevel=2)

    def critical(self, msg, *args, **kwargs):
        if HAS_LOGURU:
            loguru_logger.opt(depth=1).critical(msg, *args, **kwargs)
        else:
            logging_logger.log(logging.CRITICAL, msg, *args, **kwargs, stacklevel=2)


# 提供统一的 logger 接口
logger = _LoggerWrapper()