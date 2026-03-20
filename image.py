"""
image.py - 通用图像处理工具模块

提供多种图像格式之间的转换函数（URL/本地路径、bytes、base64、Pillow Image），
以及统一的 MyImage 类，可接收多种输入并自动识别格式。

主要功能:
    - 多格式互转: URL/本地路径 ↔ bytes ↔ base64 ↔ Pillow Image
    - 自动格式识别: 基于 magic bytes / 文件后缀 / data URL 前缀
    - MyImage 统一封装: 接收任意来源，提供一致的属性与方法接口

典型用法::

    # 从 URL 加载
    image = MyImage(url="https://example.com/photo.jpg")

    # 从本地文件加载
    image = MyImage(path="/tmp/photo.png")

    # 获取 base64
    b64_str = image.base64

    # 转换格式并保存
    image.convert("webp").save("/tmp/photo.webp")
"""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path
from typing import Optional, Union

import requests

import pillow_heif

pillow_heif.register_heif_opener()

from PIL import Image, ExifTags

from .logger import logger

# ---------------------------------------------------------------------------
# 常量与辅助
# ---------------------------------------------------------------------------

# 支持的图像格式集合（统一小写）
SUPPORTED_FORMATS: frozenset[str] = frozenset(
    {"png", "jpeg", "webp", "heif", "gif", "bmp", "tiff", "ico"}
)

# 格式别名映射（统一到标准名称）
_FORMAT_ALIASES: dict[str, str] = {
    "jpg": "jpeg",
    "jpe": "jpeg",
    "jfif": "jpeg",
    "tif": "tiff",
    "heic": "heif",
}

# Pillow Image.save() 所接受的 format 参数映射
_PILLOW_SAVE_FORMAT: dict[str, str] = {
    "jpeg": "JPEG",
    "jpg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "gif": "GIF",
    "bmp": "BMP",
    "tiff": "TIFF",
    "ico": "ICO",
    "heif": "HEIF",
}

_DEFAULT_FORMAT: str = "jpeg"

# 文件头 magic bytes 映射（按匹配优先级排列）
_MAGIC_BYTES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
    (b"II\x2a\x00", "tiff"),
    (b"MM\x00\x2a", "tiff"),
    # RIFF 容器需要额外判断子类型，单独处理
    # HEIF/HEIC 的 ftyp box 长度可变，单独处理
]

# data-URL 正则：匹配 data:image/<fmt>;base64, 前缀
_DATA_URL_RE: re.Pattern[str] = re.compile(
    r"^\s*data:image/(?P<fmt>[a-zA-Z0-9.+-]+);base64,", re.IGNORECASE
)

# 下载相关默认配置
_DEFAULT_DOWNLOAD_TIMEOUT: int = 30
_MAX_DOWNLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB


# ---------------------------------------------------------------------------
# 异常定义
# ---------------------------------------------------------------------------


class ImageError(Exception):
    """图像处理基础异常。"""


class ImageFormatError(ImageError):
    """不支持或无法识别的图像格式。"""


class ImageDownloadError(ImageError):
    """图像下载失败。"""


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _normalize_format(fmt: Optional[str]) -> Optional[str]:
    """统一格式字符串：小写化，并将常见别名映射为标准名称。

    Args:
        fmt: 原始格式字符串，可为 None。

    Returns:
        标准化后的格式字符串，或 None（当输入为 None / 空字符串时）。

    Examples:
        >>> _normalize_format("JPG")
        'jpeg'
        >>> _normalize_format("TIFF")
        'tiff'
        >>> _normalize_format(None)
        None
    """
    if not fmt:
        return None
    fmt = fmt.strip().lower()
    if not fmt:
        return None
    return _FORMAT_ALIASES.get(fmt, fmt)


def _guess_format_from_suffix(path_or_url: str) -> Optional[str]:
    """尝试从文件路径或 URL 的后缀推断图像格式。

    Args:
        path_or_url: 文件路径或 URL 字符串。

    Returns:
        推断出的格式（已标准化），或 None。
    """
    # 去掉查询参数与锚点
    clean = path_or_url.split("?")[0].split("#")[0]
    suffix = Path(clean).suffix  # 包含 '.'
    if not suffix:
        return None

    fmt = _normalize_format(suffix.lstrip("."))
    if fmt and fmt in SUPPORTED_FORMATS:
        logger.debug("从后缀 '%s' 推断格式: %s", suffix, fmt)
        return fmt

    logger.warning("后缀 '%s' 对应的格式 '%s' 不在支持列表中", suffix, fmt)
    return None


def _guess_format_from_bytes(data: bytes) -> Optional[str]:
    """通过 magic bytes 或 Pillow 从原始字节推断格式。

    Args:
        data: 原始图像字节数据（至少需要前 32 字节用于判断）。

    Returns:
        推断出的格式（已标准化），或 None。
    """
    if not data:
        return None

    # 1. 标准 magic bytes 匹配
    for magic, fmt in _MAGIC_BYTES:
        if data[: len(magic)] == magic:
            logger.debug("通过 magic bytes 识别格式: %s", fmt)
            return fmt

    # 2. RIFF 容器 → 检查是否为 WEBP
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        logger.debug("通过 magic bytes 识别格式: webp")
        return "webp"

    # 3. 回退到 Pillow 解析
    try:
        with Image.open(io.BytesIO(data)) as img:
            pil_fmt = _normalize_format(img.format)
            if pil_fmt:
                logger.debug("通过 Pillow 识别格式: %s", pil_fmt)
                return pil_fmt
    except Exception:
        logger.warning("无法从 bytes 识别格式")

    return None


def _pillow_save_format(fmt: str) -> str:
    """返回 Pillow ``Image.save`` 所接受的 format 参数值。"""
    return _PILLOW_SAVE_FORMAT.get(fmt, fmt.upper())


def _ensure_rgb_for_jpeg(img: Image.Image) -> Image.Image:
    """若目标格式为 JPEG 且图像含 alpha 通道，转换为 RGB。

    Args:
        img: 原始 Pillow Image。

    Returns:
        转换后的 Image（可能是同一个对象）。
    """
    if img.mode in ("RGBA", "P", "PA", "LA"):
        logger.debug("将模式 %s 转换为 RGB 以兼容 JPEG", img.mode)
        # 对于 P 模式需先转 RGBA 再转 RGB，以正确处理透明色
        if img.mode == "P":
            img = img.convert("RGBA")
        return img.convert("RGB")
    return img


# ---------------------------------------------------------------------------
# 公开转换函数
# ---------------------------------------------------------------------------


def download_bytes_from_url(
    url: str,
    *,
    timeout: int = _DEFAULT_DOWNLOAD_TIMEOUT,
    max_size: int = _MAX_DOWNLOAD_SIZE,
) -> bytes:
    """从给定 URL 下载图片数据，返回原始二进制 bytes。

    Args:
        url: 图片的 HTTP/HTTPS 地址。
        timeout: 请求超时时间（秒），默认 30s。
        max_size: 最大允许下载大小（字节），默认 100 MB。

    Returns:
        下载得到的原始字节数据。

    Raises:
        ImageDownloadError: 下载失败、超时或文件过大时。
        ValueError: URL 不是有效的 HTTP/HTTPS 地址时。
    """
    # URL 合法性校验
    if not url or not url.strip().startswith(("http://", "https://")):
        raise ValueError(f"URL 必须以 http:// 或 https:// 开头，收到: {url!r}")

    logger.debug("开始从 URL 下载图片: %s", url)

    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        # 检查 Content-Length（如果服务端提供）
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_size:
            raise ImageDownloadError(
                f"文件大小 ({int(content_length)} bytes) 超过限制 ({max_size} bytes)"
            )

        # 流式读取，防止大文件撑爆内存
        chunks: list[bytes] = []
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            downloaded += len(chunk)
            if downloaded > max_size:
                raise ImageDownloadError(
                    f"下载数据量 ({downloaded} bytes) 超过限制 ({max_size} bytes)"
                )
            chunks.append(chunk)

        data = b"".join(chunks)
        logger.debug("下载完成，数据大小: %d bytes", len(data))
        return data

    except requests.Timeout as exc:
        raise ImageDownloadError(f"下载超时 (timeout={timeout}s): {url}") from exc
    except requests.HTTPError as exc:
        raise ImageDownloadError(
            f"HTTP 错误 {exc.response.status_code}: {url}"
        ) from exc
    except requests.RequestException as exc:
        raise ImageDownloadError(f"下载失败: {url} - {exc}") from exc


def bytes_to_img(data: bytes) -> Image.Image:
    """将二进制 bytes 转换为 Pillow Image。

    Args:
        data: 图像的原始字节数据。

    Returns:
        Pillow Image 对象（数据已完全加载至内存）。

    Raises:
        ImageFormatError: 无法解析的图像数据。
    """
    if not data:
        raise ImageFormatError("图像数据为空")

    logger.debug("bytes_to_img: 输入数据大小 %d bytes", len(data))
    try:
        img = Image.open(io.BytesIO(data))
        # img.load()  # 确保数据完全读入内存
        return img
    except Exception as exc:
        raise ImageFormatError(f"无法解析图像数据: {exc}") from exc


def img_to_bytes(img: Image.Image, fmt: Optional[str] = None) -> bytes:
    """将 Pillow Image 转换为 bytes。

    Args:
        img: Pillow Image 对象。
        fmt: 目标格式（小写），默认为 None 时使用 img.format 或 'png'。

    Returns:
        编码后的图像字节数据。
    """
    if fmt is None:
        fmt = _normalize_format(img.format) or _DEFAULT_FORMAT
    else:
        fmt = _normalize_format(fmt) or _DEFAULT_FORMAT

    save_fmt = _pillow_save_format(fmt)
    buf = io.BytesIO()

    # 处理 RGBA -> JPEG 不支持 alpha 通道的场景
    save_img = _ensure_rgb_for_jpeg(img) if fmt == "jpeg" else img

    save_img.save(buf, format=save_fmt)
    data = buf.getvalue()
    logger.debug("img_to_bytes: 编码为 %s, 大小 %d bytes", fmt, len(data))
    return data


def base64_to_bytes(data: str) -> bytes:
    """将 base64 字符串转换为 bytes。

    支持纯 base64 内容和带 data URL 前缀两种形式。

    Args:
        data: base64 编码的字符串（可带 data:image/...;base64, 前缀）。

    Returns:
        解码后的原始字节数据。

    Raises:
        ValueError: base64 解码失败。
    """
    if not data or not data.strip():
        raise ValueError("base64 字符串不能为空")

    data = data.strip()
    match = _DATA_URL_RE.match(data)
    if match:
        raw_b64 = data[match.end() :]
        logger.debug(
            "base64_to_bytes: 检测到 data URL 前缀, MIME 格式=%s", match.group("fmt")
        )
    else:
        raw_b64 = data

    raw_b64 = raw_b64.strip()

    try:
        decoded = base64.b64decode(raw_b64, validate=True)
    except Exception as exc:
        raise ValueError(f"base64 解码失败: {exc}") from exc

    logger.debug("base64_to_bytes: 解码后大小 %d bytes", len(decoded))
    return decoded


def bytes_to_base64(data: bytes, *, with_data_prefix: bool = False) -> str:
    """将 bytes 转换为 base64 字符串。

    Args:
        data: 原始字节数据。
        with_data_prefix: 为 True 时添加 data:image/<fmt>;base64, 前缀。

    Returns:
        base64 编码的字符串。
    """
    encoded = base64.b64encode(data).decode("ascii")

    if with_data_prefix:
        fmt = _guess_format_from_bytes(data) or _DEFAULT_FORMAT
        prefix = f"data:image/{fmt};base64,"
        logger.debug("bytes_to_base64: 添加前缀, 格式=%s", fmt)
        return prefix + encoded

    logger.debug("bytes_to_base64: 编码完成 (无前缀), 长度=%d", len(encoded))
    return encoded


def base64_to_img(data: str) -> Image.Image:
    """将 base64 字符串转换为 Pillow Image。

    Args:
        data: base64 编码的图像字符串（支持 data URL 前缀）。

    Returns:
        Pillow Image 对象。
    """
    logger.debug("base64_to_img: 开始转换")
    raw_bytes = base64_to_bytes(data)
    return bytes_to_img(raw_bytes)


def img_to_base64(
    img: Image.Image, *, with_data_prefix: bool = False, fmt: Optional[str] = None
) -> str:
    """将 Pillow Image 转换为 base64 字符串。

    Args:
        img: Pillow Image 对象。
        with_data_prefix: 为 True 时添加 data URL 前缀。
        fmt: 目标编码格式，默认为 None（使用 img.format）。

    Returns:
        base64 编码的字符串。
    """
    logger.debug("img_to_base64: 开始转换, with_data_prefix=%s", with_data_prefix)
    raw_bytes = img_to_bytes(img, fmt=fmt)
    return bytes_to_base64(raw_bytes, with_data_prefix=with_data_prefix)


# ---------------------------------------------------------------------------
# MyImage 类
# ---------------------------------------------------------------------------


class MyImage:
    """通用图像包装类，支持多种输入来源并统一为 Pillow Image。

    支持的输入来源（互斥，仅允许传入其中一种）：
        - path:  本地文件路径（str 或 Path）。
        - url:   HTTP/HTTPS 图片地址。
        - data:  原始字节 bytes。
        - b64:   base64 编码字符串（支持 data URL 前缀）。
        - img:   已有的 Pillow Image.Image 对象。

    Attributes:
        format (str): 图像格式，小写（如 'png', 'jpeg', 'webp'）。

    Examples:
        >>> img = MyImage(path="photo.jpg")
        >>> img.format
        'jpeg'
        >>> img.img.size
        (1920, 1080)

        >>> web_img = MyImage(url="https://example.com/image.png")
        >>> web_img.save("local_copy.png")

        >>> converted = web_img.convert("webp")
        >>> converted.format
        'webp'
    """

    __slots__ = ("_img", "_format", "_bytes", "_base64")

    def __init__(
        self,
        *,
        path: Optional[Union[str, Path]] = None,
        url: Optional[str] = None,
        bytes: Optional[bytes] = None,
        base64: Optional[str] = None,
        img: Optional[Image.Image] = None,
    ) -> None:
        # ------ 互斥检查 ------
        sources = {"path": path, "url": url, "bytes": bytes, "base64": base64, "img": img}
        provided = {k: v for k, v in sources.items() if v is not None}

        if len(provided) == 0:
            raise ValueError("必须提供至少一个图像来源 (path/url/bytes/base64/img)")
        if len(provided) > 1:
            raise ValueError(
                f"仅允许传入一种图像来源，但同时传入了: {list(provided.keys())}"
            )

        self._img: Image.Image = None
        self._bytes: bytes = None
        self._base64: str = None
        self._format: str = None

        # ------ 根据来源进行转换 ------
        if path is not None:
            path = Path(path)
            if not path.exists():
                raise FileNotFoundError(f"文件不存在: {path}")
            fmt = _guess_format_from_suffix(str(path))
            self._img = Image.open(path)
            # self._img.load()
            if fmt is None:
                fmt = _normalize_format(self._img.format)

        elif url is not None:
            fmt = _guess_format_from_suffix(url)
            raw_bytes = download_bytes_from_url(url)
            self._bytes = raw_bytes
            if fmt is None:
                fmt = _guess_format_from_bytes(raw_bytes)
            self._img = bytes_to_img(raw_bytes)

        elif bytes is not None:
            self._bytes = bytes
            fmt = _guess_format_from_bytes(bytes)
            self._img = bytes_to_img(bytes)

        elif base64 is not None:
            self._base64 = base64
            # 优先从 data URL 前缀解析格式
            match = _DATA_URL_RE.match(base64.strip())
            if match:
                fmt = _normalize_format(match.group("fmt"))
            raw_bytes = base64_to_bytes(base64)
            self._bytes = raw_bytes
            if fmt is None:
                fmt = _guess_format_from_bytes(raw_bytes)
            self._img = bytes_to_img(raw_bytes)

        elif img is not None:
            self._img = img
            fmt = _normalize_format(img.format)

        # ------ 格式兜底 ------
        self._format = fmt or _normalize_format(self._img.format) or _DEFAULT_FORMAT

    # ---- 属性 ----

    @property
    def img(self) -> Image.Image:
        """返回内部持有的 Pillow Image 对象。"""
        return self._img
    
    @property
    def bytes(self) -> bytes:
        """返回当前图像按 self._format 编码后的 bytes。"""
        if self._bytes is None:
            self._bytes = img_to_bytes(self._img, fmt=self._format)
        return self._bytes

    @property
    def base64(self) -> str:
        """返回当前图像按 self._format 编码后的纯 base64 字符串（不带前缀）。"""
        if self._base64 is None:
            self._base64 = img_to_base64(self._img, fmt=self._format)
        return self._base64

    # ---- 方法 ----

    def get_info(self) -> dict:
        """获取当前图像的基本信息。

        Returns:
            包含 format, size, readable_size, mode, exif 等键的字典。
        """
        raw = self._bytes
        size_bytes = len(raw)

        # 可读大小
        if size_bytes < 1024:
            readable = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            readable = f"{size_bytes / 1024:.2f} KB"
        else:
            readable = f"{size_bytes / (1024 * 1024):.2f} MB"

        # EXIF 信息
        exif_data: dict = {}
        try:
            raw_exif = self._img.getexif()
            if raw_exif:
                for tag_id, value in raw_exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    if isinstance(value, bytes):
                        value = value.hex()
                    elif isinstance(value, (list, tuple)):
                        value = str(value)
                    exif_data[tag_name] = value
        except Exception as exc:
            logger.error("读取 EXIF 信息时出错: %s", exc)

        info = {
            "format": self._format,
            "size": self._img.size,
            "readable_size": readable,
            "mode": self._img.mode,
            "exif": exif_data,
        }

        logger.info("MyImage info: %s", info)
        return info

    def save(self, path: Union[str, Path], fmt: Optional[str] = None) -> Path:
        """将图像保存到本地文件。

        Args:
            path: 目标文件路径。
            fmt: 目标格式（小写），为 None 时优先从路径后缀推断，
                 否则使用 self._format。

        Returns:
            保存后的文件路径（Path 对象）。
        """
        path = Path(path)

        # 优先从路径后缀推断格式
        if fmt is None:
            fmt = _guess_format_from_suffix(str(path)) or self._format
        else:
            fmt = _normalize_format(fmt) or self._format

        # 自动创建父目录
        path.parent.mkdir(parents=True, exist_ok=True)

        pil_fmt = _pillow_save_format(fmt)
        save_img = _ensure_rgb_for_jpeg(self._img) if fmt == "jpeg" else self._img

        save_img.save(str(path), format=pil_fmt)
        logger.debug("图像已保存至: %s (格式=%s)", path, fmt)
        return path

    def __repr__(self) -> str:
        return (
            f"<MyImage format={self._format!r} size={self._img.size} "
            f"mode={self._img.mode!r}>"
        )