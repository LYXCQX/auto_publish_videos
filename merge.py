import argparse
import random
import re
from datetime import datetime
import pandas as pd
import loguru
from apscheduler.schedulers.blocking import BlockingScheduler
from filelock import FileLock, Timeout

from util.audio_util import wrap_text
from util.db.sql_utils import getdb
from util.file_util import get_mp4_files_path
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
        video_goods = db.fetchall("select * from video_goods where state = 1 order by id desc ")
        # 循环并找出可以生成视频（未到发布条数） 还没生成视频的用户
        for user_info in user_infos:
            loguru.logger.info(f"合并视频有{len(user_infos)}用户需要处理")
            try:
                video_goods_publish = db.fetchall(
                    f'select vg.brand_base,vgp.vg_id from video_goods_publish vgp left join video_goods vg on vgp.vg_id=vg.id where user_id = {user_info["user_id"]} and DATE(vgp.create_time) = CURDATE()')
                video_goods_publish_his = db.fetchall(
                    f'select vg.brand_base,vgp.vg_id from video_goods_publish vgp left join video_goods vg on vgp.vg_id=vg.id where user_id = {user_info["user_id"]}')
                pub_num = len(video_goods_publish)
                use_goods = get_use_good(video_goods, video_goods_publish_his, 1)
                if len(use_goods) == 0:
                    use_goods = get_use_good(video_goods, video_goods_publish, 0)
                user_brands = []
                for use_good in use_goods:
                    goods_des = f"{random.choice(config.bottom_sales)}， {get_goods_des(use_good)}，{random.choice(config.tail_sales)}"
                    use_good['sales_script'] = get_sales_scripts(use_good)
                    loguru.logger.info(f"合并视频有{len(video_goods)}商品需要处理")
                    # 相同的平台才能生成对应的视频
                    if user_info['type'] == use_good['type']:
                        if (pub_num < user_info['pub_num']
                                and use_good['id'] not in [obj['vg_id'] for obj in video_goods_publish]
                                and use_good['brand_base'] not in user_brands
                        ):
                            try:
                                video_path_list = get_mp4_files_path(f"{config.video_path}{use_good['brand_base']}")
                                if len(video_path_list) < 1:
                                    loguru.logger.info("合并视频时没有合适的视频，请等待视频分割处理完成")
                                else:
                                    video_path = process_dedup_by_config(config, use_good, goods_des)
                                    if video_path is not None:
                                        db.execute(
                                            f"INSERT INTO video_goods_publish(`goods_id`, `user_id`, `vg_id`, `video_path`,`brand`,`video_title`, `state`) "
                                            f"VALUES ({use_good['goods_id']},{user_info['user_id']},{use_good['id']},'{video_path}','{use_good['brand']}','{goods_des}',{1})")
                                        pub_num += 1
                                        user_brands.append(use_good['brand_base'])
                            except Exception as e:
                                loguru.logger.exception(
                                    f'{user_info["user_id"]} -  商品名称:{use_good["goods_name"]} 商品id:{use_good["id"]}')
                                pass
            except Exception as e:
                loguru.logger.error(f"生成要发布的视频失败: {e}")
    except Exception as e:
        loguru.logger.error(f"生成要发布的视频失败: {e}")


def get_use_good(video_goods, video_goods_publish, video_type):
    pub_ids = []
    pub_brand = []
    for vg_p in video_goods_publish:
        pub_ids.append(vg_p['vg_id'])
        pub_brand.append(vg_p['brand_base'])
    no_brand = []
    no_id = []
    for video_good in video_goods:
        video_path_list = get_mp4_files_path(f"{config.video_path}{video_good['brand_base']}")
        if len(video_path_list) > 1:
            if video_good['brand_base'] not in pub_brand:
                no_brand.append(video_good)
            elif video_good['id'] not in pub_ids:
                no_id.append(video_good)
        else:
            video_goods.remove(video_good)
    if len(no_brand) > 0:
        use_goods = no_brand
    elif len(no_id) > 0:
        use_goods = no_id
    else:
        if video_type == 1:
            use_goods = []
        else:
            use_goods = video_goods
    # 将数据转换为 DataFrame
    df = pd.DataFrame(use_goods)
    # 随机打乱行的顺序
    df_shuffled = df.sample(frac=1).reset_index(drop=True)
    # 使用 drop_duplicates 方法去重
    df_unique = df_shuffled.drop_duplicates(subset='brand_base')
    # 将去重后的 DataFrame 转换回字典列表
    result = df_unique.to_dict(orient='records')
    return use_goods


def get_goods_des(video_good):
    goods_price = convert_amount(video_good['goods_price'])
    real_price = convert_amount(video_good['real_price'])
    goods_des = [
        f"{get_brand_no_kh(video_good['brand'])}刚上新一个{video_good['goods_title']}的活动{'' if goods_price == real_price else f'，原价{goods_price}'},现在只要{real_price},{get_good_des_ran(video_good['goods_des'])}{random.choice(config.center_sales)}",
        f"{get_brand_no_kh(video_good['brand'])}{video_good['goods_title']},{get_good_des_ran(video_good['goods_des'])}这价格也太划算了吧，历史低价，赶紧囤够几单慢慢用,{random.choice(config.center_sales)}",
        f"这个只要{real_price}的{video_good['goods_title']}绝对不允许还有人不知道,{get_good_des_ran(video_good['goods_des'])}{random.choice(config.center_sales)}",
        f"{video_good['goods_title']}仅需{real_price},{get_good_des_ran(video_good['goods_des'])}{random.choice(config.center_sales)}",
        f"赶紧来看看我们的{video_good['goods_title']}只要{real_price}，你就可以体验到这块超值优惠的套餐哟,{get_good_des_ran(video_good['goods_des'])}{random.choice(config.center_sales)}",
        f"{video_good['goods_title']}现在价格超值，{get_good_des_ran(video_good['goods_des'])}这个价格简直不能太好了，这个价格不会持续太久,{random.choice(config.center_sales)}",
        f"{real_price}就可以享受到{video_good['goods_title']},{get_good_des_ran(video_good['goods_des'])}{random.choice(config.center_sales)}",
        f"{get_brand_no_kh(video_good['brand'])}{video_good['goods_title']}{'' if goods_price == real_price else f'，昨天还要{goods_price},今天'}只要{real_price},{get_good_des_ran(video_good['goods_des'])}{random.choice(config.center_sales)}",
        f"{get_brand_no_kh(video_good['brand'])}{video_good['goods_title']}只要{real_price},{get_good_des_ran(video_good['goods_des'])}{random.choice(config.center_sales)}"]
    return random.choice(goods_des)


def get_good_des_ran(goods_des):
    goods_des = f'{goods_des},' if goods_des is not None and goods_des != '' else ''
    goods_des_s = [
        goods_des,
        '',
    ]

    return random.choice(goods_des_s)


def get_sales_scripts(video_good):
    goods_price = convert_amount(video_good['goods_price'])
    real_price = convert_amount(video_good['real_price'])
    sales_script = [
        f"{get_brand_no_kh(video_good['brand'])}\n{handle_txt(video_good['goods_title'], 10)}\n{'' if goods_price == real_price else f'原价{goods_price}'}\n仅需{real_price}"]
    if video_good['sales_script'] != '' and video_good['sales_script'] is not None:
        sales_script.append(video_good['sales_script'])
    return random.choice(sales_script).replace('\n\n', '\n').replace('\n \n', '\n')


def handle_txt(text, width):
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
    nind = 0
    for part in parts:
        if len(current_line) + len(part) <= width:
            current_line += part
        else:
            nind += 1
            if nind > 1:
                wrapped_text += current_line.strip()
                return wrapped_text
            else:
                wrapped_text += current_line.strip() + '\n'
            current_line = part
    if current_line:
        wrapped_text += current_line.strip()
    return wrapped_text


def get_brand_no_kh(brand):
    brand_new = brand.replace('（', '(')
    return brand_new.split('(')[0] if '(' in brand_new else brand_new


def convert_amount(amount):
    int_part = int(amount)  # 获取整数部分
    if int_part < 1:
        return f"不到{int_part+1}块"
    elif int_part < 20:
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
