# my_toolkit

[![GitHub Repo stars](https://img.shields.io/github/stars/Enzohj/my_toolkit?style=social)](https://github.com/Enzohj/my_toolkit/stargazers)
[![GitHub last commit](https://img.shields.io/github/last-commit/Enzohj/my_toolkit)](https://github.com/Enzohj/my_toolkit/commits/main)
[![GitHub license](https://img.shields.io/github/license/Enzohj/my_toolkit)](https://github.com/Enzohj/my_toolkit/blob/main/LICENSE)

一个简单易用的 Python 工具包，旨在简化日常开发中的常用操作。

---

## 目录

- [✨ 特性亮点](#-特性亮点)
- [💾 安装指南](#-安装指南)
- [🚀 快速开始](#-快速开始)
  - [文件操作](#文件操作)
  - [图像处理](#图像处理)
  - [日志记录](#日志记录)
  - [并行计算](#并行计算)
  - [实用装饰器](#实用装饰器)
  - [文本处理](#文本处理)
- [📜 常用脚本说明](#-常用脚本说明)
- [🤔 常见问题](#-常见问题)
- [📄 许可](#-许可)

## ✨ 特性亮点

- **统一文件接口**: 支持 `TXT`, `JSON`, `JSONL`, `CSV`, `Parquet` 等多种格式的标准化读写，无需关心底层细节。
- **便捷图像处理**: 轻松实现 `PIL.Image`, `Bytes`, `Base64` 之间的相互转换，支持从本地或 URL 加载图像。
- **无缝日志系统**: 自动兼容 `loguru` 和标准 `logging`，提供统一、简洁的日志记录接口。
- **高效并行处理**: 简化多线程和多进程任务，内置 `tqdm` 进度条，让并行化更加直观。
- **实用装饰器**: 提供 `@timer` (计时), `@timeout` (超时), `@retry` (重试) 等常用装饰器，提升代码健壮性。
- **轻量文本工具**: 包含文本清洗、`#hashtags#` 提取等常用文本处理功能。

## 💾 安装指南

1.  **克隆仓库**

    ```bash
    git clone https://github.com/Enzohj/my_toolkit.git
    cd my_toolkit
    ```

2.  **安装依赖**

    基础依赖项已在 `requirements.txt` 中列出。

    ```bash
    pip install -r setup_env/requirements.txt
    ```

    此外，部分功能依赖于以下第三方库，建议一并安装以获得完整体验：

    - `Pillow`: 图像处理
    - `requests`: 从 URL 下载图像
    - `tqdm`: 在并行计算中显示进度条

    可以使用以下命令安装所有推荐依赖：

    ```bash
    pip install loguru pandas huggingface_hub pyarrow Pillow requests tqdm
    ```

## 🚀 快速开始

### 文件操作

`my_toolkit` 提供了 `read_file` 和 `write_file` 两个高级函数，能够根据文件扩展名自动选择合适的读写方式。

```python
from my_toolkit.file import read_file, write_file

# 读取 JSONL 文件
data_list = read_file('data.jsonl')

# 读取 CSV 文件为 DataFrame
df = read_file('data.csv', format='dataframe')

# 写入 JSON 文件
my_dict = {"name": "my_toolkit", "version": "1.0"}
write_file(my_dict, 'config.json', indent=4)

# 以追加模式写入 TXT 文件
lines_to_append = ["hello", "world"]
write_file(lines_to_append, 'log.txt', append=True)
```

### 图像处理

`ImageTool` 类封装了所有与图像相关的操作，可以方便地在不同格式间转换。

```python
from my_toolkit.image import ImageTool

# 从本地路径或 URL 加载图像
img_tool = ImageTool(img_path='path/to/your/image.jpg')
# img_tool = ImageTool(img_path='https://example.com/image.png')

# 获取 PIL.Image 对象
pil_image = img_tool.img_pil

# 图像格式转换
img_bytes = ImageTool.img_to_bytes(pil_image)
img_base64 = ImageTool.bytes_to_base64(img_bytes)

# 从 Base64 恢复图像
restored_pil_image = ImageTool.base64_to_img(img_base64)

# 缩放图像并保存
resized_img = img_tool.resize_img(scale=0.5)
ImageTool(img_pil=resized_img).save_img('resized_image.png')
```

### 日志记录

统一的 `logger` 实例，无论是否安装 `loguru` 都能正常工作。

```python
from my_toolkit.logger import logger, setup_logger

# 配置日志级别和输出文件（可选）
setup_logger(level="INFO", output_file="app.log")

# 使用 logger
logger.debug("这是一条调试信息。")
logger.info("欢迎使用 my_toolkit！")
logger.warning("请注意，这个操作可能耗时较长。")
logger.error("文件未找到！")
```

### 并行计算

通过 `apply_multi_thread` 和 `apply_multi_process` 轻松执行并行任务。

```python
from my_toolkit.mp import apply_multi_thread, apply_multi_process
import time

def task(item):
    time.sleep(0.1)
    return item * 2

data = range(20)

# 使用多线程处理 I/O 密集型任务
print("开始多线程处理...")
results_thread = apply_multi_thread(data, task, num_workers=4)
print(f"多线程结果: {results_thread}")

# 使用多进程处理 CPU 密集型任务
print("\n开始多进程处理...")
results_process = apply_multi_process(data, task, num_workers=4)
print(f"多进程结果: {results_process}")
```

### 实用装饰器

用装饰器简化常用功能。

```python
from my_toolkit.decorator import timer, retry, timeout

@retry(max_attempts=3, delay=1)
@timeout(seconds=5)
@timer
def risky_operation(should_fail):
    if should_fail:
        raise ValueError("操作失败！")
    print("操作成功！")
    return "OK"

# 示例：函数将自动重试，并在计时结束后打印耗时
print("--- 第一次调用 (会失败并重试) ---")
risky_operation(should_fail=True)

print("\n--- 第二次调用 (直接成功) ---")
risky_operation(should_fail=False)
```

### 文本处理

提供简单快捷的文本工具函数。

```python
from my_toolkit.text import normalize_text, extract_hashtag, remove_emoji_and_hashtag

text = "   欢迎来到 #my_toolkit  , 这是一个 #Python 库!   😊 "

# 标准化文本 (去除多余空格)
normalized = normalize_text(text)
print(f"标准化文本: {normalized}")

# 提取 hashtags
tags = extract_hashtag(text)
print(f"提取的标签: {tags}")

# 移除 emoji 和 hashtags
cleaned_text = remove_emoji_and_hashtag(text)
print(f"清洗后文本: {cleaned_text}")
```

## 📜 常用脚本说明

`scripts` 目录下提供了一些实用脚本，方便日常开发和管理。

-   **`hang.sh`**: 在后台挂起一个长时间运行的命令，并将标准输出和错误重定向到日志文件。

    ```bash
    # 用法: ./scripts/hang.sh <你的命令> [你的参数...]
    # 示例: 在后台运行 Python 脚本
    ./scripts/hang.sh python my_train_script.py --epochs 100
    ```
    日志会默认保存在 `./logs/hang_YYYYMMDD_HHMMSS.log`。

-   **`download_hf_ckpt.sh`**: 从 Hugging Face 镜像（`hf-mirror.com`）下载模型或数据集。

    ```bash
    # 用法: ./scripts/download_hf_ckpt.sh <模型名称> [保存目录]
    # 示例: 下载 Llama-3-8B-Instruct 到指定目录
    ./scripts/download_hf_ckpt.sh meta-llama/Meta-Llama-3-8B-Instruct /path/to/models
    ```

-   **`kill.sh` & `cmd.sh`**: 用于进程管理。
    - `kill.sh`: 根据关键词查找并杀死相关进程，支持交互式确认。
      ```bash
      # 用法: ./scripts/kill.sh <关键词>
      # 示例: 查找并杀死所有包含 "python" 的进程
      ./scripts/kill.sh python
      ```
    - `cmd.sh`: 强制杀死所有占用 NVIDIA GPU 的进程，请谨慎使用。
      ```bash
      # 用法: ./scripts/cmd.sh
      ```

## 🤔 常见问题

**Q: 为什么在其他目录导入 `my_toolkit` 时会提示 `ModuleNotFoundError`？**

A: 这是因为 `my_toolkit` 的根目录没有被添加到 Python 的搜索路径中。你可以通过将项目根目录添加到 `PYTHONPATH` 环境变量来解决这个问题。

将以下命令添加到你的 `~/.bashrc` 或 `~/.zshrc` 文件中：

```bash
# 将 /path/to/your/my_toolkit 替换为你的实际项目路径
export PYTHONPATH=$PYTHONPATH:/path/to/your/my_toolkit
```

然后执行 `source ~/.bashrc` 或 `source ~/.zshrc` 使其生效。

## 📄 许可

本仓库遵循 [MIT License](LICENSE) 许可。
