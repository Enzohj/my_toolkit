#!/usr/bin/env bash

set -e

if [ $# -lt 1 ]; then
  echo "Usage: hang.sh <command> [args...]"
  echo "Example: hang.sh python train.py --epochs 10"
  exit 1
fi

# 日志文件名：按时间戳生成，避免覆盖
LOG_DIR="${HANG_LOG_DIR:-./logs}"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/hang_$TIMESTAMP.log"

# 核心逻辑
nohup "$@" >"$LOG_FILE" 2>&1 &

PID=$!

echo "✔ Command started in background"
echo "✔ PID: $PID"
echo "✔ Log: $LOG_FILE"
echo "✔ Info: ps -ef | grep $PID"
echo "✔ Kill: kill -9 $PID"