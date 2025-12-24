# my_toolkit
[![GitHub Repo stars](https://img.shields.io/github/stars/Enzohj/my_toolkit?style=social)](https://github.com/Enzohj/my_toolkit/stargazers)
[![GitHub last commit](https://img.shields.io/github/last-commit/Enzohj/my_toolkit)](https://github.com/Enzohj/my_toolkit/commits/main)
[![GitHub license](https://img.shields.io/github/license/Enzohj/my_toolkit)](https://github.com/Enzohj/my_toolkit/blob/main/LICENSE)

A simple and easy-to-use Python toolkit designed to streamline common operations in daily development.

[ English | [中文](README_zh.md) ]

---

## Table of Contents

- [✨ Features](#-features)
- [💾 Installation](#-installation)
- [🚀 Quickstart](#-quickstart)
  - [File Operations](#file-operations)
  - [Image Processing](#image-processing)
  - [Logging](#logging)
  - [Parallel Processing](#parallel-processing)
  - [Useful Decorators](#useful-decorators)
  - [Text Processing](#text-processing)
- [📜 Scripts Usage](#-scripts-usage)
- [🤔 FAQ](#-faq)
- [📄 License](#-license)

## ✨ Features

- **Unified File Interface**: Standardized read/write support for multiple formats, including `TXT`, `JSON`, `JSONL`, `CSV`, and `Parquet`, without worrying about the underlying details.
- **Convenient Image Processing**: Effortlessly convert between `PIL.Image`, `Bytes`, and `Base64`, with support for loading images from local paths or URLs.
- **Seamless Logging System**: Automatically compatible with both `loguru` and the standard `logging` library, providing a unified and concise logging interface.
- **Efficient Parallel Processing**: Simplifies multi-threading and multi-processing tasks, with a built-in `tqdm` progress bar to make parallelization more intuitive.
- **Practical Decorators**: Offers common decorators like `@timer`, `@timeout`, and `@retry` to enhance code robustness.
- **Lightweight Text Utilities**: Includes common text processing functions for cleaning text, extracting `#hashtags#`, and more.

## 💾 Installation

1.  **Clone the Repository**

    ```bash
    git clone https://github.com/Enzohj/my_toolkit.git
    cd my_toolkit
    ```

2.  **Install Dependencies**

    The basic dependencies are listed in `setup_env/requirements.txt`.

    ```bash
    pip install -r setup_env/requirements.txt
    ```

    Additionally, some features depend on the following third-party libraries. It is recommended to install them for the full experience:

    - `Pillow`: For image processing.
    - `requests`: For downloading images from URLs.
    - `tqdm`: For displaying progress bars in parallel computations.

    You can install all recommended dependencies with the following command:

    ```bash
    pip install loguru pandas huggingface_hub pyarrow Pillow requests tqdm
    ```

## 🚀 Quickstart

### File Operations

`my_toolkit` provides two high-level functions, `read_file` and `write_file`, which automatically select the appropriate reader/writer based on the file extension.

```python
from my_toolkit.file import read_file, write_file

# Read a JSONL file
data_list = read_file('data.jsonl')

# Read a CSV file as a DataFrame
df = read_file('data.csv', format='dataframe')

# Write a dictionary to a JSON file
my_dict = {"name": "my_toolkit", "version": "1.0"}
write_file(my_dict, 'config.json', indent=4)

# Append lines to a TXT file
lines_to_append = ["hello", "world"]
write_file(lines_to_append, 'log.txt', append=True)
```

### Image Processing

The `ImageTool` class encapsulates all image-related operations, making it easy to convert between different formats.

```python
from my_toolkit.image import ImageTool

# Load an image from a local path or URL
img_tool = ImageTool(img_path='path/to/your/image.jpg')
# img_tool = ImageTool(img_path='https://example.com/image.png')

# Get the PIL.Image object
pil_image = img_tool.img_pil

# Convert between image formats
img_bytes = ImageTool.img_to_bytes(pil_image)
img_base64 = ImageTool.bytes_to_base64(img_bytes)

# Restore an image from a Base64 string
restored_pil_image = ImageTool.base64_to_img(img_base64)

# Resize and save an image
resized_img = img_tool.resize_img(scale=0.5)
ImageTool(img_pil=resized_img).save_img('resized_image.png')
```

### Logging

A unified `logger` instance that works correctly whether `loguru` is installed or not.

```python
from my_toolkit.logger import logger, setup_logger

# Configure the log level and output file (optional)
setup_logger(level="INFO", output_file="app.log")

# Use the logger
logger.debug("This is a debug message.")
logger.info("Welcome to my_toolkit!")
logger.warning("Please note, this operation may take a long time.")
logger.error("File not found!")
```

### Parallel Processing

Easily execute parallel tasks with `apply_multi_thread` and `apply_multi_process`.

```python
from my_toolkit.mp import apply_multi_thread, apply_multi_process
import time

def task(item):
    time.sleep(0.1)
    return item * 2

data = range(20)

# Use multi-threading for I/O-bound tasks
print("Starting multi-threading...")
results_thread = apply_multi_thread(data, task, num_workers=4)
print(f"Multi-threading results: {results_thread}")

# Use multi-processing for CPU-bound tasks
print("\nStarting multi-processing...")
results_process = apply_multi_process(data, task, num_workers=4)
print(f"Multi-processing results: {results_process}")
```

### Useful Decorators

Simplify common functionalities with decorators.

```python
from my_toolkit.decorator import timer, retry, timeout

@retry(max_attempts=3, delay=1)
@timeout(seconds=5)
@timer
def risky_operation(should_fail):
    if should_fail:
        raise ValueError("Operation failed!")
    print("Operation successful!")
    return "OK"

# Example: The function will automatically retry and print the execution time
print("--- First call (will fail and retry) ---")
risky_operation(should_fail=True)

print("\n--- Second call (will succeed directly) ---")
risky_operation(should_fail=False)
```

### Text Processing

Provides simple and fast text utility functions.

```python
from my_toolkit.text import normalize_text, extract_hashtag, remove_emoji_and_hashtag

text = "   Welcome to #my_toolkit  , this is a #Python library!   😊 "

# Normalize text (remove extra spaces)
normalized = normalize_text(text)
print(f"Normalized text: {normalized}")

# Extract hashtags
tags = extract_hashtag(text)
print(f"Extracted tags: {tags}")

# Remove emojis and hashtags
cleaned_text = remove_emoji_and_hashtag(text)
print(f"Cleaned text: {cleaned_text}")
```

## 📜 Scripts Usage

The `scripts` directory contains some useful scripts for daily development and management.

-   **`hang.sh`**: Runs a long-running command in the background and redirects its standard output and error to a log file.

    ```bash
    # Usage: ./scripts/hang.sh <your_command> [your_args...]
    # Example: Run a Python script in the background
    ./scripts/hang.sh python my_train_script.py --epochs 100
    ```
    Logs are saved by default to `./logs/hang_YYYYMMDD_HHMMSS.log`.

-   **`download_hf_ckpt.sh`**: Downloads a model or dataset from a Hugging Face mirror (`hf-mirror.com`).

    ```bash
    # Usage: ./scripts/download_hf_ckpt.sh <model_name> [save_directory]
    # Example: Download Llama-3-8B-Instruct to a specific directory
    ./scripts/download_hf_ckpt.sh meta-llama/Meta-Llama-3-8B-Instruct /path/to/models
    ```

-   **`kill.sh` & `cmd.sh`**: Used for process management.
    - `kill.sh`: Finds and kills processes based on a keyword, with an interactive confirmation prompt.
      ```bash
      # Usage: ./scripts/kill.sh <keyword>
      # Example: Find and kill all processes containing "python"
      ./scripts/kill.sh python
      ```
    - `cmd.sh`: Forcibly kills all processes using NVIDIA GPUs. Use with caution.
      ```bash
      # Usage: ./scripts/cmd.sh
      ```

## 🤔 FAQ

**Q: Why do I get a `ModuleNotFoundError` when importing `my_toolkit` from another directory?**

A: This is because the root directory of `my_toolkit` has not been added to Python's search path. You can solve this by adding the project's root directory to the `PYTHONPATH` environment variable.

Add the following command to your `~/.bashrc` or `~/.zshrc` file:

```bash
# Replace /path/to/your/my_toolkit with the actual path to your project
export PYTHONPATH=$PYTHONPATH:/path/to/your/my_toolkit
```

Then, run `source ~/.bashrc` or `source ~/.zshrc` to apply the changes.

## 📄 License

This repository is licensed under the [MIT License](LICENSE).
