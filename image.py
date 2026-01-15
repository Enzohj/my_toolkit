from PIL import Image
import requests
import base64
import io
import os
from pathlib import Path
from typing import Optional, Union, Tuple, Any
from .logger import logger

IMG_FORMAT_MAP = {
    'jpg': 'JPEG',
    'jpeg': 'JPEG',
    'png': 'PNG',
    'gif': 'GIF',
    'bmp': 'BMP',
    'tif': 'TIFF',
    'tiff': 'TIFF',
    'webp': 'WEBP',
}

def bytes_to_img(img_bytes: bytes, force_rgb: bool = True) -> Image.Image:
    """字节流 -> PIL 图像"""
    try:
        img = Image.open(io.BytesIO(img_bytes))
        if force_rgb:
            img = img.convert('RGB')
        return img
    except Exception as e:
        logger.error(f"Error converting bytes to image: {e}")
        raise e

def img_to_bytes(img_pil: Image.Image, img_format: str = 'JPEG', force_rgb: bool = True) -> bytes:
    """PIL 图像 -> 字节流"""
    try:
        img_byte_arr = io.BytesIO()
        if force_rgb:
            img_pil = img_pil.convert('RGB')
        
        img_pil.save(img_byte_arr, format=img_format)
        result = img_byte_arr.getvalue()
        return result
    except Exception as e:
        logger.error(f"Error converting image to bytes: {e}")
        raise e

def bytes_to_base64(img_bytes: bytes) -> str:
    """字节流 -> Base64 字符串"""
    try:
        return base64.b64encode(img_bytes).decode('utf-8')
    except Exception as e:
        logger.error(f"Error converting bytes to base64:: {e}")
        raise e

def base64_to_bytes(img_base64: str) -> bytes:
    """Base64 字符串 -> 字节流"""
    try:
        # 处理可能包含的 header (如 data:image/png;base64,...)
        if ',' in img_base64:
            img_base64 = img_base64.split(',')[1]
        return base64.b64decode(img_base64)
    except Exception as e:
        logger.error(f"Error converting base64 to bytes:: {e}")
        raise e


def base64_to_img(img_base64: str, return_bytes: bool = False, force_rgb: bool = True) -> Image.Image:
    """Base64 字符串 -> PIL 图像"""
    try:
        img_bytes = base64_to_bytes(img_base64)
        if return_bytes:
            return bytes_to_img(img_bytes, force_rgb),img_bytes
        return bytes_to_img(img_bytes, force_rgb)
    except Exception as e:
        logger.error(f"Error converting base64 to image: {e}")
        raise e


def img_to_base64(img_pil: Image.Image, img_format: str = 'JPEG', return_bytes: bool = False, force_rgb: bool = True) -> str:
    """PIL 图像 -> Base64 字符串"""
    try:
        img_bytes = img_to_bytes(img_pil, img_format, force_rgb)
        if return_bytes:
            return bytes_to_base64(img_bytes), img_bytes
        return bytes_to_base64(img_bytes)
    except Exception as e:
        logger.error(f"Error converting image to base64: {e}")
        raise e

def load_img(img_path: str, return_bytes: bool = False, timeout: int = 30, force_rgb: bool = True):
    """
    从路径或 URL 加载图像。
    
    :param img_path: 本地路径或 URL
    :param return_bytes: 是否返回字节流
    :param timeout: 请求超时时间
    """
    try:
        if img_path.startswith(('http://', 'https://')):
            resp = requests.get(img_path, timeout=timeout)
            resp.raise_for_status()
            img_bytes = resp.content
        elif os.path.isfile(img_path):
            with open(img_path, 'rb') as f:
                img_bytes = f.read()
        else:
            raise ValueError(f"Image path not valid: {img_path}")
        img_pil = bytes_to_img(img_bytes, force_rgb)
        logger.debug(f"Image size: {img_pil.size}")
        logger.debug(f"Image format: {img_pil.format if img_pil.format else IMG_FORMAT_MAP.get(img_path.split('.')[-1].lower(), 'JPEG')}")
        logger.debug(f"Image mode: {img_pil.mode}")
        if return_bytes:
            return img_pil, img_bytes
        return img_pil
        
    except Exception as e:
        logger.error(f"Error loading image from {img_path}: {e}")
        raise e
    
class MyImage:
    """
    图像处理工具类：提供图像、字节流、Base64 字符串之间的转换，以及图像加载、调整大小与保存功能。
    """
    ImageSource = Union[str, bytes, Image.Image]

    def __init__(self, 
                 img_input: Optional[ImageSource] = None, force_rgb: bool = True):
        
        if img_input:
            try:
                if isinstance(img_input, Image.Image): 
                    img_pil = img_input
                    if force_rgb:
                        img_pil = img_pil.convert('RGB')
                    self.img_pil = img_pil
                elif isinstance(img_input, bytes): 
                    img_bytes = img_input
                    self.img_pil = bytes_to_img(img_bytes, force_rgb=force_rgb)
                    self.img_bytes = img_bytes
                elif isinstance(img_input, str):
                    if os.path.exists(img_input) or img_input.startswith(('http', 'https')):
                        img_path = img_input
                        self.img_pil, self.img_bytes = load_img(img_path, return_bytes=True, force_rgb=force_rgb)
                    else:
                        img_base64 = img_input
                        self.img_pil, self.img_bytes = base64_to_img(img_base64, return_bytes=True, force_rgb=force_rgb)
                else:
                    raise ValueError(f"Unsupported image source type: {type(img_input)}")
                self.img_size = self.img_pil.size
                self.img_format = self.img_pil.format if self.img_pil.format else IMG_FORMAT_MAP.get(img_path.split('.')[-1].lower(), 'JPEG')
            except Exception as e:
                logger.error(f"Failed to initialize Image: {e}")
                raise e
        else:
            raise ValueError("No valid image source provided.")
        
    def save_img(self, save_path: str, img_format: Optional[str] = None):
        """保存当前图像"""
        try:
            save_format = img_format or self.img_format or 'JPEG'
            
            # 自动纠正文件扩展名对应的格式
            if img_format is None and save_path:
                ext = Path(save_path).suffix.lower().replace('.', '')
                if ext in ['jpg', 'jpeg']: save_format = 'JPEG'
                elif ext == 'png': save_format = 'PNG'
                elif ext == 'webp': save_format = 'WEBP'

            logger.debug(f"Saving image to {save_path}, format: {save_format}")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            
            self.img_pil.save(save_path, format=save_format)
        except Exception as e:
            logger.error(f"Error saving image to {save_path}: {e}")
            raise e

