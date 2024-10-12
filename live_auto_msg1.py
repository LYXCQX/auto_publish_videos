import ctypes
from pywinauto import Application, findwindows
import win32con
import win32gui

# Constants for window transparency
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x00000002

# 软件名称
soft_name = '快手直播伴侣'
# 输入框名称
input_name = '大家多多关注，谢谢你们~'
# 发送按钮名称
send_name = '发送'
# 互动消息名称，需要根据他 找父类然后找第二个GroupControl点击
hd_name = '互动消息'


def set_window_transparency(hwnd, transparency):
    """
    设置具有给定手柄的窗口的透明度。
    :param hwnd: 窗口的句柄
    :param transparency: 透明度级别（0-255，其中 0 表示完全透明，255 表示完全不透明）
    """
    # Add WS_EX_LAYERED style to the window
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                           win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) | WS_EX_LAYERED)

    # Set the transparency
    ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, transparency, LWA_ALPHA)


def auto_reply():
    # 查找窗口中的程序，如果有中文则需用Unicode;可用
    live_win = get_live_window()

    if not live_win:
        print('请先打开快速直播伴侣')
        return None

    # Get the HWND for the found window
    hwnd = live_win.handle
    if hwnd:
        print(f"窗口手柄 （HWND）: {hwnd}")
        # Set the window transparency to 128 (50% transparent)
        set_window_transparency(hwnd, 128)
        print("透明度设置为 128.")
    else:
        print("找不到窗口手柄.")
    return live_win


def send_msg(live_win):
    # 通过 pywinauto 获取输入框和发送按钮控件并进行操作
    input_box = live_win.child_window(title=input_name, control_type='Edit')
    send_button = live_win.child_window(title=send_name, control_type='Button')

    input_box.set_edit_text('Hello')
    send_button.click()


def get_live_window():
    live_win = None
    try:
        app = Application(backend='uia').connect(title_re='.*快手直播伴侣.*')
        live_win = app.window(title='快手直播伴侣')
        print('找到直播伴侣')
    except findwindows.ElementNotFoundError:
        print('找不到直播伴侣窗口')
    return live_win


def top_msg_window():
    live_win = get_live_window()
    if not live_win:
        print('请先打开快速直播伴侣')
        return

    # Find and click on the interaction message group control
    doc_control = live_win.child_window(title=soft_name, control_type='Pane')
    hd_control = doc_control.child_window(title=hd_name, control_type='Text')
    hd_control.click_input(double=True)  # Simulates a double-click if needed


if __name__ == '__main__':
    # 置顶消息窗口
    top_msg_window()
    # 将消息窗口透明化
    live_window = auto_reply()
    if live_window:
        while True:
            # 发送消息
            send_msg(live_window)
