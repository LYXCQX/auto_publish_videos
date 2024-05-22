
from video_dedup.config_parser import read_dedup_config
from video_dedup.video_dedup_by_config import process_dedup_by_config

config = read_dedup_config()


def scheduled_job():
    process_dedup_by_config(config)


if __name__ == '__main__':
    # scheduler = BlockingScheduler()
    # now = datetime.now()
    # initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second + 10,
    #                                                 microsecond=0)
    # scheduler.add_job(scheduled_job, 'interval', seconds=30, start_date=initial_execution_time)  # 每30分钟执行一次
    # scheduler.start()
    scheduled_job()
