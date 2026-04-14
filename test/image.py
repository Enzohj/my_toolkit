"""test/image.py

对 `my_toolkit.image` 的最小可运行测试脚本。

说明：`my_toolkit.image` 依赖 Pillow / pillow_heif / requests。
若依赖缺失导致模块无法导入，则本测试会自动跳过。
"""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
import sys


def _import_image_module():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root.parent))
    try:
        return importlib.import_module("my_toolkit.image"), None
    except Exception as exc:
        return None, exc


image_mod, _IMPORT_ERR = _import_image_module()


def _import_pil():
    try:
        from PIL import Image
        return Image, None
    except Exception as exc:
        return None, exc


PIL_Image, _PIL_ERR = _import_pil()


@unittest.skipIf(image_mod is None, f"my_toolkit.image 导入失败: {_IMPORT_ERR}")
@unittest.skipIf(PIL_Image is None, f"Pillow 导入失败: {_PIL_ERR}")
class TestImageConversions(unittest.TestCase):
    def _make_img(self):
        # 生成一个小的 RGBA 图像，覆盖 JPEG 兼容转换路径
        return PIL_Image.new("RGBA", (16, 8), color=(10, 20, 30, 40))

    def test_img_bytes_roundtrip(self):
        img = self._make_img()
        b = image_mod.img_to_bytes(img, fmt="png")
        self.assertIsInstance(b, (bytes, bytearray))
        img2 = image_mod.bytes_to_img(b)
        self.assertEqual(img2.size, img.size)

    def test_base64_roundtrip_with_prefix(self):
        img = self._make_img()
        b64 = image_mod.img_to_base64(img, with_data_prefix=True, fmt="png")
        self.assertTrue(b64.startswith("data:image/"))
        raw = image_mod.base64_to_bytes(b64)
        self.assertGreater(len(raw), 0)
        img2 = image_mod.base64_to_img(b64)
        self.assertEqual(img2.size, img.size)

    def test_download_invalid_url(self):
        with self.assertRaises(ValueError):
            image_mod.download_bytes_from_url("not-a-url")


@unittest.skipIf(image_mod is None, f"my_toolkit.image 导入失败: {_IMPORT_ERR}")
@unittest.skipIf(PIL_Image is None, f"Pillow 导入失败: {_PIL_ERR}")
class TestMyImage(unittest.TestCase):
    def _make_img(self):
        return PIL_Image.new("RGB", (10, 10), color=(255, 0, 0))

    def test_construct_from_img_and_properties(self):
        mi = image_mod.MyImage(img=self._make_img())
        self.assertEqual(mi.size, (10, 10))
        self.assertEqual(mi.mode, "RGB")
        self.assertIsInstance(mi.byte, (bytes, bytearray))
        self.assertIsInstance(mi.base64, str)
        self.assertTrue(mi.base64_with_prefix.startswith("data:image/"))

    def test_construct_from_bytes(self):
        raw = image_mod.img_to_bytes(self._make_img(), fmt="png")
        mi = image_mod.MyImage(byte=raw)
        self.assertEqual(mi.size, (10, 10))

    def test_construct_from_base64(self):
        b64 = image_mod.img_to_base64(self._make_img(), with_data_prefix=True, fmt="png")
        mi = image_mod.MyImage(base64=b64)
        self.assertEqual(mi.size, (10, 10))
        # base64 属性为纯 base64，不含前缀
        self.assertFalse(mi.base64.startswith("data:image/"))

    def test_reject_multiple_sources(self):
        with self.assertRaises(ValueError):
            image_mod.MyImage(path="x.png", url="https://example.com/x.png")

    def test_save_creates_parent_dir(self):
        mi = image_mod.MyImage(img=self._make_img())
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a" / "b.png"
            out = mi.save(p, fmt="png")
            self.assertTrue(out.exists())

    def test_context_manager_close(self):
        raw = image_mod.img_to_bytes(self._make_img(), fmt="png")
        with image_mod.MyImage(byte=raw) as mi:
            self.assertEqual(mi.size, (10, 10))


if __name__ == "__main__":
    unittest.main(verbosity=2)

