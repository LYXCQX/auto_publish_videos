#!/bin/bash

# 确保脚本遇到错误时立即停止
set -e
cd /opt/software/auto_publish_videos
# 定义虚拟环境路径
VENV_PATH="venv"

# 创建虚拟环境（如果不存在）
if [ ! -d "$VENV_PATH" ]; then
  python3 -m venv $VENV_PATH
fi

# Activate the virtual environment
. $VENV_PATH/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install playwright dependencies
npx playwright install chromium firefox
# 运行 search_download.py
python3 search_download.py &
SEARCH_DOWNLOAD_PID=$!

# 运行 split.py
python3 split.py &
SPLIT_PID=$!

# 运行 main.py
python3 main.py &
MAIN_PID=$!

# 等待所有后台进程完成
wait $SEARCH_DOWNLOAD_PID
wait $SPLIT_PID
wait $MAIN_PID

echo "All scripts have finished executing."
