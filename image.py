from PIL import Image
import requests
import base64
import io
import os
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

class ImageTool:
    """
    提供图像、字节流、Base64 字符串之间的相互转换，图像处理，以及图像的下载与保存功能。
    """
    def __init__(self, img_path=None, img_bytes=None, img_base64=None, img_pil=None):
        """
        初始化 ImageTool 类，提供图像路径、字节流、Base64 字符串或 PIL 图像对象。

        :param img_path: 图像文件路径
        :param img_bytes: 图像的字节流
        :param img_base64: 图像的 Base64 字符串
        :param img_pil: PIL 图像对象
        """
        self.img_path = img_path
        self.img_bytes = img_bytes
        self.img_base64 = img_base64
        self.img_pil = img_pil
        if self.img_path is not None:
            self.img_pil, self.img_bytes, self.img_format = self.load_img(self.img_path, only_img=False)
        elif self.img_bytes is not None:
            self.img_pil = self.bytes_to_img(self.img_bytes)
        elif self.img_base64 is not None:
            self.img_pil, self.img_bytes = self.base64_to_img(self.img_base64, need_bytes=True)
        elif self.img_pil is not None:
            pass
        else:
            raise ValueError("No image provided")
        self.img_size = self.img_pil.size

    @staticmethod
    def img_to_bytes(img_pil, img_format='JPEG'):
        """
        将 PIL 图像对象转换为字节流。

        :param img_pil: PIL 图像对象
        :param img_format: 图像格式，默认 JPEG
        :return: 转换后的字节流
        """
        try:
            logger.debug(f"Converting image to bytes, format: {img_format}")
            img_bytes = io.BytesIO()
            img_pil.save(img_bytes, format=img_format)
            return img_bytes.getvalue()
        except Exception as e:
            logger.error(f"Error converting image to bytes: {e}")
            raise e
        
    @staticmethod
    def bytes_to_img(img_bytes):
        """
        将字节流转换为 PIL 图像对象。

        :param img_bytes: 图像的字节流
        :return: 转换后的 PIL 图像对象
        """
        try:
            logger.debug("Converting bytes to image, length: {}".format(len(img_bytes)))
            return Image.open(io.BytesIO(img_bytes)).convert('RGB')
        except Exception as e:
            logger.error(f"Error converting bytes to image: {e}")
            raise e
        
    @staticmethod
    def bytes_to_base64(img_bytes):
        """
        将字节流转换为 Base64 字符串。

        :param img_bytes: 图像的字节流
        :return: 转换后的 Base64 字符串
        """
        try:
            logger.debug("Converting bytes to base64, length: {}".format(len(img_bytes)))
            return base64.b64encode(img_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Error converting bytes to base64: {e}")
            raise e

    @staticmethod
    def base64_to_bytes(img_base64):
        """
        将 Base64 字符串转换为字节流。
        
        :param img_base64: 图像的 Base64 字符串
        :return: 转换后的字节流
        """
        try:
            logger.debug("Converting base64 to bytes, length: {}".format(len(img_base64)))
            return base64.b64decode(img_base64)
        except Exception as e:
            logger.error(f"Error converting base64 to bytes: {e}")
            raise e

    @staticmethod
    def base64_to_img(img_base64, need_bytes=False):
        """
        将 Base64 字符串转换为 PIL 图像对象。

        :param img_base64: 图像的 Base64 字符串
        :param need_bytes: 是否需要返回字节流，默认 False
        :return: 转换后的 PIL 图像对象或 (PIL 图像对象, 字节流) 元组
        """
        try:
            logger.debug("Converting base64 to image, length: {}".format(len(img_base64)))
            img_bytes = base64.b64decode(img_base64)
            img_pil = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            if need_bytes:
                return img_pil, img_bytes
            else:
                return img_pil
        except Exception as e:
            logger.error(f"Error converting base64 to image: {e}")
            raise e
        
    @staticmethod
    def img_to_base64(img_pil, img_format='JPEG'):
        """
        将 PIL 图像对象转换为 Base64 字符串。
        
        :param img_pil: PIL 图像对象
        :param img_format: 图像格式，默认 JPEG
        :return: 转换后的 Base64 字符串
        """
        try:
            logger.debug(f"Converting image to base64, format: {img_format}")
            img_bytes = io.BytesIO()
            img_pil.save(img_bytes, format=img_format)
            return base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error converting image to base64: {e}")
            raise e


    @staticmethod
    def load_img(img_path, only_img=True):
        """
        从本地路径或 URL 加载图像，支持 JPEG、PNG、GIF、BMP 等格式。

        :param img_path: 图像文件路径或 URL
        :param only_img: 是否只返回 PIL 图像对象，默认 True
        :return: 加载后的 PIL 图像对象或 (PIL 图像对象, 字节流, 图像格式, 图像大小) 元组
        """
        img_pil, img_bytes, img_format = None, None, None
        try:
            if os.path.exists(img_path):
                logger.debug(f"Loading image from local: {img_path}")
                img_pil = Image.open(img_path).convert('RGB')
            elif img_path.startswith('http') or img_path.startswith('https'):
                logger.debug(f"Loading image from remote: {img_path}")
                response = requests.get(img_path)
                img_bytes = response.content
                img_pil = ImageTool.bytes_to_img(img_bytes)
            else:
                raise ValueError(f"Image path not valid: {img_path}")
            img_format = IMG_FORMAT_MAP.get(img_path.split('.')[-1].lower(), img_pil.format)
            logger.debug(f"Image size: {img_pil.size}")
            logger.debug(f"Image format: {img_format}")
            logger.debug(f"Image mode: {img_pil.mode}")
            if only_img:
                return img_pil
            else:
                return img_pil, img_bytes, img_format
        except Exception as e:
            logger.error(f"Error loading image from {img_path}: {e}")
            raise e



    def save_img(self, save_path, img_format=None):
        """
        将 PIL 图像对象保存为文件。

        :param save_path: 保存路径
        :param img_format: 图像格式，默认 JPEG
        """
        try:
            if img_format is not None:
                save_format = img_format
            else:
                save_format = self.img_format if self.img_format is not None else 'JPEG'
            logger.debug(f"Saving image to {save_path}, format: {save_format}")
            self.img_pil.save(save_path, format=save_format)
        except Exception as e:
            logger.error(f"Error saving image to {save_path}: {e}")
            raise e


    def visualize_img(self):
        """
        可视化 PIL 图像对象。
        """
        try:
            logger.debug(f"Visualizing image...")
            self.img_pil.show()
        except Exception as e:
            logger.error(f"Error visualizing image: {e}")
            raise e
        
    def resize_img(self, size=None, scale=None):
        """
        调整 PIL 图像对象的大小。
        
        :param size: 目标大小，元组 (宽度, 高度)
        :param scale: 缩放比例，浮点数
        :return: 调整后的 PIL 图像对象
        """
        try:
            logger.debug(f"Resizing params, size: {size}, scale: {scale}")
            if size is not None:
                img_pil = self.img_pil.resize(size)
            elif scale is not None:
                img_pil = self.img_pil.resize((int(self.img_size[0] * scale), int(self.img_size[1] * scale)))
            else:
                raise ValueError("Either size or scale must be provided.")
            new_img_size = img_pil.size
            logger.debug(f"Image size after resizing: {self.img_size} -> {new_img_size}")
            return img_pil
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            raise e


