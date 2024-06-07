import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime

import loguru
from apscheduler.schedulers.blocking import BlockingScheduler
from filelock import FileLock, Timeout

from MediaCrawler.tools import utils
from util.db.sql_utils import getdb
from util.file_util import download_video, get_file_names
from video_dedup.config_parser import read_dedup_config

loguru.logger.add("error.log", format="{time} {level} {message}", level="ERROR")
loguru.logger.add("info.log", format="{time} {level} {message}", level="INFO")
# 获取当前脚本文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 将 MediaCrawler 目录添加到 sys.path
media_crawler_path = os.path.join(current_dir, 'MediaCrawler')
sys.path.append(media_crawler_path)
from MediaCrawler.main import run_crawler_with_args

config = read_dedup_config()
lock = FileLock("/opt/software/auto_publish_videos/job.lock")


def download_lock():
    try:
        loguru.logger.debug("尝试获取锁下载文件")
        with lock.acquire(timeout=5):
            loguru.logger.debug("成功获取锁，开始下载文件")
            start_download()
    except Timeout:
        loguru.logger.warning("获取锁失败，下载文件操作被跳过")
    except Exception as e:
        loguru.logger.error(f"下载文件失败：{e}")


def start_download():
    try:
        db = getdb()
        brands = db.fetchall('select distinct(brand_base) from video_goods where state = 1')
        for brand in brands:
            platform = 'xhs'
            lt = 'qrcode'
            type = 'search'
            start = 1
            brand = brand['brand_base']
            keywords = brand + '视频素材'

            asyncio.get_event_loop().run_until_complete(run_crawler_with_args(platform, lt, type, start, keywords))
            json_store_path = f'data/{platform}'
            file_count = max([int(file_name.split("_")[0]) for file_name in os.listdir(json_store_path)])
            file_patch = f"{json_store_path}/{file_count}_{type}_contents_{utils.get_current_date()}.json"
            videos = json.load(open(file_patch, encoding='utf-8'))
            file_name = get_file_names([config.need_split_path, config.video_path])
            for video in videos:
                try:
                    if video['note_id'] not in file_name:
                        down_path = f"{config.need_split_path}{brand}"
                        if not os.path.exists(down_path):
                            os.makedirs(down_path)
                        video_path = f"{down_path}/{video['note_id']}.mp4"
                        if not os.path.exists(video_path):
                            if video['video_url_none_sy'] != '':
                                download_video(video['video_url_none_sy'], video_path)
                                time.sleep(1)
                except Exception as e:
                    loguru.logger.error(f"下载视频时发生错误: {e}")
            os.remove(file_patch)
    except Exception as e:
        loguru.logger.error(f"下载视频时发生错误: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script Scheduler")
    parser.add_argument("--one", action="store_true", help="Run the script immediately")
    args = parser.parse_args()

    if args.one:
        download_lock()
    else:
        scheduler = BlockingScheduler()
        now = datetime.now()
        initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second,
                                                        microsecond=0)
        # 使用 cron 规则指定每天23点执行一次
        scheduler.add_job(download_lock, 'cron', hour=23, minute=0, max_instances=1)
        scheduler.start()
