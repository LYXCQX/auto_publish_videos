import argparse
import random
import re
from datetime import datetime

import loguru
from apscheduler.schedulers.blocking import BlockingScheduler
from filelock import FileLock, Timeout

from util.db.sql_utils import getdb
from video_dedup.config_parser import read_dedup_config
from video_dedup.video_dedup_by_config import process_dedup_by_config

loguru.logger.add("error.log", format="{time} {level} {message}", level="ERROR")
config = read_dedup_config()

lock = FileLock("/opt/software/auto_publish_videos/job.lock")


def lock_create_video():
    try:
        loguru.logger.debug("尝试获取锁来生成视频")
        with lock.acquire(timeout=5):
            loguru.logger.debug("成功获取锁，开始生成视频")
            scheduled_job()
    except Timeout:
        loguru.logger.warning("获取锁失败，生成视频操作被跳过")
    except Exception as e:
        loguru.logger.error(f"生成视频失败：{e}")


def scheduled_job():
    try:
        db = getdb()
        # 查询需要发布的用户，用来提前生成视频
        user_infos = db.fetchall("select * from user_info")
        # 查询可以发布的商品
        video_goods = db.fetchall("select * from video_goods group by brand order by id desc ")
        # 循环并找出可以生成视频（未到发布条数） 还没生成视频的用户
        for user_info in user_infos:
            loguru.logger.info(f"合并视频有{len(user_infos)}用户需要处理")
            try:
                video_goods_publish = db.fetchall(
                    f'select vg_id from video_goods_publish where user_id = {user_info["user_id"]} and DATE(create_time) = CURDATE()')
                for video_good in video_goods:
                    video_good['goods_des'] = f"{random.choice(config.bottom_sales)}， {get_goods_des(video_good)}，{random.choice(config.tail_sales)}"
                    video_good['sales_script'] = get_sales_scripts(video_good)
                    loguru.logger.info(f"合并视频有{len(video_goods)}商品需要处理")
                    # 相同的平台才能生成对应的视频
                    if user_info['type'] == video_good['type']:
                        if (len(video_goods_publish) < user_info['pub_num']
                                and video_good['id'] not in [obj['vg_id'] for obj in video_goods_publish]):
                            try:
                                video_path = process_dedup_by_config(config, video_good)
                                db.execute(
                                    f"INSERT INTO video_goods_publish(`goods_id`, `user_id`, `vg_id`, `video_path`,`brand`, `state`) "
                                    f"VALUES ({video_good['goods_id']},{user_info['user_id']},{video_good['id']},'{video_path}','{video_good['brand']}',{1})")
                            except Exception as e:
                                loguru.logger.exception(
                                    f'{user_info["user_id"]} -  商品名称:{video_good["goods_name"]} 商品id:{video_good["id"]}')
                                pass
            except Exception as e:
                loguru.logger.error(f"生成要发布的视频失败: {e}")
    except Exception as e:
        loguru.logger.error(f"生成要发布的视频失败: {e}")


def get_goods_des(video_good):
    goods_price = convert_amount(video_good['goods_price'])
    real_price = convert_amount(video_good['real_price'])
    goods_des = [
        f"{video_good['brand']}刚上新一个{video_good['goods_title']}的活动{'' if goods_price == real_price else f'，原价{goods_price}'},仅需{real_price},{random.choice(config.center_sales)}",
        f"{video_good['brand']}刚上新一个{video_good['goods_title']}的活动{'' if goods_price == real_price else f'，原价{goods_price}'},现在只要{real_price},{random.choice(config.center_sales)}",
        f"{video_good['brand']}{video_good['goods_title']}这价格也太划算了吧，历史低价，赶紧囤够几单慢慢用，",
        f"{video_good['brand']}{video_good['goods_title']}{'' if goods_price == real_price else f'，昨天还要{goods_price},今天'}只要{real_price},{random.choice(config.center_sales)}",
        f"{video_good['brand']}{video_good['goods_title']}只要{real_price}，{random.choice(config.center_sales)}"]
    if video_good['goods_des'] != '' and video_good['goods_des'] is not None:
        goods_des.append(video_good['goods_des'])
    return random.choice(goods_des)


def get_sales_scripts(video_good):
    goods_price = convert_amount(video_good['goods_price'])
    real_price = convert_amount(video_good['real_price'])
    sales_script = [
        f"{video_good['brand']}\n{wrap_text(video_good['goods_title'], 13)}\n{'' if goods_price == real_price else f'原价{goods_price}'}\n仅需{real_price}"]
    if video_good['sales_script'] != '' and video_good['sales_script'] is not None:
        sales_script.append(video_good['sales_script'])
    return random.choice(sales_script).replace('\n\n', '\n').replace('\n \n', '\n')


def wrap_text(text, width):
    """
    将字符串按指定宽度换行，尽量保持字母和数字在一起
    :param text: 输入字符串
    :param width: 每行的字符数
    :return: 处理后的字符串
    """
    wrapped_text = ''
    # 使用正则表达式将文本分割为字母/数字组合和其他字符组合
    parts = re.findall(r'[\da-zA-Z]+|[^a-zA-Z\d\s]', text)
    current_line = ''
    for part in parts:
        if len(current_line) + len(part) <= width:
            current_line += part
        else:
            wrapped_text += current_line.strip() + '\n'
            current_line = part
    if current_line:
        wrapped_text += current_line.strip()
    return wrapped_text

def convert_amount(amount):
    int_part = int(amount)  # 获取整数部分

    if int_part < 20:
        return f"{int_part}块多"
    else:
        str_amount = str(int_part)
        length = len(str_amount)

        # 找到最高位的数字
        high_digit = str_amount[0]

        # 找到后面的位数
        remainder = "0" * (length - 1)

        # 构造模糊表示
        fuzzy_amount = high_digit + remainder + "多"

        return fuzzy_amount


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Script Scheduler")
    parser.add_argument("--one", action="store_true", help="Run the script immediately")
    args = parser.parse_args()
    if args.one:
        lock_create_video()
    else:
        scheduler = BlockingScheduler()
        now = datetime.now()
        initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second,
                                                        microsecond=0)
        scheduler.add_job(lock_create_video, 'interval', minutes=32, max_instances=1)  # 每30分钟执行一次
        scheduler.start()
