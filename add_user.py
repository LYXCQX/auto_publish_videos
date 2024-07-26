import asyncio
import os
import sys
import threading
import time

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
EXPIRATION_TIME = 60


def cleanup_expired_entries():
    while True:
        time.sleep(60)  # Run cleanup every 60 seconds
        current_time = time.time()
        keys_to_delete = [key for key, value in qr_login.items() if current_time > value['expiry']]
        for key in keys_to_delete:
            del qr_login[key]
            try:
                qr_path = f'/opt/img/login/xhs_{key}.png'
                if os.path.exists(qr_path):
                    os.remove(qr_path)
            except:
                loguru.logger.info('删除二维码文件失败')
            loguru.logger.info(f"Deleted expired entry for UUID: {key}")


# Start the cleanup thread
cleanup_thread = threading.Thread(target=cleanup_expired_entries, daemon=True)
cleanup_thread.start()


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
            loguru.logger.info(f"request.remote_addr{request.remote_addr}")
            login_obj.user_id = request.remote_addr
            loguru.logger.info(f"user_id{login_obj.user_id}")
            await login_obj.begin()
            await crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)
            qr_login[request.remote_addr] = {
                'status': True,
                'expiry': time.time() + EXPIRATION_TIME
            }
        else:
            loguru.logger.info("xhs  cookie 有效，不需要再次获取")

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
    utils.logger.info(
        f"[XiaoHongShuLogin.login_by_qrcode] Login successful then wait for {wait_redirect_seconds} seconds redirect ...")
    await asyncio.sleep(wait_redirect_seconds)
    crawler.xhs_client.update_cookies(browser_context=crawler.browser_context)


def start_async_task(task):
    # 开始异步任务，但不等待其完成
    asyncio.create_task(task)


@app.route('/download')
def index():
    return render_template('add_user.html')


@app.route('/get_image')
def get_image():
    # Check if the image file exists for the given UUID
    image_path = "http://49.232.31.208/img/login/xhs_" + request.remote_addr + ".png"  # Assuming images are saved in 'static' folder
    res = jsonify({'success': True, 'imageUrl': f'{image_path}'})
    if request.remote_addr in qr_login and qr_login[request.remote_addr]['status']:
        res = jsonify({'success': True, 'msg': '登录成功'})
    return res


@app.route('/add_user')
def add_user():
    platform = 'xhs'
    lt = 'qrcode'
    asyncio.run(user_login(platform, lt))
    return jsonify({'success': True})


async def user_login(platform, lt):
    # init db
    if config.SAVE_DATA_OPTION == "db":
        await db.init_db()
    config.PLATFORM = platform
    config.LOGIN_TYPE = lt
    config.CRAWLER_TYPE = type
    crawler = CrawlerFactory.create_crawler(platform=platform)
    await add_user_login(crawler)
    if config.SAVE_DATA_OPTION == "db":
        await db.close()


if __name__ == '__main__':
    app.run(debug=True, port=6890)
