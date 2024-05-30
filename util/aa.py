import requests
import os
import shutil

def download_file(url, filename):
    try:
        # 发送 HTTP GET 请求获取文件数据
        response = requests.get(url, stream=True)

        # 检查响应状态码
        if response.status_code != 200:
            print(f"请求失败，状态码: {response.status_code}")
            return False

        # 保存文件到本地
        with open(filename, 'wb') as file:
            shutil.copyfileobj(response.raw, file)

        print(f"文件下载成功: {filename}")
        return True
    except Exception as e:
        print(f"下载失败 ({filename}): {e}")
        return False

# 示例用法
url = 'https:\\sns-video-hw.xhscdn.com\pre_post/1040g2t03138fm9ke00d05pbk0pcfdbp2uuajmp8'
filename = '111.mp4'
download_file(url, filename)
