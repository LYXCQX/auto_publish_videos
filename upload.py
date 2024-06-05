# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from video_upload.kuaishou.kuaishou_upload import KuaiShouVideo


def upload_video():
    app = KuaiShouVideo()
    # app.main()
    asyncio.run(app.main())


if __name__ == '__main__':
    scheduler = BlockingScheduler()
    now = datetime.now()
    initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second,
                                                    microsecond=0)
    # 使用 cron 规则指定每天23点执行一次
    scheduler.add_job(upload_video, 'interval', minutes=30, max_instances=1)  # 每30分钟执行一次
    scheduler.start()
    # upload_video()
