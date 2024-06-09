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

# 激活虚拟环境
. $VENV_PATH/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 依赖
playwright install chromium firefox

# 检查并运行 search_download.py
if ! pgrep -f search_download.py > /dev/null; then
  python3 search_download.py &
  SEARCH_DOWNLOAD_PID=$!
else
  echo "search_download.py is already running"
fi

# 检查并运行 split.py
if ! pgrep -f split.py > /dev/null; then
  python3 split.py &
  SPLIT_PID=$!
else
  echo "split.py is already running"
fi

# 检查并运行 merge.py
if ! pgrep -f merge.py > /dev/null; then
  python3 merge.py &
  MAIN_PID=$!
else
  echo "main.py is already running"
fi

# 检查并运行 kuaishou_upload.py
if ! pgrep -f upload.py > /dev/null; then
  python3 upload.py &
  UPLOAD_PID=$!
else
  echo "kuaishou_upload.py is already running"
fi
# 检查并运行 add_user.py
if ! pgrep -f add_user.py > /dev/null; then
  python3 add_user.py &
  ADD_USER_PID=$!
else
  echo "add_user.py is already running"
fi

# 检查并运行 add_upload_user.py
if ! pgrep -f add_upload_user.py > /dev/null; then
  python3 add_upload_user.py &
  ADD_UPLOAD_USER_PID=$!
else
  echo "add_upload_user.py is already running"
fi

# 检查并运行 video_manage.py
if ! pgrep -f video_manage.py > /dev/null; then
  python3 video_manage.py &
  VIDEO_MANAGE_PID=$!
else
  echo "video_manage.py is already running"
fi

# 等待所有后台进程完成
if [ -n "$SEARCH_DOWNLOAD_PID" ]; then
  wait $SEARCH_DOWNLOAD_PID
fi

if [ -n "$SPLIT_PID" ]; then
  wait $SPLIT_PID
fi

if [ -n "$MAIN_PID" ]; then
  wait $MAIN_PID
fi

if [ -n "$UPLOAD_PID" ]; then
  wait $UPLOAD_PID
fi

if [ -n "$ADD_USER_PIDD" ]; then
  wait $ADD_USER_PID
fi

if [ -n "$ADD_UPLOAD_USER_PID" ]; then
  wait $ADD_UPLOAD_USER_PID
fi

if [ -n "$VIDEO_MANAGE_PID" ]; then
  wait $VIDEO_MANAGE_PID
fi

echo "All scripts have finished executing."
