import argparse
from datetime import datetime

import loguru
from filelock import FileLock, Timeout

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
            process_video(config.sub_remove_path, config.need_split_path, 'patchmatch')
    except Timeout:
        loguru.logger.warning("获取锁失败，字幕移除操作被跳过")
    except Exception as e:
        loguru.logger.error(f"字幕移除失败：{e}")


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
