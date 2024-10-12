import os
import subprocess
from datetime import datetime


def reencode_videos(folder_path):
    cutoff_date = datetime(2024, 10, 7)
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(('.mp4', '.mkv', '.avi')):  # 可根据需要添加格式

                try:
                    input_file = os.path.join(root, file)
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(input_file))

                    # Check if the file modification date is before the cutoff date
                    if file_mod_time < cutoff_date:
                        temp_file = os.path.join(root, 'temp_' + file)  # 创建临时文件
                        command = [
                            'ffmpeg', '-y',
                            '-i', input_file,
                            '-c:v', 'h264_nvenc',
                            '-pix_fmt', 'yuv420p',
                            '-preset', 'slow',
                            temp_file
                        ]
                        subprocess.run(command)

                        # 替换原文件
                        os.replace(temp_file, input_file)
                        print(f"重新编码: {input_file}")
                except:
                    if os.path.exists(input_file):
                        os.remove(input_file)
                    pass

            # 删除临时文件
            # if os.path.exists(temp_file):
            #     os.remove(temp_file)


# 使用示例
reencode_videos('E:\IDEA\workspace\\auto_publish_videos\\video\source')
