from datetime import datetime

import loguru
from apscheduler.schedulers.blocking import BlockingScheduler

from util.db.sql_utils import getdb
from video_dedup.config_parser import read_dedup_config
from video_dedup.video_dedup_by_config import process_dedup_by_config

loguru.logger.add("error.log", format="{time} {level} {message}", level="ERROR")
config = read_dedup_config()


def scheduled_job():
    try:
        db = getdb()
        # 查询需要发布的用户，用来提前生成视频
        user_infos = db.fetchall("select * from user_info")
        # 查询可以发布的商品
        video_goods = db.fetchall("select * from video_goods")
        # 循环并找出可以生成视频（未到发布条数） 还没生成视频的用户
        for user_info in user_infos:
            try:
                for video_good in video_goods:
                    # 相同的平台才能生成对应的视频
                    if user_info['type'] == video_good['type']:
                        video_goods_publish = db.fetchall(
                            f'select vg_id from video_goods_publish where user_id = {user_info["user_id"]} and DATE(create_time) = CURDATE()')
                        if len(video_goods_publish) < user_info['pub_num'] and video_good['id'] not in [obj['vg_id'] for obj in
                                                                                                        video_goods_publish]:
                            try:
                                video_path = process_dedup_by_config(config, video_good)
                                db.execute(f"INSERT INTO video_goods_publish(`goods_id`, `user_id`, `vg_id`, `video_path`, `state`) "
                                           f"VALUES ({video_good['goods_id']},{user_info['user_id']},{video_good['id']},'{video_path}',{1})")
                            except Exception as e:
                                loguru.logger.exception(f'{user_info["user_id"]} -  商品名称:{video_good["goods_name"]} 商品id:{video_good["id"]}')
                                pass
            except Exception as e:
                loguru.logger.error(f"生成要发布的视频失败: {e}")
    except Exception as e:
        loguru.logger.error(f"生成要发布的视频失败: {e}")


if __name__ == '__main__':
    scheduler = BlockingScheduler()
    now = datetime.now()
    initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second + 10,microsecond=0)
    scheduler.add_job(scheduled_job, 'interval', minutes=30, start_date=initial_execution_time)  # 每30分钟执行一次
    scheduler.start()
