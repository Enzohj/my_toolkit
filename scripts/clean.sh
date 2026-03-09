#!/bin/bash

# 检查参数数量
if [ $# -ne 2 ]; then
    echo "用法: $0 <目标路径> <要删除的文件/文件夹名称>"
    echo "示例: $0 /home/user/docs temp_dir"
    exit 1
fi

# 定义参数变量
TARGET_PATH="$1"
DELETE_NAME="$2"

# 检查目标路径是否存在
if [ ! -d "$TARGET_PATH" ]; then
    echo "错误：目标路径 '$TARGET_PATH' 不存在或不是目录！"
    exit 1
fi

# 查找所有匹配的文件/文件夹
echo "正在查找 '$TARGET_PATH' 下所有名为 '$DELETE_NAME' 的文件/文件夹..."
MATCHES=$(find "$TARGET_PATH" -name "$DELETE_NAME" -print)

# 检查是否找到匹配项
if [ -z "$MATCHES" ]; then
    echo "未找到任何名为 '$DELETE_NAME' 的文件/文件夹，无需删除。"
    exit 0
fi

# 列出所有待删除项
echo -e "\n找到以下待删除的文件/文件夹："
echo "$MATCHES"

# 确认删除操作
read -p $'\n确认要删除以上所有项吗？(y/N) ' CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "删除操作已取消。"
    exit 0
fi

# 执行删除操作
echo -e "\n开始删除..."
while IFS= read -r item; do
    if [ -e "$item" ]; then
        # 判断是文件还是文件夹，使用对应的删除命令
        if [ -d "$item" ]; then
            rm -rf "$item"
            echo "已删除文件夹: $item"
        else
            rm -f "$item"
            echo "已删除文件: $item"
        fi
    fi
done <<< "$MATCHES"

echo -e "\n删除操作完成！"
exit 0