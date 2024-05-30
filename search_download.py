import asyncio
import json
import os
import string
import sys
import time
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from MediaCrawler.tools import utils
from util.db.sql_utils import getdb
from util.file_util import download_video
from video_dedup.config_parser import read_dedup_config

# 获取当前脚本文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 将 MediaCrawler 目录添加到 sys.path
media_crawler_path = os.path.join(current_dir, 'MediaCrawler')
sys.path.append(media_crawler_path)
from MediaCrawler.main import run_crawler_with_args

config = read_dedup_config()


def call_main_script():
    db = getdb()
    brands = db.fetchall('select distinct(brand) from video_goods where state = 1')
    for brand in brands:
        platform = 'xhs'
        lt = 'qrcode'
        type = 'search'
        start = 1
        brand = brand['brand']
        keywords = brand + '视频素材'

        asyncio.get_event_loop().run_until_complete(run_crawler_with_args(platform, lt, type, start, keywords))
        json_store_path = f'data/{platform}'
        file_count = max([int(file_name.split("_")[0]) for file_name in os.listdir(json_store_path)])
        file_patch = f"{json_store_path}/{file_count}_{type}_contents_{utils.get_current_date()}.json"
        videos = json.load(open(file_patch, encoding='utf-8'))
        for video in videos:
            down_path = f"{config.need_split_path}{brand}"
            if not os.path.exists(down_path):
                os.makedirs(down_path)
            video_path = f"{down_path}\{video['note_id']}.mp4"
            if not os.path.exists(video_path):
                if video['video_url_none_sy'] != '':
                    download_video(video['video_url_none_sy'], video_path)
                    time.sleep(1)
        os.remove(file_patch)


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    now = datetime.now()
    initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second + 10, microsecond=0)
    # 使用 cron 规则指定每天23点执行一次
    scheduler.add_job(call_main_script, 'cron', hour=23, minute=0)
    scheduler.start()
    # call_main_script()
