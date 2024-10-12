@echo off

cd D:\IDEA\workspace\auto_publish_videos
call conda activate auto_publish_videos

@REM pip install -r requirements.txt

@REM playwright install chromium firefox

 start /B python search_download.py
 start /B python subtitle_remove.py
 start /B python split.py
 start /B python merge.py
 start /B python upload.py
@REM  start /B python add_user.py