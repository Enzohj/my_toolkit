import sys
import os
sys.path.insert(0, '../')
from my_toolkit.logger import init_logger
logger = init_logger(name="test")


def test_image():
    from my_toolkit.image import MyImage, img_to_bytes, img_to_base64, bytes_to_img, bytes_to_base64, base64_to_bytes, base64_to_img
    img_path = 'test/cartoon_brave_person.jpeg'
    logger.info("start test_image")
    img = MyImage(img_path)
    img_to_bytes(img.img)
    img_to_base64(img.img)
    bytes_to_img(img.byte)
    bytes_to_base64(img.byte)
    base64_to_bytes(img.base64)
    base64_to_img(img.base64)
    logger.info(img)
    logger.info(img.get_info())
    
def test_file():
    from my_toolkit.file import read_file, write_file, read_parquet
    for fpath in [
        '/mnt/bn/hjx-nas-arnold/code/work/kp/main_kp/0106_enable.txt',
        '/mnt/bn/hjx-nas-arnold/code/work/kp/main_kp/0113_v2_gsb_31main.csv',
        '/mnt/bn/hjx-nas-arnold/code/work/kp/main_kp/debug.json',
    ]:
        read_file(fpath)
    


def test_benchmark():
    from my_toolkit.benchmark import benchmark
    import random
    import time

    test_data = [random.randint(1, 100) for _ in range(100)]
    def test_func(x):
        time.sleep(0.1)
        return x * 2
    benchmark(test_func, test_data, concurrency=4)


if __name__ == "__main__":
    # test_image()
    test_file()