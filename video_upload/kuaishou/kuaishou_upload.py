# -*- coding: utf-8 -*-
import base64
import json
import pathlib
import random
import time
import uuid
from datetime import datetime
from io import BytesIO
import loguru
from PIL import Image
from apscheduler.schedulers.blocking import BlockingScheduler
from playwright.async_api import Playwright, async_playwright
import os
import asyncio

current_dir = os.path.dirname(os.path.abspath(__file__))
libs_path = os.path.join(current_dir, '..', '..', 'MediaCrawler', 'libs', 'stealth.min.js')
from util.db.sql_utils import getdb
from util.file_util import get_account_file, download_video, get_upload_login_path

loguru.logger.add("error.log", format="{time} {level} {message}", level="ERROR")
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
            await page.wait_for_selector(".SOCr7n1uoqI-", timeout=20000)  # 等待5秒
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
        await context.add_init_script(path=libs_path)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://cp.kuaishou.com/article/publish/video")
        await page.locator('.login').click()
        await page.locator('.platform-switch').click()
        login_url = page.url
        img_url = await page.locator('.qrcode img').get_attribute('src')
        # 解码 base64 图片
        img_data = base64.b64decode(img_url.replace('data:image/png;base64,', ''))
        img = Image.open(BytesIO(img_data))
        img.save(get_upload_login_path('kuaishou'))
        start_time = time.time()
        while True:
            if login_url == page.url:
                await asyncio.sleep(0.5)
            else:
                break
            elapsed_time = time.time() - start_time
            # 检查是否超过了超时时间
            if elapsed_time > 60:
                raise TimeoutError("操作超时，跳出循环")
        await page.goto('https://cp.kuaishou.com/profile')
        await asyncio.sleep(0.5)
        user_id = await get_user_id(page)
        user_name = await page.locator('.detail__name').text_content()
        loguru.logger.info(f'{user_id}---{user_name}')
        # 点击调试器的继续，保存cookie
        await context.storage_state(path=get_account_file(user_id))
        try:
            os.remove(get_upload_login_path('kuaishou'))
        except:
            loguru.logger.info(f"删除图片失败")
        return user_id, user_name


async def get_user_id(page):
    start_time = time.time()  # 获取开始时间
    while True:
        user_id = await page.locator('.detail__userKwaiId').text_content()
        user_id = user_id.replace(" 用户 ID：", "").strip()
        if user_id == '0':
            current_time = time.time()  # 获取当前时间
            elapsed_time = current_time - start_time  # 计算已经过去的时间
            if elapsed_time > 10:  # 如果已经过去的时间超过5秒
                break  # 退出循环
        else:
            break  # 退出循环
    return user_id


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

                if await page.get_by_text('上传失败').count():
                    loguru.logger.info("  [-] 发现上传出错了...")
                    loguru.logger.info("视频出错了，重新上传中")
                    await clickUpload(goods, page, ".SOCr7n1uoqI-")
        except Exception as e:
            loguru.logger.error("  [-] 正在上传视频中...", e)
            await asyncio.sleep(2)


class KuaiShouVideo(object):
    async def upload(self, playwright: Playwright, goods, user_info, account_file, local_executable_path) -> None:
        # 使用 Chromium 浏览器启动一个浏览器实例
        if local_executable_path:
            browser = await playwright.chromium.launch(headless=True, executable_path=local_executable_path)
        else:
            browser = await playwright.chromium.launch(headless=True)
        # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(storage_state=f"{account_file}", permissions=['geolocation'],
                                            geolocation={'latitude': float(goods['lat']),
                                                         'longitude': float(goods['lng'])})

        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://cp.kuaishou.com/article/publish/video")
        loguru.logger.info('[+]{}正在上传-------{}.mp4'.format(user_info['username'], goods['goods_title']))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        loguru.logger.info('[-] {}正在打开主页...'.format(user_info['username']))
        await page.wait_for_url("https://cp.kuaishou.com/article/publish/video")
        await clickUpload(goods, page, ".SOCr7n1uoqI-")

        # 填充标题和话题
        # 检查是否存在包含输入框的元素
        # 这里为了避免页面变化，故使用相对位置定位：作品标题父级右侧第一个元素的input子元素
        await asyncio.sleep(1)
        loguru.logger.info("  [-]{} 正在填充标题和话题...".format(user_info['username']))
        await page.locator(".clGhv3UpdEo-").fill(goods['video_title'])
        loguru.logger.info(f"{user_info['username']}话题{goods['tips'].split('#')}")
        tips = goods['tips'].replace("\r", "").replace('\n', '').strip().split('#')
        tips = random.sample(tips, 4) if len(tips) > 3 else tips
        for tip in tips:
            if tip != '':
                loguru.logger.info(f"{user_info['username']}正在添加第{tip}话题")
                await page.type(".clGhv3UpdEo-", "#" + tip)
        # 查找按钮
        button = page.get_by_text('我知道了')
        # 检查按钮是否存在
        await button.click() if await button.count() > 0 else None
        await page.get_by_text('不允许下载此作品').locator('..').locator('.ant-checkbox').click()
        await page.get_by_text('当前地点').locator('..').locator('.ant-radio').click()
        # 授权位置
        while True:
            pp_bl = await page.locator('.uUoMPMIW8HY-').is_visible()
            if pp_bl:
                break
        start_time = time.time()  # 获取开始时间
        while True:
            # 提取并打印每个 item 的 label 属性值
            brand_flag = False
            brand_strs = list(goods['brand'])
            brand_strs.insert(0, goods['brand'])
            brand_new = goods['brand'].replace('（', '(')
            brand_new = brand_new.split('(')[0] if '(' in brand_new else brand_new
            for index, brand_str in enumerate(brand_strs):
                # 输入品牌品牌 第一个是店铺地址全称
                if index == 1:
                    await page.locator('#rc_select_2').fill('')
                await page.locator('#rc_select_2').type(brand_str)
                await asyncio.sleep(0.5)
                # 等待页面加载并确保元素存在
                await page.wait_for_selector('.rc-virtual-list-holder-inner .ant-select-item')
                # 获取 rc-virtual-list-holder-inner 下的所有 ant-select-item
                items = await page.query_selector_all('.rc-virtual-list-holder-inner .ant-select-item')
                for item in items:
                    label_value = await item.get_attribute('label')
                    if goods['brand'] == label_value:
                        brand_flag = True
                        await item.click()
                        break
                if not brand_flag:
                    for item in items:
                        label_value = await item.get_attribute('label')
                        if brand_new in label_value:
                            brand_flag = True
                            await item.click()
                            break
                if brand_flag:
                    break
            if brand_flag:
                break
            current_time = time.time()  # 获取当前时间
            elapsed_time = current_time - start_time  # 计算已经过去的时间
            if elapsed_time > 10:  # 如果已经过去的时间超过5秒
                return  # 退出循环
        await video_is_upload(goods, page)
        try:
            await page.locator('.XwacrNGK2pY-').get_by_text('发布').click()
        except Exception as e:
            loguru.logger.error(f"{goods['goods_name']}上传快手发现上传出错了...{goods['id']}{e}")
        # 判断视频是否发布成功
        while True:
            # 判断视频是否发布成功
            try:
                await page.wait_for_url("https://cp.kuaishou.com/article/manage/video?status=2&from=publish",
                                        timeout=15000)  # 如果自动跳转到作品页面，则代表发布成功
                loguru.logger.info("  [-]{}视频发布成功".format(user_info['username']))
                db.execute(f"update video_goods_publish set state = 2 where id = {goods['id']}")
                if os.path.exists(goods['video_path']):
                    os.remove(goods['video_path'])
                break
            except Exception as e:
                loguru.logger.info(f"  [-] {user_info['username']}视频正在发布中...{e}")
                # await page.screenshot(full_page=True)

                await asyncio.sleep(0.5)
                await page.screenshot(path=f'imgs/{uuid.uuid4()}.png')
                # 查找按钮
                publish_button = page.locator('.XwacrNGK2pY-').get_by_text('发布')
                # 检查按钮是否存在
                await publish_button.click() if await publish_button.count() > 0 else None
        await context.storage_state(path=account_file)  # 保存cookie
        loguru.logger.info('  [-]cookie更新完毕！'.format(user_info['username']))
        await asyncio.sleep(2)  # 这里延迟是为了方便眼睛直观的观看
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()

    async def main(self):
        user_infos = db.fetchall("select * from user_info")
        for user_info in user_infos:
            try:
                # 根据视频生成记录发布视频
                good = db.fetchone(
                    f"select * from video_goods_publish vgp left join video_tools.video_goods vg on vgp.vg_id = vg.id where vgp.state=1 and vgp.user_id = {user_info['user_id']} limit 1")
                if datetime.now().hour in json.loads(user_info['publish_hours']) and good is not None:
                    account_file = get_account_file(user_info['user_id'])
                    async with async_playwright() as playwright:
                        await kuaishou_setup(account_file, handle=True)
                        await self.upload(playwright, good, user_info, account_file, '')
            except Exception as e:
                loguru.logger.error(e)


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
