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

import itertools
import math
import os
import platform
import random
import re
import subprocess

from PIL import Image

from util.file_util import generate_temp_filename, get_temp_path
from video_dedup.config_parser import Config
from video_dedup.texiao_service import gen_filter

work_output_dir = os.path.abspath('video/temp/')
if platform.system() == "Windows":
    # work目录
    work_output_dir = os.path.abspath('video/temp/').replace("\\", "/")

DEFAULT_DURATION = 5


def get_audio_duration(audio_file):
    """
    获取音频文件的时长（秒）
    :param audio_file: 音频文件路径
    :return: 音频时长（秒），如果失败则返回None
    """
    # 使用ffmpeg命令获取音频信息
    cmd = ['ffmpeg', '-i', audio_file]
    print(" ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, encoding='utf-8')

    # 解析输出，找到时长信息
    duration_search = re.search(
        r'Duration: (?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+)\.(?P<milliseconds>\d+)',
        result.stderr.decode('utf-8'))
    if duration_search:
        hours = int(duration_search.group('hours'))
        minutes = int(duration_search.group('minutes'))
        seconds = int(duration_search.group('seconds'))
        total_seconds = hours * 3600 + minutes * 60 + seconds
        print("音频时长:", total_seconds)
        return total_seconds
    else:
        print(f"无法从输出中获取音频时长: {result.stderr.decode('utf-8')}")
        return None


def get_video_fps(video_path):
    # ffprobe 命令，用于获取视频的帧率
    ffprobe_cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    print(" ".join(ffprobe_cmd))

    try:
        # 运行 ffprobe 命令并捕获输出
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, encoding='utf-8')

        # 检查命令是否成功执行
        if result.returncode != 0:
            print(f"Error running ffprobe: {result.stderr}")
            return None

        # 解析输出以获取帧率
        output = result.stdout.strip()
        if '/' in output:
            numerator, denominator = map(int, output.split('/'))
            fps = float(numerator) / float(denominator)
        else:
            fps = float(output)
        print("视频fps:", fps)
        return fps
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_video_info(video_file):
    command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of',
               'default=noprint_wrappers=1:nokey=1', video_file]
    print(" ".join(command))
    result = subprocess.run(command, capture_output=True)

    # 解析输出以获取宽度和高度
    output = result.stdout.decode('utf-8')
    # print("output is:",output)
    width_height = output.split('\n')
    width = int(width_height[0])
    height = int(width_height[1])

    print(f'Width: {width}, Height: {height}')
    return width, height


def get_image_info(image_file):
    # 打开图片
    img = Image.open(image_file)
    # 获取图片的宽度和高度
    width, height = img.size
    print(f'Width: {width}, Height: {height}')
    return width, height


def get_video_duration(video_file):
    # 构建FFmpeg命令来获取视频时长
    command = ['ffprobe', '-i', video_file, '-show_entries', 'format=duration']
    # 执行命令并捕获输出
    print(" ".join(command))
    result = subprocess.run(command, capture_output=True)
    output = result.stdout.decode('utf-8')

    # 使用正则表达式从输出中提取时长
    duration_match = re.search(r'duration=(\d+\.\d+)', output)
    if duration_match:
        duration = float(duration_match.group(1))
        print("视频时长:", duration)
        return duration
    else:
        print(f"无法从输出中提取视频时长: {output}")
        return None


def get_video_length_list(video_list):
    video_length_list = []
    for video_file in video_list:
        length = get_video_duration(video_file)
        video_length_list.append(length)
    return video_length_list


def add_music(video_file, audio_file, max_sec):
    output_file = generate_temp_filename(video_file, new_directory=work_output_dir)
    # 构造ffmpeg命令
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', video_file,  # 输入视频文件
        '-i', audio_file,  # 输入音频文件
        '-c:v', 'copy',  # 复制视频流编码
        '-c:a', 'aac',  # 使用AAC编码音频流
        '-strict', 'experimental',  # 有时可能需要这个选项来启用AAC编码
        '-map', '0:v:0',  # 选择第一个输入文件的视频流
        '-map', '1:a:0',  # 选择第二个输入文件的音频流
        # '-shortest',
        '-t', str(max_sec),
        '-y',
        output_file  # 输出文件路径
    ]
    print(" ".join(ffmpeg_cmd))
    subprocess.run(ffmpeg_cmd, capture_output=True, text=True, encoding='utf-8')
    # 重命名最终的文件
    if os.path.exists(output_file):
        os.remove(video_file)
        os.renames(output_file, video_file)


def add_background_music(video_file, audio_file, max_sec, bgm_volume=0.5):
    output_file = generate_temp_filename(video_file, new_directory=work_output_dir)
    # 构建FFmpeg命令
    command = [
        'ffmpeg',
        '-i', video_file,  # 输入视频文件
        '-i', audio_file,  # 输入音频文件（背景音乐）
        '-filter_complex',
        f"[1:a]aloop=loop=0:size=100M[bgm];[bgm]volume={bgm_volume}[bgm_vol];[0:a][bgm_vol]amix=duration=first:dropout_transition=3:inputs=2[a]",
        # 在[1:a]之后添加了aloop过滤器来循环背景音乐。loop=0表示无限循环，size=200M和duration=300是可选参数，用于设置循环音频的大小或时长（这里设置得很大以确保足够长，可以根据实际需要调整），start=0表示从音频的开始处循环。
        '-map', '0:v',  # 选择视频流
        '-map', '[a]',  # 选择混合后的音频流
        '-c:v', 'copy',  # 复制视频流
        # '-shortest',  # 输出时长与最短的输入流相同
        '-t', str(max_sec),  # 设置输出文件时长为视频时长
        output_file  # 输出文件
    ]
    # 调用FFmpeg命令
    print(command)
    subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    # 重命名最终的文件
    if os.path.exists(output_file):
        os.remove(video_file)
        os.renames(output_file, video_file)


class VideoService:
    def __init__(self, video_list, audio_file, max_sec, config: Config):
        self.config = config
        self.video_list = video_list
        self.audio_file = audio_file
        self.fps = config.fps
        self.seg_min_duration = 0
        self.segment_max_length = max_sec
        self.target_width = int(config.video_width)
        self.target_height = int(config.video_height)

        self.enable_background_music = config.bgm_audio_path != ''
        self.background_music_volume = 0.3

        self.enable_video_transition_effect = True
        self.video_transition_effect_duration = '1'
        self.video_transition_effect_type = 'xfade'
        self.video_transition_effect_value = 'fade'
        self.default_duration = DEFAULT_DURATION
        if DEFAULT_DURATION < self.seg_min_duration:
            self.default_duration = self.seg_min_duration

    def normalize_video(self):
        return_video_list = []
        random.shuffle(self.video_list)
        total_sec = 0
        for video_inf in self.video_list:
            apply_flip = random.choice(['', 'hflip,'])  # 随机选择是否镜像
            media_file = video_inf.replace('\\', '/')
            # 如果当前文件是图片，添加转换为视频的命令
            if media_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                output_name = generate_temp_filename(media_file, ".mp4", work_output_dir)
                # 判断图片的纵横比和
                img_width, img_height = get_image_info(media_file)
                if img_width / img_height > self.target_width / self.target_height:
                    # 转换图片为视频片段 图片的视频帧率必须要跟视频的帧率一样，否则可能在最后的合并过程中导致 合并过后的视频过长
                    # ffmpeg_cmd = f"ffmpeg -loop 1 -i '{media_file}' -c:v h264 -t {self.default_duration} -r {self.fps} -vf 'scale=-1:{self.target_height}:force_original_aspect_ratio=1,crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2' -y {output_name}"
                    ffmpeg_cmd = [
                        'ffmpeg',
                        '-loop', '1',
                        '-i', media_file,
                        '-c:v', 'h264',
                        '-t', str(self.default_duration),
                        '-r', str(self.fps),
                        '-vf',
                        f'scale=-1:{self.target_height}:force_original_aspect_ratio=1,{apply_flip}crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2',
                        '-y', output_name]
                else:
                    # ffmpeg_cmd = f"ffmpeg -loop 1 -i '{media_file}' -c:v h264 -t {self.default_duration} -r {self.fps} -vf 'scale={self.target_width}:-1:force_original_aspect_ratio=1,crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2' -y {output_name}"
                    ffmpeg_cmd = [
                        'ffmpeg',
                        '-loop', '1',
                        '-i', media_file,
                        '-c:v', 'h264',
                        '-t', str(self.default_duration),
                        '-r', str(self.fps),
                        '-vf',
                        f'scale={self.target_width}:-1:force_original_aspect_ratio=1,{apply_flip}crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2',
                        '-y', output_name]
                print(" ".join(ffmpeg_cmd))
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True, encoding='utf-8')
                return_video_list.append(output_name)
                total_sec += self.default_duration
            else:
                # 当前文件是视频文件
                video_duration = get_video_duration(media_file)
                video_width, video_height = get_video_info(media_file)
                output_name = generate_temp_filename(media_file, new_directory=work_output_dir)
                if self.seg_min_duration > video_duration:
                    # 需要扩展视频
                    stretch_factor = float(self.seg_min_duration) / float(video_duration)  # 拉长比例
                    # 构建FFmpeg命令
                    if video_width / video_height > self.target_width / self.target_height:
                        command = [
                            'ffmpeg',
                            '-i', media_file,  # 输入文件
                            '-r', str(self.fps),  # 设置帧率
                            '-an',  # 去除音频
                            '-vf',
                            f"setpts={stretch_factor}*PTS,scale=-1:{self.target_height}:force_original_aspect_ratio=1,{apply_flip}crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2",
                            # 调整时间戳滤镜
                            # '-vf', f'scale=-1:{self.target_height}:force_original_aspect_ratio=1',  # 设置视频滤镜来调整分辨率
                            # '-vf', f'crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2',
                            # '-af', f'atempo={1 / stretch_factor}',  # 调整音频速度以匹配视频
                            '-y',
                            output_name  # 输出文件
                        ]
                    else:
                        command = [
                            'ffmpeg',
                            '-i', media_file,  # 输入文件
                            '-r', str(self.fps),  # 设置帧率
                            '-an',  # 去除音频
                            '-vf',
                            f"setpts={stretch_factor}*PTS,scale={self.target_width}:-1:force_original_aspect_ratio=1,{apply_flip}crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2",
                            # 调整时间戳滤镜
                            # '-vf', f'scale={self.target_width}:-1:force_original_aspect_ratio=1',  # 设置视频滤镜来调整分辨率
                            # '-vf', f'crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2',
                            # '-af', f'atempo={1 / stretch_factor}',  # 调整音频速度以匹配视频
                            '-y',
                            output_name  # 输出文件
                        ]
                    # 执行FFmpeg命令
                    print(" ".join(command))
                    run_ffmpeg_command(command)
                else:
                    # 不需要拉伸也不需要裁剪，只需要调整分辨率和fps
                    if video_width / video_height > self.target_width / self.target_height:
                        command = [
                            'ffmpeg',
                            '-i', media_file,  # 输入文件
                            '-r', str(self.fps),  # 设置帧率
                            '-an',  # 去除音频
                            '-vf',
                            f"scale=-1:{self.target_height}:force_original_aspect_ratio=1,{apply_flip}crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2",
                            # 设置视频滤镜来调整分辨率
                            # '-vf', f'crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2',
                            '-y',
                            output_name  # 输出文件
                        ]
                    else:
                        command = [
                            'ffmpeg',
                            '-i', media_file,  # 输入文件
                            '-r', str(self.fps),  # 设置帧率
                            '-an',  # 去除音频
                            '-vf',
                            f"scale={self.target_width}:-1:force_original_aspect_ratio=1,{apply_flip}crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2",
                            # 设置视频滤镜来调整分辨率
                            # '-vf', f'crop={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2',
                            '-y',
                            output_name  # 输出文件
                        ]
                    # 执行FFmpeg命令
                    print(" ".join(command))
                    run_ffmpeg_command(command)
                # 重命名最终的文件
                # if os.path.exists(output_name):
                #     os.remove(media_file)
                #     os.renames(output_name, media_file)
                return_video_list.append(output_name)
                new_video_duration = get_video_duration(output_name)
                if self.enable_video_transition_effect and len(self.video_list) > 1:
                    new_video_duration -= int(self.video_transition_effect_duration)
                total_sec += new_video_duration
            print(
                f'一共需要{self.segment_max_length} ，目前一共 {total_sec} ，当前视频b{video_duration} e{new_video_duration}')
            if total_sec >= self.segment_max_length:
                break
        self.video_list = return_video_list
        return return_video_list

    def generate_video_with_audio(self):
        # 生成视频和音频的代码
        # random_name = str(random_with_system_time())
        merge_video = get_temp_path('.mp4')
        temp_video_filelist_path = get_temp_path('.txt')

        # 创建包含所有视频文件的文本文件
        with open(temp_video_filelist_path, 'w', encoding='utf-8') as f:
            for video_file in self.video_list:
                f.write(f"file '{video_file}'\n")
        angle_radians = math.radians(self.config.reverse_angle)
        # 拼接视频
        ffmpeg_concat_cmd = ['ffmpeg',
                             '-f', 'concat',
                             '-safe', '0',
                             '-i', temp_video_filelist_path,
                             # '-c', 'copy',
                             '-vf',
                             f"rotate={angle_radians}",
                             '-fflags',
                             '+genpts',
                             '-y',
                             merge_video]

        # 是否需要转场特效
        if self.enable_video_transition_effect and len(self.video_list) > 1:
            video_length_list = get_video_length_list(self.video_list)
            print("启动转场特效")
            zhuanchang_txt = gen_filter(video_length_list, None, None,
                                        self.video_transition_effect_type,
                                        self.video_transition_effect_value,
                                        self.video_transition_effect_duration,
                                        self.config,
                                        False)

            # File inputs from the list
            files_input = [['-i', f] for f in self.video_list]
            ffmpeg_concat_cmd = ['ffmpeg', *itertools.chain(*files_input),
                                 '-filter_complex', zhuanchang_txt,
                                 '-map', '[video]',
                                 # '-map', '[audio]',
                                 '-y',
                                 merge_video]
        print(" ".join(ffmpeg_concat_cmd))
        subprocess.run(ffmpeg_concat_cmd, encoding='utf-8')
        # 删除临时文件
        os.remove(temp_video_filelist_path)

        # 拼接音频
        add_music(merge_video, self.audio_file, self.segment_max_length)

        # 添加背景音乐
        if self.enable_background_music:
            add_background_music(merge_video, random.choice(self.config.bgm_audio_path), self.segment_max_length,
                                 self.background_music_volume)
        for tmp_video in self.video_list:
            if os.path.exists(tmp_video):
                os.remove(tmp_video)
        return merge_video


def run_ffmpeg_command(command):
    try:
        result = subprocess.run(command, capture_output=True, check=True, text=True, encoding='utf-8')
        if result.returncode != 0:
            print(f"FFmpeg returned an error: {result.stderr}")
        else:
            print("Command executed successfully.")
    except Exception as e:
        print(f"An error occurred while execute ffmpeg command {e}")


def extent_audio(audio_file, pad_dur=2):
    temp_file = generate_temp_filename(audio_file, new_directory=work_output_dir)
    # 构造ffmpeg命令
    command = [
        'ffmpeg',
        '-i', audio_file,
        '-af', f'apad=pad_dur={pad_dur}',
        temp_file
    ]
    # 执行命令
    subprocess.run(command, capture_output=True, check=True, encoding='utf-8')
    # 重命名最终的文件
    if os.path.exists(temp_file):
        os.remove(audio_file)
        os.renames(temp_file, audio_file)
