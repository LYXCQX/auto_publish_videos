from datetime import datetime

import loguru
from apscheduler.schedulers.blocking import BlockingScheduler

from video_dedup.config_parser import read_dedup_config
from video_split.main import remove_audio, split_video

config = read_dedup_config()


def split_job():
    # remove_audio(config.need_split_path, config.video_path)
    try:
        split_video(config.need_split_path, config.video_path)
    except Exception as e:
        loguru.logger.error(f"分割文件失败: {e}")


if __name__ == '__main__':
    scheduler = BlockingScheduler()
    now = datetime.now()
    initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second + 10, microsecond=0)
    scheduler.add_job(split_job, 'interval', minutes=30, start_date=initial_execution_time)  # 每30分钟执行一次
    scheduler.start()
    # split_job()
