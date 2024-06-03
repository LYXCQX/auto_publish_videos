import os
import shutil

def copy_fonts(source_folder, target_folder, font_extensions):
    # 确保目标文件夹存在
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    # 遍历源文件夹及其子文件夹
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            # 检查文件扩展名
            if file.lower().endswith(tuple(font_extensions)):
                # 构建文件的完整路径
                source_file = os.path.join(root, file)
                # 复制文件到目标文件夹
                shutil.copy(source_file, target_folder)


source_folder = r'C:\Users\41525\AppData\Local\JianyingPro\User Data\Cache\effect'
target_folder = r'D:\IDEA\workspace\auto_publish_videos\font'
# 定义常见字体文件扩展名
font_extensions = ['.ttf', '.otf', '.woff', '.woff2']

copy_fonts(source_folder, target_folder, font_extensions)
