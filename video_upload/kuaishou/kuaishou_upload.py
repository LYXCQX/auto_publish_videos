# -*- coding: utf-8 -*-
import base64
import json
import pathlib
import random
import uuid
from datetime import datetime
from io import BytesIO

import loguru
import pyautogui
from PIL import Image
from apscheduler.schedulers.blocking import BlockingScheduler
from playwright.async_api import Playwright, async_playwright
import os
import asyncio

from util.db.sql_utils import getdb
from util.file_util import get_account_file, download_video, get_upload_login_path

db = getdb()


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=account_file)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://cp.kuaishou.com/article/publish/video")
        try:
            await page.wait_for_selector(".SOCr7n1uoqI-", timeout=5000)  # 等待5秒
            loguru.logger.info("[+] cookie 有效")
            return True
        except Exception as e:
            loguru.logger.info("Error initializing browser:", str(e))
            loguru.logger.info("[+] 等待5秒 cookie 失效")
            return False


async def kuaishou_setup(account_file, handle=False):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            # Todo alert message
            return False
        loguru.logger.info('[+] cookie文件不存在或已失效，即将自动打开浏览器，请扫码登录，登陆后会自动生成cookie文件')
        await kuaishou_cookie_gen(account_file)
    return True


async def kuaishou_cookie_gen(account_file):
    async with async_playwright() as playwright:
        options = {
            'headless': True
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context()  # Pass any options
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://cp.kuaishou.com/article/publish/video")
        await page.locator('.login').click()
        await page.locator('.platform-switch').click()
        img_url = await page.locator('.qrcode img').get_attribute('src')
        # 解码 base64 图片
        img_data = base64.b64decode(img_url.replace('data:image/png;base64,', ''))
        img = Image.open(BytesIO(img_data))
        img.save(get_upload_login_path('kuaishou'))
        await page.wait_for_url('https://cp.kuaishou.com/article/publish/video', timeout=120000)
        await page.goto('https://cp.kuaishou.com/profile')
        user_id = await page.locator('.detail__userKwaiId').text_content()
        user_id = user_id.replace(" 用户 ID：", "").strip()

        user_name = await page.locator('.detail__name').text_content()
        # 将截图保存到指定路径
        await page.screenshot(path=f'/opt/software/auto_publish_videos/imgs/{uuid.uuid4()}.png')
        print(user_id, user_name)
        # 点击调试器的继续，保存cookie
        await context.storage_state(path=get_account_file(user_id))
        try:
            os.remove(get_upload_login_path('kuaishou'))
        except:
            loguru.logger.info(f"删除图片失败")
        return user_id, user_name


async def clickUpload(goods, page, css):
    # 点击 "上传视频" 按钮
    async with page.expect_file_chooser() as fc_info:
        await page.locator(css).click()
    file_chooser = await fc_info.value
    await file_chooser.set_files(goods['video_path'])


async def video_is_upload(goods, page):
    while True:
        try:
            number = await page.get_by_text('上传成功').count()
            if number > 0:
                loguru.logger.info("  [-]视频上传完毕")
                break
            else:
                loguru.logger.info("  [-] 正在上传视频中...")
                await asyncio.sleep(2)

                if await page.locator('上传失败').count():
                    loguru.logger.info("  [-] 发现上传出错了...")
                    loguru.logger.info("视频出错了，重新上传中")
                    await clickUpload(goods, page, ".SOCr7n1uoqI-")
        except:
            loguru.logger.info("  [-] 正在上传视频中...")
            await asyncio.sleep(2)


class KuaiShouVideo(object):
    async def upload(self, playwright: Playwright, goods, user_info, account_file, local_executable_path) -> None:
        # 使用 Chromium 浏览器启动一个浏览器实例
        if local_executable_path:
            browser = await playwright.chromium.launch(headless=True, executable_path=local_executable_path)
        else:
            browser = await playwright.chromium.launch(headless=True)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(storage_state=f"{account_file}")

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://cp.kuaishou.com/article/publish/video")
        loguru.logger.info('[+]正在上传-------{}.mp4'.format(goods['goods_title']))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        loguru.logger.info('[-] 正在打开主页...')
        await page.wait_for_url("https://cp.kuaishou.com/article/publish/video")
        await clickUpload(goods, page, ".SOCr7n1uoqI-")

        # 填充标题和话题
        # 检查是否存在包含输入框的元素
        # 这里为了避免页面变化，故使用相对位置定位：作品标题父级右侧第一个元素的input子元素
        await asyncio.sleep(1)
        loguru.logger.info("  [-] 正在填充标题和话题...")
        await page.locator(".clGhv3UpdEo-").fill(goods['goods_des'])
        loguru.logger.info(goods['tips'].split('#'))
        tips = goods['tips'].replace("\r", "").replace('\n', '').strip().split('#')
        tips = random.sample(tips, 4) if len(tips) > 3 else tips
        for tip in tips:
            if tip != '':
                loguru.logger.info(f"正在添加第{tip}话题")
                await page.type(".clGhv3UpdEo-", "#" + tip)
        # 查找按钮
        button = page.get_by_text('我知道了')
        # 检查按钮是否存在
        await button.click() if await button.count() > 0 else None
        await page.get_by_text('不允许下载此作品').locator('..').locator('.ant-checkbox').click()
        await page.get_by_text('当前地点').locator('..').locator('.ant-radio').click()
        # 授权位置
        await context.grant_permissions(['geolocation'])
        # 输入品牌品牌
        await page.locator('#rc_select_2').type(goods['brand'])
        # 选择第一个
        await page.press('#rc_select_2', "Enter")
        await video_is_upload(goods, page)
        try:
            await page.locator('.XwacrNGK2pY-').get_by_text('发布').click()
        except:
            loguru.logger.error(f"{goods['goods_name']}上传快手发现上传出错了...{goods['id']}")
            pass
        # 判断视频是否发布成功
        while True:
            # 判断视频是否发布成功
            try:
                await page.wait_for_url("https://cp.kuaishou.com/article/manage/video?status=2&from=publish",
                                        timeout=1500)  # 如果自动跳转到作品页面，则代表发布成功
                loguru.logger.info("  [-]视频发布成功")
                db.execute(f"update video_goods_publish set state = 2 where id = {goods['id']}")
                break
            except:
                loguru.logger.info("  [-] 视频正在发布中...")
                # await page.screenshot(full_page=True)
                await asyncio.sleep(0.5)
                # 查找按钮
                publish_button = page.locator('.XwacrNGK2pY-').get_by_text('发布')
                # 检查按钮是否存在
                await publish_button.click() if await publish_button.count() > 0 else None
        await context.storage_state(path=account_file)  # 保存cookie
        loguru.logger.info('  [-]cookie更新完毕！')
        await asyncio.sleep(2)  # 这里延迟是为了方便眼睛直观的观看
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()

    async def main(self):
        async with async_playwright() as playwright:
            # 根据视频生成记录发布视频
            goods = db.fetchall(
                "select * from video_goods_publish vgp left join video_tools.video_goods vg on vgp.vg_id = vg.id where vgp.state=1")
            for good in goods:
                try:
                    user_infos = db.fetchall(f"select * from user_info where user_id = {good['user_id']}")
                    # if user_infos['cookies'] == '':
                    user_info = user_infos[0]
                    if datetime.now().hour in json.loads(user_info['publish_hours']):
                        account_file = get_account_file(user_info['user_id'])
                        await kuaishou_setup(account_file, handle=True)
                        await self.upload(playwright, good, user_info, account_file, '')
                except Exception as e:
                    loguru.logger.info(e)


if __name__ == '__main__':
    app = KuaiShouVideo()
    # asyncio.run(app.main(), debug=False)
    scheduler = BlockingScheduler()
    now = datetime.now()
    initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute, second=now.second + 10,
                                                    microsecond=0)
    # 使用 cron 规则指定每天23点执行一次
    scheduler.add_job(app.main(), 'interval', minutes=30, max_instances=1)  # 每30分钟执行一次
    scheduler.start()
