import os
import shutil

from pypinyin import pinyin, Style


def chinese_to_pinyin(chinese_str):
    """
    将中文字符串转换为拼音，返回拼音列表
    """
    return pinyin(chinese_str, style=Style.NORMAL)


def rename_files_to_pinyin(folder_path):
    """
    将文件夹中所有文件的中文名重命名为拼音名称
    """
    for filename in os.listdir(folder_path):
        old_filepath = os.path.join(folder_path, filename)

        if os.path.isdir(old_filepath):
            # 如果是文件夹，递归处理
            rename_files_to_pinyin(old_filepath)
        elif os.path.isfile(old_filepath):
            # 如果是文件，处理文件名
            new_filename = ''.join([word[0] for word in chinese_to_pinyin(filename)])
            new_filepath = os.path.join(folder_path, new_filename)
            os.rename(old_filepath, new_filepath)
            print(f'Renamed "{filename}" to "{new_filename}"')


if __name__ == '__main__':
    folder_path = 'D:\IDEA\workspace\\auto_publish_videos\\font'  # 替换为你的文件夹路径
    rename_files_to_pinyin(folder_path)


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

# source_folder = r'C:\Users\41525\AppData\Local\JianyingPro\User Data\Cache\effect'
# target_folder = r'D:\IDEA\workspace\auto_publish_videos\font'
# # 定义常见字体文件扩展名
# font_extensions = ['.ttf', '.otf', '.woff', '.woff2']
#
# copy_fonts(source_folder, target_folder, font_extensions)
