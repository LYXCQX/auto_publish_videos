import ctypes
import os
import queue
import random
import threading
import time
import uuid

import loguru
import requests
import uiautomation as auto
import win32con
import win32gui
from playwright.sync_api import sync_playwright

from util.audio_util import audio_to_microphone
from util.file_util import get_live_account_file
from video_dedup.config_parser import read_dedup_config

config = read_dedup_config()
current_dir = os.path.dirname(os.path.abspath(__file__))
libs_path = os.path.join(current_dir, 'MediaCrawler', 'libs', 'stealth.min.js')
# Constants for window transparency
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x00000002
# 软件名称
soft_name = '\u5feb\u624b\u76f4\u64ad\u4f34\u4fa3'
# 输入框名称
input_name = '\u5927\u5bb6\u591a\u591a\u70b9\u5173\u6ce8\uff0c\u8c22\u8c22\u4f60\u4eec\u007e'
# 发送按钮名称
send_name = '\u53d1\u9001'
# 互动消息名称，需要根据他 找父类然后找第二个GroupControl点击
hd_name = '\u4e92\u52a8\u6d88\u606f'
# 用户随机消息
ms_list = [
    # '全国都有加油站，点击下边的小团子，它是按照距离排序的，上边的都是离您最近的呢',
    '1号链接是我们的开播福利，大家可以看一下哟', '宝子们，有任何问题都可以打到公屏上，主播会为您解答',
    '直播间的宝子们，有条件的可以帮主播点点关注，感谢',
    '售后有任何问题及时联系主播',
    '宝子，位置问题您可以点开下方链接有具体位置哦',
    # '使用请您在快手团购后台-出示二维码在油站核销',
    '心动不如行动，快下单吧',
    # '：关于洗车，开发票的问题，您需要咨询油站',
    '主播回复不及时，请您谅解。',
    '关于商品有任何问题都可以咨询主播哟。',
    # '宝子们，我们的代金券全国可用哦',
    # '使用请您在快手团购后台-出示二维码在油站核销',
    '欢迎新进直播间的宝子们，可以给主播点个小关小注，加主播粉丝团，开播有提醒的哟']
zn_msg_list = ['宝子们，有任何问题都可以打到公屏上，主播会为您解答', '直播间的宝子们，有条件的可以帮主播点点关注，感谢',
               '直播间的宝子们，有条件的可以帮主播点点关注，感谢'
    , '欢迎新进直播间的宝子们，可以给主播点个小关小注，加主播粉丝团，开播有提醒的哟']
login_user = ['乐乐团购:', '乐乐团购', '小汐团购:']
# 是否监听
is_monitor = True
last_time = time.time()
send_time = 5
replay_configs = {'加入直播间': f'欢迎 %s 加入直播间',
                  '加入，': f'欢迎 %s 加入直播间',
                  '关注了你': f'感谢 %s 的关注，非常感谢宝子的支持',
                  '个新粉丝，记得感谢': f'感谢 %s 的关注，非常感谢宝子的支持',
                  '已观看5分钟': f'热烈感谢宝子 %s 的支持',
                  '已观看10分钟': f'热烈感谢宝子 %s 的支持',
                  '已观看15分钟': f'热烈感谢宝子 %s 的支持',
                  '已观看20分钟': f'热烈感谢宝子 %s 的支持',
                  '点亮爱心': f'感谢宝子 %s 点亮的爱心，非常感谢宝子的支持',
                  '早上好': f'%s 早上好，有条件帮主播点个关注，非常感谢',
                  '上午好': f'%s 上午好，有条件帮主播点个关注，非常感谢',
                  '中午好': f'%s 中午好，有条件帮主播点个关注，非常感谢',
                  '下午好': f'%s 下午好，有条件帮主播点个关注，非常感谢',
                  '晚上好': f'%s 晚上好，有条件帮主播点个关注，非常感谢',
                  '你好': f'%s 你好，感谢你的支持',
                  '分享了直播': f'%s 感谢宝子的分享，非常感谢宝子的支持',
                  }
goods_explains = [1, 2]
goods_explain_id = 1
# 1固定id 2.随机id 3.随机配置id
goods_explains_type = 2
msg_queue = queue.Queue()
goods_explain_second = 3 * 60
# 消息回复方式 web网页，win使用客户端,audio是语音回复
msg_type = 'web'


def set_window_transparency(hwnd, transparency):
    """
   设置具有给定手柄的窗口的透明度。
    :p aram hwnd： 窗口的句柄
    :p aram 透明度：透明度级别（0-255，其中 0 表示完全透明，255 表示完全不透明）"""
    # Add WS_EX_LAYERED style to the window
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                           win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) | WS_EX_LAYERED)

    # Set the transparency
    ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, transparency, LWA_ALPHA)


# 透明窗口
def auto_reply():
    # 查找窗口中的程序，如果有中文则需用Unicode;可用
    time.sleep(5)
    live_win, doc_control, hd_control = get_live_window(1)
    if not live_win:
        auto.Logger.WriteLine('请先打开快手直播伴侣', auto.ConsoleColor.Yellow)
        return
    # doc_control = live_win.DocumentControl(searchDepth=2, Name=soft_name)
    # hd_control = doc_control.TextControl(searchDepth=8, Name=hd_name)
    pl_control = hd_control.GetParentControl().GetParentControl().GroupControl(searchDepth=1,
                                                                               foundIndex=4).GroupControl(
        searchDepth=1, foundIndex=1).GroupControl(searchDepth=1, foundIndex=4)
    pl_val = doc_control.EditControl(searchDepth=8, Name=input_name)
    send_but = doc_control.TextControl(searchDepth=9, Name=send_name)
    # Get the HWND for the found window
    hwnd = win32gui.FindWindow(None, live_win.Name)
    if hwnd:
        auto.Logger.WriteLine(f"窗口手柄 （HWND）: {hwnd}")
        # Set the window transparency to 128 (50% transparent)
        set_window_transparency(hwnd, 128)
        auto.Logger.WriteLine("透明度设置为 128.")
    else:
        auto.Logger.WriteLine("找不到窗口手柄.")
    return live_win, pl_control, pl_val, send_but, hwnd


# 发送消息
def send_msg(msg):
    if msg_type == 'audio' and msg not in ms_list:
        audio_to_microphone(tts(msg))
    elif msg_type == 'win':
        loguru.logger.info(f'使用win发送消息{msg}')
        # pl_value.GetValuePattern().SetValue(msg)
        pl_value.SendKeys(msg)
        # send_button.Click()
        # send_button.SetFocus()
        send_button.SendKeys('{Enter}')
    else:
        loguru.logger.info(f'使用web发送消息{msg}')
        msg_queue.put(msg)
    global last_time
    last_time = time.time()


def tts(word):
    # 设置请求的URL
    url = "http://127.0.0.1:9880/"

    # 定义要发送的参数
    params = {
        'refer_wav_path': r"E:\GPT-SoVITS\ckyp\奶绿完整版\LAPLACE\感谢我的奶糖花兄弟让有事没趣的我有了参与感下次线下一定去。.wav",  # 参考WAV文件路径
        'prompt_text': '谢谢，老公老公我爱你，哎还没缓过劲儿啊？',  # 提示文本
        'prompt_language': '中文',  # 提示语言
        'text': word,  # 要发送的文本
        'text_language': '中文',  # 文本语言
        'cut_punc': '按标点符号切',  # 切分标点符号的方式
        'top_k': 15,  # top-k采样
        'top_p': 1,  # top-p采样
        'temperature': 1,  # 温度参数
        'speed': 1  # 语速参数
    }

    # 发送POST请求
    response = requests.get(url, params=params, headers={'accept': 'application/json'})
    res_audio_path = f'{config.video_temp}/live/{uuid.uuid4()}.wav'
    # 检查响应是否为音频内容
    if response.headers['Content-Type'] == 'audio/wav':
        # 将返回的内容保存为WAV文件
        with open(res_audio_path, 'wb') as f:
            f.write(response.content)  # 写入音频内容
        print(f"音频已保存为 {res_audio_path}")
        return res_audio_path



# 这里result返回的是gptsovits输出的音频文件路径地址，之后可以通过读取这个地址的文件来播放音频
def get_live_window(win_type):
    doc_control = None
    hd_control = None
    live_win = None
    for win in auto.GetRootControl().GetChildren():
        if win.Name == '快手直播伴侣':
            if win_type == 1:
                for c, d in auto.WalkControl(win, maxDepth=10):
                    if c.Name == '互动消息':
                        doc_control = win.DocumentControl(searchDepth=2, Name=soft_name)
                        hd_control = doc_control.TextControl(searchDepth=8, Name=hd_name)
                        live_win = win
                        break
            else:
                auto.Logger.WriteLine('找到直播伴侣')
                live_win = win
            break
    return live_win, doc_control, hd_control


# 置顶消息窗口
def top_msg_window():
    live_win, doc_control, hd_control = get_live_window(0)
    if not live_win:
        auto.Logger.WriteLine('请先打开快速直播伴侣', auto.ConsoleColor.Yellow)
    doc_control = live_win.DocumentControl(searchDepth=2, Name=soft_name)
    hd_control = doc_control.TextControl(searchDepth=8, Name=hd_name)
    gn_controls = hd_control.GetParentControl().GroupControl(foundIndex=2)
    gn_controls.Click()


def add_msg(user_name, now_msg):
    global send_time
    user_msgs = msg_list.get(user_name)
    user_msgs = [] if user_msgs is None else user_msgs
    if time.time() - last_time > send_time:
        auto.Logger.WriteLine(last_time)
        auto.Logger.WriteLine(time.time())
        auto.Logger.WriteLine(last_time - time.time())
        time_msg = random.choice(ms_list)
        auto.Logger.WriteLine(f'超过{send_time} 秒 未发送消息自动发送一条:{time_msg}')
        send_msg(time_msg)
        send_time = random.randint(60, 120)
    if now_msg not in user_msgs and user_name not in login_user and user_name != '快手平台账号: ':
        auto.Logger.WriteLine(f'收到消息{now_msg}')
        user_msgs.append(now_msg)
        msg = None
        # 遍历字典的每一个键值对
        for key, template in replay_configs.items():
            # 如果当前消息包含某个键
            if key in now_msg:
                # 使用模板并将占位符替换为 user_name
                msg = template % (user_name.replace('User_', '').replace('快手用户', '').replace(':', ''))
                break
        # 如果没有匹配的模板，则从备用消息列表中随机选择一条
        if msg is None:
            msg = random.choice(ms_list)

        msg_list[user_name] = user_msgs
        send_msg(msg)


# 监听并处理消息
def monitor_process_msg(pl_cont):
    last_len = 0;
    while is_monitor:
        try:
            pl_controls = pl_cont.GetChildren()
            for index, pl_control in enumerate(pl_controls):
                msgs = pl_control.GetChildren()
                if index == 0:
                    continue
                if len(msgs) > 1:
                    user_name = pl_control.TextControl(foundIndex=1).Name
                    # auto.Logger.WriteLine(user_name)
                    now_msg = pl_control.TextControl(foundIndex=2).Name
                    # auto.Logger.WriteLine(now_msg)
                    add_msg(user_name, now_msg)
                last_len = len(pl_controls)
            set_window_transparency(hwnd, 128)
        except Exception as e:
            auto.Logger.WriteLine(e)
            pass
        # # 发送消息
        # send_msg(live_window)


def init_list(pl_cont):
    pl_controls = pl_cont.GetChildren()
    for index, pl_control in enumerate(pl_controls):
        msgs = pl_control.GetChildren()
        if index == 0:
            continue
        if len(msgs) > 1:
            user_name = pl_control.TextControl(foundIndex=1).Name
            now_msg = pl_control.TextControl(foundIndex=2).Name
            auto.Logger.WriteLine(f'初始化数据--{user_name}----{now_msg}')
            user_msgs = msg_list.get(user_name)
            user_msgs = [] if user_msgs is None else user_msgs
            if user_name not in login_user and user_name != '快手平台账号: ':
                user_msgs.append(now_msg)
                msg_list[user_name] = user_msgs


def live_manage(account_file) -> None:
    with sync_playwright() as playwright:
        # 使用 Chromium 浏览器启动一个浏览器实例
        browser = playwright.chromium.launch(headless=False)
        if os.path.exists(account_file):
            # 创建一个浏览器上下文，使用指定的 cookie 文件
            context = browser.new_context(storage_state=f"{account_file}")
        else:
            context = browser.new_context()
        context.add_init_script(path=libs_path)
        # 创建一个新的页面
        page = context.new_page()
        # 访问指定的 URL
        page.goto("https://lbs.kuaishou.com/sandslash/login")
        page.wait_for_url("https://lbs.kuaishou.com/sandslash/login")
        while True:
            if page.url == 'https://lbs.kuaishou.com/sandslash/login':
                loguru.logger.info('等待扫码登录')
                if page.get_by_text('达人账号登录').count() > 0:
                    page.get_by_text('达人账号登录').click()
            elif page.url == 'https://lbs.kuaishou.com/sandslash/live/liveInfo':
                page.get_by_text('跟播助手').click()
                context.storage_state(path=account_file)
                break
            elif page.url == 'https://lbs.kuaishou.com/sandslash/live/liveHepler':
                loguru.logger.info('等待扫码登录')
                context.storage_state(path=account_file)
                break
        start_time = time.time()
        goods_explain_time = time.time()
        while True:
            try:
                if time.time() - start_time > 600:
                    start_time = time.time()
                    page.reload()
                # 等待元素加载
                page.wait_for_selector('.ks-main iframe')  # 等待包含iframe的元素加载
                # 获取class为ks-main下的iframe
                frame_element = page.query_selector('.ks-main iframe')
                # 等待iframe加载
                frame = frame_element.content_frame()
                if msg_type == 'web':
                    comment_list_selector = '.live-helper-comment-list'
                    comment_item_selector = '.live-helper-comment-list-item'
                    # 获取所有评论项
                    comment_items = frame.query_selector_all(comment_list_selector + ' ' + comment_item_selector)

                    for item in comment_items:
                        # 获取用户名和内容
                        username = item.query_selector('.live-helper-comment-username')
                        content = item.query_selector('.live-helper-comment-content')

                        # 检查是否包含 class "is-me"
                        if 'is-me' in username.get_attribute('class').split():
                            continue  # 跳过这条消息
                        # 提取文本
                        username_text = username.inner_text() if username else ''
                        content_text = content.inner_text() if content else ''
                        print(f'用户: {username_text}, 内容: {content_text}')
                        add_msg(username_text, content_text)
                # else:
                while not msg_queue.empty():
                    msg = msg_queue.get()
                    while True:
                        print(msg)
                        send_button_class = '.live-helper-comment-input-wrap button'
                        is_enabled = frame.query_selector(send_button_class).is_enabled()
                        if not is_enabled:
                            frame.type('#rc_select_0', msg, delay=100)  # 每个字符延迟100毫秒
                            frame.click(send_button_class)
                            break

                if time.time() > goods_explain_time + goods_explain_second:
                    # 等待 good-item 元素加载
                    frame.wait_for_selector('.scroll-wrapper .good-item')

                    # 获取所有 good-item 元素
                    good_items = frame.query_selector_all('.scroll-wrapper .good-item')
                    # 遍历每个 good-item
                    if goods_explains_type == 1:
                        explain_id = goods_explain_id
                    elif goods_explains_type == 2:
                        explain_id = random.randint(1, len(good_items))
                    elif goods_explains_type == 3:
                        explain_id = random.choice(goods_explains)
                    item = good_items[explain_id]
                    if item and 'ant-btn-primary' not in (item.get_attribute('class')).split():
                        jj_button = item.query_selector('.ant-btn')
                        if jj_button:
                            jj_button.click()
                            loguru.logger.info(f'点击了第{explain_id}个商品讲解')
                            goods_explain_time = time.time()
                time.sleep(10)
            except Exception as e:
                loguru.logger.error(f'直播管理发生异常{e}')
        # 关闭浏览器上下文和浏览器实例
        context.close()
        browser.close()


if __name__ == '__main__':
    account_file = get_live_account_file('4142857862')
    tt = threading.Thread(target=live_manage, args=(account_file,), daemon=True)
    tt.start()
    msg_list = {}
    # 置顶消息窗口
    top_msg_window()
    # 将消息窗口透明化
    live_window, pl_con, pl_value, send_button, hwnd = auto_reply()
    # 初始化聊天室互动消息
    init_list(pl_con)
    # if len(msg_list) == 0:
    #     auto.Logger.WriteLine(f'没有数据发送一条')
    #     send_msg(random.choice(ms_list))
    # 监听并处理消息
    # if msg_type == 'win':
    monitor_process_msg(pl_con)
    tt.join()
