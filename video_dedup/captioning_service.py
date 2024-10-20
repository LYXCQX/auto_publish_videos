#  Copyright © [2024] 程序那些事
#
#  All rights reserved. This software and associated documentation files (the "Software") are provided for personal and educational use only. Commercial use of the Software is strictly prohibited unless explicit permission is obtained from the author.
#
#  Permission is hereby granted to any person to use, copy, and modify the Software for non-commercial purposes, provided that the following conditions are met:
#
#  1. The original copyright notice and this permission notice must be included in all copies or substantial portions of the Software.
#  2. Modifications, if any, must retain the original copyright information and must not imply that the modified version is an official version of the Software.
#  3. Any distribution of the Software or its modifications must retain the original copyright notice and include this permission notice.
#
#  For commercial use, including but not limited to selling, distributing, or using the Software as part of any commercial product or service, you must obtain explicit authorization from the author.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHOR OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
#  Author: 程序那些事
#  email: flydean@163.com
#  Website: [www.flydean.com](http://www.flydean.com)
#  GitHub: [https://github.com/ddean2009/MoneyPrinterPlus](https://github.com/ddean2009/MoneyPrinterPlus)
#
#  All rights reserved.
#
#

import os
import platform
import random
import subprocess

from util.ffmpeg_python_util import get_font_file, random_color
from util.file_util import generate_temp_filename
from video_dedup.config_parser import Config


# 添加字幕
def add_subtitles(video_file, subtitle_file,config:Config,margin_l=4, margin_r=4, spacing=2):
    font_file = get_font_file(config)
    output_file = generate_temp_filename(video_file)
    # windows路径需要特殊处理
    if platform.system() == "Windows":
        subtitle_file = subtitle_file.replace("\\", "\\\\\\\\")
        subtitle_file = subtitle_file.replace(":", "\\\\:")
    vf_text = (f"subtitles={subtitle_file}:fontsdir={os.path.dirname(font_file)}:force_style='Fontname={os.path.basename(font_file)}"
               f",Fontsize={config.font_size},Alignment=2,MarginV={config.MarginV},MarginL={margin_l},MarginR={margin_r},"
               f"BorderStyle={config.BorderStyle},Outline={random.randint(0, 3)},Shadow={random.randint(1, 3)},PrimaryColour={random_color()},OutlineColour={config.border_color_code},"
               f"Underline={int(config.underline)},BackColour={random_color()},Spacing={spacing}'")
    # 构建FFmpeg命令
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', video_file,  # 输入视频文件
        '-vf', vf_text,  # 输入字幕文件
        '-y',
        output_file  # 输出文件
    ]
    print(" ".join(ffmpeg_cmd))
    # 调用ffmpeg
    subprocess.run(ffmpeg_cmd, check=True, encoding='utf-8')
    # 重命名最终的文件
    if os.path.exists(output_file):
        os.remove(video_file)
        os.renames(output_file, video_file)