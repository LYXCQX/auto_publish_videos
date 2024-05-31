import asyncio
import os
import sys
import time
import uuid

from requests.exceptions import RetryError

from MediaCrawler.tools import utils

current_dir = os.path.dirname(os.path.abspath(__file__))
libs_path = os.path.join(current_dir, 'MediaCrawler', 'libs', 'stealth.min.js')
# 将 MediaCrawler 目录添加到 sys.path
media_crawler_path = os.path.join(current_dir, 'MediaCrawler')
sys.path.append(media_crawler_path)
print(libs_path)
from flask import Flask, render_template, jsonify, request
import loguru
from playwright.async_api import async_playwright
import MediaCrawler.db as db
from MediaCrawler import config
from MediaCrawler.main import CrawlerFactory
from MediaCrawler.media_platform.xhs.login import XiaoHongShuLogin
from MediaCrawler.proxy import IpInfoModel
from MediaCrawler.proxy.proxy_ip_pool import create_ip_pool
loguru.logger.add("error.log", format="{time} {level} {message}", level="ERROR")
loguru.logger.add("info.log", format="{time} {level} {message}", level="INFO")
app = Flask(__name__)
qr_login = {}

async def add_user_login(crawler) -> str:
    playwright_proxy_format, httpx_proxy_format = None, None
    if config.ENABLE_IP_PROXY:
        ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
        ip_proxy_info: IpInfoModel = await ip_proxy_pool.get_proxy()
        playwright_proxy_format, httpx_proxy_format = crawler.format_proxy_info(ip_proxy_info)

    async with async_playwright() as playwright:
        # Launch a browser context.
        chromium = playwright.chromium
        crawler.browser_context = await crawler.launch_browser(
            chromium,
            None,
            crawler.user_agent,
            headless=config.HEADLESS
        )
        # stealth.min.js is a js script to prevent the website from detecting the crawler.
        await crawler.browser_context.add_init_script(path=libs_path)
        # add a cookie attribute webId to avoid the appearance of a sliding captcha on the webpage
        await crawler.browser_context.add_cookies([{
            'name': "webId",
            'value': "xxx123",  # any value
            'domain': ".xiaohongshu.com",
            'path': "/"
        }])
        crawler.context_page = await crawler.browser_context.new_page()
        await crawler.context_page.goto(crawler.index_url)

        # Create a client to interact with the xiaohongshu website.
        crawler.xhs_client = await crawler.create_xhs_client(httpx_proxy_format)
        if not await crawler.xhs_client.pong():
            login_obj = XiaoHongShuLogin(
                login_type=crawler.login_type,
                login_phone="",  # input your phone number
                browser_context=crawler.browser_context,
                context_page=crawler.context_page,
                cookie_str=config.COOKIES
            )
            login_obj.need_wait = False
            await login_obj.begin()
            return login_obj.login_par

        loguru.logger.info("[XiaoHongShuCrawler.start] Xhs Crawler finished ...")


async def save_cookie(crawler):
    # get not logged session
    current_cookie = await crawler.browser_context.cookies()
    _, cookie_dict = utils.convert_cookies(current_cookie)
    no_logged_in_session = cookie_dict.get("web_session")
    utils.logger.info(f"[XiaoHongShuLogin.login_by_qrcode] waiting for scan code login, remaining time is 120s")
    try:
        await crawler.check_login_state(no_logged_in_session)
    except RetryError:
        utils.logger.info("[XiaoHongShuLogin.login_by_qrcode] Login xiaohongshu failed by qrcode login method ...")
        sys.exit()

    wait_redirect_seconds = 5
    utils.logger.info(f"[XiaoHongShuLogin.login_by_qrcode] Login successful then wait for {wait_redirect_seconds} seconds redirect ...")
    await asyncio.sleep(wait_redirect_seconds)
    crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)


def start_async_task(task):
    # 开始异步任务，但不等待其完成
    asyncio.create_task(task)


@app.route('/')
def index():
    return render_template('add_user.html')


@app.route('/add_user')
def add_user():
    platform = 'xhs'
    lt = 'qrcode'
    base64_image = asyncio.run(user_login(platform, lt))

    if base64_image:
        return jsonify({'success': True,'user_id': 'user_id', 'base64Image': base64_image})
    else:
        return jsonify({'success': False})


async def user_login(platform, lt):
    # init db
    if config.SAVE_DATA_OPTION == "db":
        await db.init_db()

    crawler = CrawlerFactory.create_crawler(platform=platform)
    crawler.init_config(
        platform=platform,
        login_type=lt,
        crawler_type='',
        keyword='',
        start_page=1
    )
    img = await add_user_login(crawler)
    qr_login[request.remote_addr] = crawler
    if config.SAVE_DATA_OPTION == "db":
        await db.close()
    return img

@app.route('/save_cookies', methods=['POST'])
def save_cookies():
    if qr_login[request.remote_addr]:
        asyncio.run(save_cookie(qr_login[request.remote_addr]))
    qr_logged_in = request.json.get('qrLoggedIn', False)
    if qr_logged_in:
        # Save cookies after QR code login
        # Example: crawler.save_cookies()
        # Store QR code login status in memory
        qr_login[request.remote_addr] = True  # Using client IP address as key
        return jsonify({'success': True})
    else:
        return jsonify({'success': False})
if __name__ == '__main__':
    app.run(debug=True)
