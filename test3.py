import time
from obswebsocket import obsws, requests  # 导入必要的库

# OBS WebSocket 设置
host = '192.168.31.249'
port = 4455  # 默认端口
password = 'leyuan521'  # 如果设置了密码，请替换

# 创建一个 OBS WebSocket 客户端
ws = obsws(host, port, password)

try:
    ws.connect()  # 连接到 OBS

    # 启用麦克风音频源
    # 请替换 '你的音频源名称' 为你在 OBS 中的实际麦克风音频源名称
    # ws.call(requests.SetMute('麦克风/Aux', False))  # 取消静音
    ws.call(requests.SetVolume('苏小谷-音频', 50))  # 将音量设置为 50%
    # ws.call(requests.SetVolume('苏小谷-背景音乐', 50))  # 将音量设置为 50%
    # 等待一段时间播放音频（可根据需要调整）
    # time.sleep(10)  # 播放 10 秒

    # 停止麦克风音频源
    # ws.call(requests.SetMute('你的音频源名称', True))  # 静音

finally:
    ws.disconnect()  # 确保断开连接
