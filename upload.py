# -*- coding: utf-8 -*-
import argparse
import asyncio
import random
import time
from datetime import datetime

import loguru
from apscheduler.schedulers.blocking import BlockingScheduler

from video_upload.kuaishou.kuaishou_upload import KuaiShouVideo


def upload_video():
    random_seconds = random.randint(1, 2 )
    loguru.logger.info(f'上传视频随机睡眠：{random_seconds}秒')
    time.sleep(random_seconds)
    app = KuaiShouVideo()
    # app.main()
    asyncio.run(app.main())


if __name__ == '__main__':
    scheduler = BlockingScheduler()
    parser = argparse.ArgumentParser(description="Script Scheduler")
    parser.add_argument("--one", action="store_true", help="Run the script immediately")
    args = parser.parse_args()
    if args.one:
        upload_video()
    else:
        now = datetime.now()
        initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second,
                                                        microsecond=0)
        # 使用 cron 规则指定每天23点执行一次
        scheduler.add_job(upload_video, 'interval', minutes=60, max_instances=1)  # 每30分钟执行一次
        scheduler.start()
    # upload_video()
