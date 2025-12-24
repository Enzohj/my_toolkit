#!/bin/bash
# 检查是否传入关键词
if [ -z "$1" ]; then
    echo "Error: 请传入要杀死的进程关键词！"
    echo "用法：$0 <关键词>"
    echo "示例：$0 python"
    exit 1
fi

# 查找并显示要杀死的进程
echo "===== 即将杀死的进程 ====="
ps -ef | grep "$1" | grep -v grep
if [ $? -ne 0 ]; then
    echo "未找到包含关键词「$1」的进程！"
    exit 0
fi

# 提示用户确认
echo "是否继续？(y/n)"
read -r confirm
if [ "$confirm" != "y" ]; then
    echo "操作取消！"
    exit 0
fi
# 执行杀死操作
ps -ef | grep "$1" | grep -v grep | awk '{print $2}' | xargs kill -9
echo "进程已全部杀死！"