import argparse
import os
from _imp import acquire_lock
from datetime import datetime

import loguru
from filelock import FileLock, Timeout

loguru.logger.add("error.log", format="{time} {level} {message}", level="ERROR")
from apscheduler.schedulers.blocking import BlockingScheduler

from video_dedup.config_parser import read_dedup_config
from video_split.main import split_video

config = read_dedup_config()
lock = FileLock("/opt/software/auto_publish_videos/job.lock")


def split_job():
    try:
        loguru.logger.debug("尝试获取锁分割文件")
        with lock.acquire(timeout=5):
            loguru.logger.debug("成功获取锁，开始分割文件")
            rename_directories_with_spaces(config.need_split_path)
            split_video(config.need_split_path, config.video_path)
    except Timeout:
        loguru.logger.warning("获取锁失败，分割文件操作被跳过")
    except Exception as e:
        loguru.logger.error(f"分割文件失败：{e}")


def rename_directories_with_spaces(path):
    # 遍历路径下的所有文件和目录
    for root, dirs, files in os.walk(path):
        for dir_name in dirs:
            if ' ' in dir_name:
                # 构造原目录的完整路径
                old_dir_path = os.path.join(root, dir_name)
                # 去掉空格的目录名
                new_dir_name = dir_name.replace(' ', '')  # 可以选择其他替换方式
                new_dir_path = os.path.join(root, new_dir_name)

                # 重命名目录
                os.rename(old_dir_path, new_dir_path)
                print(f'Renamed: "{old_dir_path}" to "{new_dir_path}"')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Script Scheduler")
    parser.add_argument("--one", action="store_true", help="Run the script immediately")
    args = parser.parse_args()

    if args.one:
        split_job()
    else:
        scheduler = BlockingScheduler()
        now = datetime.now()
        initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=0)
        scheduler.add_job(split_job, 'interval', minutes=30, max_instances=1)  # 每30分钟执行一次
        scheduler.start()
    # split_job()

