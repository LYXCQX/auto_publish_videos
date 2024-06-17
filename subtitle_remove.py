import argparse
import os
import time
from datetime import datetime

import loguru
from filelock import FileLock, Timeout

from util.file_util import get_mp4_files_path
from util.sub_title_util import process_video

loguru.logger.add("error.log", format="{time} {level} {message}", level="ERROR")
from apscheduler.schedulers.blocking import BlockingScheduler

from video_dedup.config_parser import read_dedup_config

config = read_dedup_config()
lock = FileLock("/opt/software/auto_publish_videos/job.lock")


def subtitle_remove():
    try:
        loguru.logger.debug("尝试获取锁字幕移除")
        with lock.acquire(timeout=5):
            loguru.logger.debug("成功获取锁，开始字幕移除")
            subtitle_remove_one(config.sub_remove_path, config.need_split_path)
    except Timeout:
        loguru.logger.warning("获取锁失败，字幕移除操作被跳过")
    except Exception as e:
        loguru.logger.error(f"字幕移除失败：{e}")


def subtitle_remove_one(folder_path, source_path):
    video_files = get_mp4_files_path(folder_path)
    loguru.logger.info(f"字幕移除需要处理的数据有{len(video_files)}条")
    last_time = time.time()
    for video_path in video_files:
        try:
            video_folder = os.path.dirname(video_path)
            output_folder = os.path.join(source_path, video_folder.replace(folder_path, ''))
            loguru.logger.info(f'字幕移除正在处理的文件为{video_path}')
            process_video(video_path, output_folder, 'patchmatch')
            # 每次运行完校验一下上次的运行时间，如果超过半个小时，则看一下有没有需要合并的数据
            if last_time - time.time() > 1800:
                # scheduled_job()
                last_time = time.time()
        except:
            loguru.logger.info(f"字幕移除失败 {video_path}: {e}")
        finally:
            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except PermissionError as e:
                    loguru.logger.info(f"字幕移除后删除视频失败 {video_path}: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Script Scheduler")
    parser.add_argument("--one", action="store_true", help="Run the script immediately")
    args = parser.parse_args()

    if args.one:
        subtitle_remove()
    else:
        scheduler = BlockingScheduler()
        now = datetime.now()
        initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second,
                                                        microsecond=0)
        scheduler.add_job(subtitle_remove, 'interval', minutes=25, max_instances=1)  # 每30分钟执行一次
        scheduler.start()
    # split_job()
