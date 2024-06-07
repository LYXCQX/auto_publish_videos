import argparse
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
            split_video(config.need_split_path, config.video_path)
    except Timeout:
        loguru.logger.warning("获取锁失败，分割文件操作被跳过")
    except Exception as e:
        loguru.logger.error(f"分割文件失败：{e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Script Scheduler")
    parser.add_argument("--run-now", action="store_true", help="Run the script immediately")
    args = parser.parse_args()

    if args.one:
        split_job()
    else:
        scheduler = BlockingScheduler()
        now = datetime.now()
        initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=0)
        scheduler.add_job(split_job, 'interval', minutes=25, max_instances=1)  # 每30分钟执行一次
        scheduler.start()
    # split_job()
