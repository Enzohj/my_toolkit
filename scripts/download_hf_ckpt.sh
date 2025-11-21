export HF_ENDPOINT=https://hf-mirror.com

if [ $# -lt 1 ]; then
    echo "用法: $0 model_name [save_dir]"
    echo "示例1: $0 model_name save_dir  # 下载模型到指定目录"
    echo "示例2: $0 model_name           # 下载模型到默认目录"
    exit 1
fi

model_name=$1
if [ $# -eq 2 ]; then
    save_dir="$2"
    mkdir -p "$save_dir"
    hf download "$model_name" --local-dir "$save_dir"
else
    hf download "$model_name"
fi
