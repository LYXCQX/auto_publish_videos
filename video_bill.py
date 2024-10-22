import argparse
import asyncio
import datetime
import random

import loguru
from apscheduler.schedulers.blocking import BlockingScheduler
from playwright.async_api import async_playwright

from merge import get_goods_des, get_sales_scripts
from util.db.sql_utils import getdb
from util.file_util import get_mp4_files_path, get_account_file
from video_dedup.config_parser import read_dedup_config
from video_dedup.video_dedup_by_config import process_dedup_by_config
from video_upload.kuaishou.kuaishou_upload import kuaishou_setup, KuaiShouVideo

loguru.logger.add("error.log", format="{time} {level} {message}", level="ERROR")
config = read_dedup_config()
db = getdb()


def merge_one():
    try:
        video_bills = db.fetchall(
            "SELECT * FROM video_bill WHERE video_bill.state = 1 AND (last_time IS NULL OR DATE(DATE_ADD(last_time, INTERVAL cycle DAY)) <= CURDATE())")
        for video_bill in video_bills:
            # 查询需要发布的用户，用来提前生成视频
            user_infos = db.fetchall(
                f"select * from user_info where user_info.user_level >={video_bill['user_level']} and type =1")
            # 查询可以发布的商品
            use_good = db.fetchone(
                f"select * from video_goods where state = 1 and  goods_id ={video_bill['goods_id']} ")
            is_up_last_time = True
            # 循环并找出可以生成视频（未到发布条数） 还没生成视频的用户
            for user_info in user_infos:
                for i in range(video_bill['pub_num']):
                    loguru.logger.info(f"合并视频有{len(user_infos)}用户需要处理")
                    try:
                        goods_des = f"{random.choice(config.bottom_sales)}， {get_goods_des(use_good)}，{random.choice(config.tail_sales)}"
                        use_good['sales_script'] = get_sales_scripts(use_good)
                        loguru.logger.info(f"合并视频有{len(video_bills)}商品需要处理")
                        # 相同的平台才能生成对应的视频
                        if user_info['type'] == use_good['type']:
                            try:
                                video_path_list = get_mp4_files_path(f"{use_good['video_path']}")
                                if len(video_path_list) < 1:
                                    is_up_last_time = False
                                    loguru.logger.info("合并视频时没有合适的视频，请等待视频分割处理完成")
                                else:
                                    video_path = process_dedup_by_config(config, use_good, goods_des, True)
                                    if video_path is not None:

                                        if video_bill['publish_now'] == 1:
                                            vpg_id = db.execute(
                                                "INSERT INTO video_goods_publish(`goods_id`, `user_id`, `vg_id`, `video_path`,`brand`,`video_title`, `state`,`type`,`vb_id`) "
                                                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                                (use_good['goods_id'], user_info['user_id'], use_good['id'], video_path,
                                                 use_good['brand'], goods_des, 1, 1, video_bill['id'])
                                            )
                                            asyncio.run(update_now(user_info, video_bill, vpg_id))

                                    else:
                                        db.execute(
                                            "INSERT INTO video_goods_publish(`goods_id`, `user_id`, `vg_id`, `video_path`,`brand`,`video_title`, `state`,`type`,`vb_id`) "
                                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                            (use_good['goods_id'], user_info['user_id'], use_good['id'], video_path,
                                             use_good['brand'], goods_des, 1, 2, video_bill['id'])
                                        )
                            except Exception as e:
                                is_up_last_time = False
                                loguru.logger.exception(
                                    f'{user_info["user_id"]} -  商品名称:{use_good["goods_name"]} 商品id:{use_good["id"]}')
                                pass
                    except Exception as e:
                        is_up_last_time = False
                        loguru.logger.error(f"生成要发布的视频失败: {e}")
            if is_up_last_time:
                if video_bill['type'] == 1:
                    db.execute(f"update video_bill set 	last_time = now(),state =2 where id = {video_bill['id']}")
                else:
                    db.execute(f"update video_bill set 	last_time = now() where id = {video_bill['id']}")
    except Exception as e:
        loguru.logger.error(f"生成要发布的视频失败: {e}")


def hot_video_update():
    try:
        video_goods = db.fetchall(
            "SELECT * FROM video_goods WHERE state = 1 AND hot_score =100")
        ensure_list_length(video_goods, 80)

        for use_good in video_goods:
            # 查询需要发布的用户，用来提前生成视频
            user_infos = db.fetchall(
                f"select * from user_info where user_id = 4142857862")
            # 循环并找出可以生成视频（未到发布条数） 还没生成视频的用户
            for user_info in user_infos:
                loguru.logger.info(f"合并视频有{len(user_infos)}用户需要处理")
                try:
                    goods_des = f"{random.choice(config.bottom_sales)}， {get_goods_des(use_good)}，{random.choice(config.tail_sales)}"
                    use_good['sales_script'] = get_sales_scripts(use_good)
                    loguru.logger.info(f"合并视频有{len(use_good)}商品需要处理")
                    # 相同的平台才能生成对应的视频
                    if user_info['type'] == use_good['type']:
                        try:
                            video_path_list = get_mp4_files_path(f"{use_good['video_path']}")
                            if len(video_path_list) < 1:
                                loguru.logger.info("合并视频时没有合适的视频，请等待视频分割处理完成")
                            else:
                                video_path = process_dedup_by_config(config, use_good, goods_des, True)
                                if video_path is not None:
                                    vpg_id = db.execute(
                                        "INSERT INTO video_goods_publish(`goods_id`, `user_id`, `vg_id`, `video_path`,`brand`,`video_title`, `state`,`type`,`vb_id`) "
                                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                        (use_good['goods_id'], user_info['user_id'], use_good['id'], video_path,
                                         use_good['brand'], goods_des, 1, 1, None)
                                    )
                                    asyncio.get_event_loop().run_until_complete(
                                        update_now(user_info, None, vpg_id))
                        except Exception as e:
                            loguru.logger.exception(
                                f'{user_info["user_id"]} -  商品名称:{use_good["goods_name"]} 商品id:{use_good["id"]}')
                            pass
                except Exception as e:
                    loguru.logger.error(f"生成要发布的视频失败: {e}")
    except Exception as e:
        loguru.logger.error(f"生成要发布的视频失败: {e}")


def ensure_list_length(original_list, leng):
    # 计算当前列表的长度
    current_length = len(original_list)

    # 如果长度小于 100，则复制列表
    if current_length < leng:
        # 计算需要添加的元素数量
        elements_to_add = leng - current_length

        # 将原列表复制到目标长度
        extended_list = original_list + original_list[:elements_to_add]

        return extended_list
    else:
        return original_list[:leng]


async def update_now(user_info, video_bill, vpg_id):
    app = KuaiShouVideo()
    # 根据视频生成记录发布视频
    good = db.fetchone(
        f"select * from video_goods_publish vgp left join video_tools.video_goods vg on vgp.vg_id = vg.id where vgp.state=1 and vgp.id = {vpg_id} ")
    account_file = get_account_file(user_info['user_id'])
    async with async_playwright() as playwright:
        await kuaishou_setup(account_file, handle=True)
        await app.upload(playwright, good, user_info, account_file, '', video_bill)


async def publish_video(vb_id_p):
    app = KuaiShouVideo()
    if vb_id_p is None:
        video_bills = db.fetchall(
            f"SELECT * FROM video_bill WHERE DATE(last_time) = CURDATE();")
    else:
        video_bills = db.fetchall(
            f"select * from video_bill where id = {vb_id_p} and  DATE(last_time) = CURDATE();")
    for video_bill in video_bills:
        # 根据视频生成记录发布视频
        goods = db.fetchall(
            f"select * from video_goods_publish vgp left join video_tools.video_goods vg on vgp.vg_id = vg.id where vgp.state=1 and vgp.vb_id = {video_bill['id']}")
        for good in goods:
            try:
                user_info = db.fetchone(
                    f"select * from user_info where user_id = {good['user_id']} ")
                account_file = get_account_file(user_info['user_id'])
                async with async_playwright() as playwright:
                    await kuaishou_setup(account_file, handle=True)
                    await app.upload(playwright, good, user_info, account_file, '', video_bill)
            except Exception as e:
                loguru.logger.error(f'商单发布视频失败，{e}')


def pub_v():
    asyncio.run(publish_video(None))


if __name__ == '__main__':
    # 合并并发布商单视频
    # merge_one()
    # 发片之星补单
    # hot_video_update()
    # 已经合并好的商单视频，群里审核完成，发布一下
    # asyncio.get_event_loop().run_until_complete(publish_video(None))
    scheduler = BlockingScheduler()
    parser = argparse.ArgumentParser(description="Script Scheduler")
    parser.add_argument("--one", action="store_true", help="Run the script immediately")
    args = parser.parse_args()
    if args.one:
        merge_one()
    else:
        # 使用 cron 规则指定每天23点执行一次
        # 使用 cron 规则指定每天凌晨4点执行一次
        # scheduler.add_job(merge_one, 'cron', hour=4, minute=0, max_instances=1)  # 每天4点执行一次
        scheduler.add_job(merge_one, 'interval', minutes=30, max_instances=1)  # 每30分钟执行一次
        scheduler.add_job(pub_v, 'interval', minutes=30, max_instances=1)
        scheduler.start()
