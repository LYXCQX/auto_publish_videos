#!/bin/bash

# 确保脚本遇到错误时立即停止
set -e
python3 -m venv myenv
# Activate the virtual environment
source myenv/bin/activate

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
