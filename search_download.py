import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
import ffmpeg
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
        platform = 'xhs'
        lt = 'qrcode'
        type = 'search'
        start = 1
        json_store_path = f'data/{platform}/json/'
        dowaloads_file = 'download.txt'
        if os.path.exists(dowaloads_file) and os.path.getsize(dowaloads_file) > 0:
            with open(dowaloads_file, 'r', encoding='utf-8') as file:
                downloads_video = json.load(file)
        else:
            # 如果文件不存在或为空，初始化一个空列表
            downloads_video = []
        json_today = f'{json_store_path}{type}_contents_{utils.get_current_date()}.json'
        json_today_f = {}
        if os.path.exists(json_today):
            with open(json_today, 'r', encoding='utf-8') as file:
                json_today_f = json.load(file)
        key_words = set(item["key_word"] for item in json_today_f)
        db = getdb()
        if args.now:
            brands = db.fetchall(
                'select distinct(brand_base) from video_goods where state = 1 and DATE(create_time) = CURDATE() order by id desc')
        else:
            brands = db.fetchall('select distinct(brand_base) from video_goods where state = 1 order by id desc')
        keywords = ''
        folders = [name for name in os.listdir(config.video_path)
                   if os.path.isdir(os.path.join(config.video_path, name))]
        for brand in brands:
            brand_base = f'{brand["brand_base"]}视频素材'
            if brand_base not in key_words and brand["brand_base"] not in folders:
                keywords += f'{brand_base},'
        if len(keywords) > 0:
            asyncio.get_event_loop().run_until_complete(run_crawler_with_args(platform, lt, type, start, keywords))
        download(dowaloads_file, downloads_video, json_store_path)
    except Exception as e:
        loguru.logger.error(f"下载视频时发生错误: {e}")


def download(dowaloads_file, downloads_video, json_store_path):
    for file_patch in os.listdir(json_store_path):
        file_patch = json_store_path + file_patch
        videos = json.load(open(file_patch, encoding='utf-8'))
        file_name = get_file_names([config.sub_remove_path, config.need_split_path, config.video_path])
        for video in videos:
            try:
                if video['note_id'] not in file_name and video['note_id'] not in downloads_video:
                    down_path = f"{config.sub_remove_path}{video['key_word'].replace('视频素材', '')}/{datetime.now().strftime('%Y-%m-%d')}"
                    if not os.path.exists(down_path):
                        os.makedirs(down_path)
                    video_path_tem = f"{config.video_temp}{video['note_id']}_tmp.mp4"
                    video_path = f"{down_path}/{video['note_id']}.mp4"
                    if not os.path.exists(video_path):
                        if video['video_url_none_sy'] != '':
                            download_video(video['video_url_none_sy'], video_path_tem)
                            downloads_video.append(video['note_id'])
                            if os.path.exists(video_path_tem):
                                input_stream = ffmpeg.input(video_path_tem)
                                output_stream = ffmpeg.output(input_stream['v'], input_stream['a'], video_path,
                                                              c='copy', y='-y')
                                ffmpeg.run(output_stream)
                                os.remove(video_path_tem)
            except Exception as e:
                loguru.logger.error(f"下载视频时发生错误: {e}")
            finally:
                with open(dowaloads_file, 'w', encoding='utf-8') as file:
                    json.dump(downloads_video, file, ensure_ascii=False, indent=4)
        os.remove(file_patch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script Scheduler")
    parser.add_argument("--one", action="store_true", help="Run the script immediately")
    parser.add_argument("--now", action="store_true", help="Run the script immediately")
    args = parser.parse_args()

    if args.one or args.now:
        download_lock()
    else:
        scheduler = BlockingScheduler()
        now = datetime.now()
        initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second,
                                                        microsecond=0)
        # 使用 cron 规则指定每天23点执行一次
        scheduler.add_job(download_lock, 'cron', hour=3, minute=0, max_instances=1)
        scheduler.start()
