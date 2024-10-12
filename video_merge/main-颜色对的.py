import os
import subprocess
import time
import uuid
from datetime import datetime
from typing import List

import cv2
import ffmpeg
import loguru

from model.model import VideoGoods
from util.file_util import get_mp4_files, get_mp4_files_path, get_mp4_by_goods_name, get_temp_path, delete_files
from video_dedup.config_parser import Config
from video_merge.datacls import VideoInfo
from video_merge.enums import Orientation, Rotation
from video_merge.pipes import rotation_video, resize_video
from video_merge.utils import evenly_distribute_numbers, evenly_interpolate_numbers
from video_merge.video_info import get_video_info, get_most_compatible_resolution

# 处理视频功能
sample_rate: float = 0.5  # 该值表示从视频中采样的帧数占总帧数的比例
video_orientation: Orientation = Orientation.VERTICAL
horizontal_rotation: Rotation = Rotation.CLOCKWISE
vertical_rotation: Rotation = Rotation.CLOCKWISE


def process_and_get_videos(config: Config, good: VideoGoods, max_sec, video_paths, is_bill):
    start_time: float = time.time()
    if is_bill:
        video_path_list = get_mp4_by_goods_name(good['video_path'], good['goods_name'])
    else:
        video_path_list = get_mp4_files_path(
            f"{good['video_path']}" if video_paths is None else video_paths)
    if len(video_path_list) < 1:
        loguru.logger.info("合并视频时没有合适的视频，请等待视频分割处理完成")
        return []
    video_info_list: List[VideoInfo] = get_video_info(video_path_list, max_sec)
    loguru.logger.info(f'视频拼接:获取视频信息完成,共计{len(video_info_list)}个视频:{video_info_list}')

    # 获取最佳分辨率
    loguru.logger.debug('视频拼接:正在获取最佳分辨率')
    if int(config.video_width) > 0 and int(config.video_height) > 0:
        best_width = int(config.video_width)
        best_height = int(config.video_height)
    else:
        best_width, best_height = get_most_compatible_resolution(video_info_list)

    loguru.logger.info(f'视频拼接:最佳分辨率为{best_width}x{best_height}')
    output_file_paths = []  # 用于存储输出文件路径的列表

    # 遍历每个视频信息进行处理
    for video_info in video_info_list:
        output_file_path = f"{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp4"  # 输出文件路径
        output_video = cv2.VideoWriter(output_file_path, cv2.VideoWriter.fourcc(*'mp4v'), int(config.fps),
                                       (best_width, best_height))  # 创建视频写入对象
        video = cv2.VideoCapture(str(video_info.video_path))
        fps = int(video.get(cv2.CAP_PROP_FPS))
        width = video.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = video.get(cv2.CAP_PROP_FRAME_HEIGHT)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        total_seconds = video_info.total_seconds
        target_total_frames = int(total_seconds * config.fps)
        current_frame_index = 0
        is_change =False
        fourcc = int(video.get(cv2.CAP_PROP_FOURCC))
        print(f'fourcc:{fourcc}')
        # 设置进度条
        loguru.logger.debug(f'正在拼接视频[{video_info.video_path}]')
        loguru.logger.debug(f'当前视频时长为{total_seconds}s, 目标视频时长为{target_total_frames / fps}s')

        # 平滑抽帧或者平滑插值
        is_distribute: bool = fps > config.fps
        is_interpolate: bool = fps < config.fps
        frame_index_list: list[int] = []

        # if is_distribute:
        #     frame_index_list = evenly_distribute_numbers(total_frames, target_total_frames)
        #     loguru.logger.warning(f'视频拼接:视频帧率为{fps}, 目标帧率为{fps}, 采用平滑抽帧')
        # el
        if total_frames < target_total_frames:
            # frame_index_list = evenly_interpolate_numbers(fps, fps)
            loguru.logger.warning(f'视频拼接:视频帧率为{total_frames}, 目标帧率为{target_total_frames}, 采用平滑插帧')
            frame_index_list = evenly_interpolate_numbers(total_frames, target_total_frames)

        while True:
            # 如果当前的 fps 大于目标 fps, 则需要continue跳过一些帧
            # if is_distribute and current_frame_index not in frame_index_list:
            #     current_frame_index += 1
            #     continue

            ret, frame = video.read()
            if not ret:
                break

            # 对视频进行旋转
            if (
                    video_orientation != Orientation.HORIZONTAL
                    or video_info.width <= video_info.height
            ) and (
                    video_orientation != Orientation.VERTICAL
                    or video_info.width >= video_info.height
            ):
                # 如果是横屏视频, 且宽度大于高度, 则需要旋转
                if video_orientation == Orientation.HORIZONTAL:
                    if horizontal_rotation == Rotation.NOTHING:
                        pass
                    elif horizontal_rotation == Rotation.CLOCKWISE:
                        frame = rotation_video(frame, 90)
                        is_change =True
                    elif horizontal_rotation == Rotation.COUNTERCLOCKWISE:
                        frame = rotation_video(frame, 270)
                        is_change =True
                    elif horizontal_rotation == Rotation.UPSIDE_DOWN:
                        frame = rotation_video(frame, 180)
                        is_change =True
                # 如果是竖屏视频, 且宽度小于高度, 则需要旋转
                elif video_orientation == Orientation.VERTICAL:
                    if vertical_rotation == Rotation.NOTHING:
                        pass
                    elif vertical_rotation == Rotation.CLOCKWISE:
                        frame = rotation_video(frame, 90)
                        is_change =True
                    elif vertical_rotation == Rotation.COUNTERCLOCKWISE:
                        frame = rotation_video(frame, 270)
                        is_change =True
                    elif vertical_rotation == Rotation.UPSIDE_DOWN:
                        frame = rotation_video(frame, 180)
                        is_change =True

            # 对视频进行缩放(如果视频的分辨率不是最佳分辨率)
            if width != best_width or height != best_height:
                frame = resize_video(frame, best_width, best_height)
                is_change =True

            # 如果当前的 fps 小于目标 fps, 则需要重复一些帧
            if is_interpolate:
                repeat_time = frame_index_list.count(current_frame_index)
                for _ in range(repeat_time):
                    is_change =True
                    output_video.write(frame)
            # 不需要补帧或者抽帧
            else:
                if is_change :
                    output_video.write(frame)

            current_frame_index += 1
        video.release()  # 释放视频读取对象
        output_video.release()  # 释放视频写入对象
        if is_change:
            output_file_paths.append(output_file_path)  # 添加输出路径到列表
        else:
            os.remove(output_file_path)
            output_file_paths.append(video_info.video_path)
        loguru.logger.debug(f'视频拼接:完成一个视频: {video_info.video_path}')

    loguru.logger.info(
        f'\n视频拼接:视频拼接完成, 输出文件为{output_file_paths}, 总共耗时[{time.time() - start_time:.2f}s]\n')
    return output_file_paths

def merge_video(config: Config, good: VideoGoods, max_sec, video_paths, is_bill):
    start_time: float = time.time()
    if is_bill:
        video_path_list = get_mp4_by_goods_name(good['video_path'], good['goods_name'])
    else:
        video_path_list = get_mp4_files_path(
            f"{good['video_path']}" if video_paths is None else video_paths)
    if len(video_path_list) < 1:
        loguru.logger.info("合并视频时没有合适的视频，请等待视频分割处理完成")
        return
    video_info_list: List[VideoInfo] = get_video_info(video_path_list, max_sec)
    loguru.logger.info(f'视频拼接:获取视频信息完成,共计{len(video_info_list)}个视频:{video_info_list}')

    # 获取最佳分辨率
    loguru.logger.debug('视频拼接:正在获取最佳分辨率')
    if int(config.video_width) > 0 and int(config.video_height) > 0:
        best_width = int(config.video_width)
        best_height = int(config.video_height)
    else:
        best_width, best_height = get_most_compatible_resolution(video_info_list)

    loguru.logger.info(f'视频拼接:最佳分辨率为{best_width}x{best_height}')
    output_file_path = f"{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp4"
    # 开始对视频依次执行[剪裁],[旋转],[缩放],[帧同步],[拼接]操作
    output_video = cv2.VideoWriter(output_file_path, cv2.VideoWriter.fourcc(*'mp4v'), int(config.fps),
                                   (best_width, best_height))
    for video_info in video_info_list:
        video = cv2.VideoCapture(str(video_info.video_path))
        fps = int(video.get(cv2.CAP_PROP_FPS))
        width = video.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = video.get(cv2.CAP_PROP_FRAME_HEIGHT)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        total_seconds = video_info.total_seconds
        target_total_frames = int(total_seconds * config.fps)
        current_frame_index = 0

        # 设置进度条
        loguru.logger.debug(f'正在拼接视频[{video_info.video_path}]')
        loguru.logger.debug(f'当前视频时长为{total_seconds}s, 目标视频时长为{target_total_frames / fps}s')

        # 平滑抽帧或者平滑插值
        is_distribute: bool = fps > config.fps
        is_interpolate: bool = fps < config.fps
        frame_index_list: list[int] = []

        # if is_distribute:
        #     frame_index_list = evenly_distribute_numbers(total_frames, target_total_frames)
        #     loguru.logger.warning(f'视频拼接:视频帧率为{fps}, 目标帧率为{fps}, 采用平滑抽帧')
        # el
        if total_frames < target_total_frames:
            # frame_index_list = evenly_interpolate_numbers(fps, fps)
            loguru.logger.warning(f'视频拼接:视频帧率为{total_frames}, 目标帧率为{target_total_frames}, 采用平滑插帧')
            frame_index_list = evenly_interpolate_numbers(total_frames, target_total_frames)

        while True:
            # 如果当前的 fps 大于目标 fps, 则需要continue跳过一些帧
            # if is_distribute and current_frame_index not in frame_index_list:
            #     current_frame_index += 1
            #     continue

            ret, frame = video.read()
            if not ret:
                break

            # 对视频进行旋转
            if (
                    video_orientation != Orientation.HORIZONTAL
                    or video_info.width <= video_info.height
            ) and (
                    video_orientation != Orientation.VERTICAL
                    or video_info.width >= video_info.height
            ):
                # 如果是横屏视频, 且宽度大于高度, 则需要旋转
                if video_orientation == Orientation.HORIZONTAL:
                    if horizontal_rotation == Rotation.NOTHING:
                        pass
                    elif horizontal_rotation == Rotation.CLOCKWISE:
                        frame = rotation_video(frame, 90)
                    elif horizontal_rotation == Rotation.COUNTERCLOCKWISE:
                        frame = rotation_video(frame, 270)
                    elif horizontal_rotation == Rotation.UPSIDE_DOWN:
                        frame = rotation_video(frame, 180)
                # 如果是竖屏视频, 且宽度小于高度, 则需要旋转
                elif video_orientation == Orientation.VERTICAL:
                    if vertical_rotation == Rotation.NOTHING:
                        pass
                    elif vertical_rotation == Rotation.CLOCKWISE:
                        frame = rotation_video(frame, 90)
                    elif vertical_rotation == Rotation.COUNTERCLOCKWISE:
                        frame = rotation_video(frame, 270)
                    elif vertical_rotation == Rotation.UPSIDE_DOWN:
                        frame = rotation_video(frame, 180)

            # 对视频进行缩放(如果视频的分辨率不是最佳分辨率)
            if width != best_width or height != best_height:
                frame = resize_video(frame, best_width, best_height)

            # 如果当前的 fps 小于目标 fps, 则需要重复一些帧
            if is_interpolate:
                repeat_time = frame_index_list.count(current_frame_index)
                for _ in range(repeat_time):
                    output_video.write(frame)
            # 不需要补帧或者抽帧
            else:
                output_video.write(frame)

            current_frame_index += 1
        video.release()
        loguru.logger.debug(f'视频拼接:完成一个视频: {video_info.video_path}')
    output_video.release()

    loguru.logger.info(
        f'\n视频拼接:视频拼接完成, 输出文件为[{output_file_path}], 总共耗时[{time.time() - start_time:.2f}s]\n')
    return output_file_path


def merge_video_direct(config: Config, good: VideoGoods, max_sec, video_paths, is_bill):
    start_time: float = time.time()
    video_info_list =process_and_get_videos(config,good,max_sec, video_paths, is_bill)
    loguru.logger.info(f'视频拼接:获取视频信息完成,共计{len(video_info_list)}个视频:{video_info_list}')
    output_file_path = f"{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp4"

    # 假设你的文件夹列表
    output_file_tmp = get_temp_path('.txt')
    # 创建一个文本文件，列出所有视频文件
    with open(output_file_tmp, 'w', encoding='utf-8') as f:
        for video in video_info_list:
            f.write(f"file '{os.path.abspath(video)}'\n")

    # 使用 ffmpeg 合并视频
    command = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', output_file_tmp,
        '-c:v', 'h264_nvenc',
        '-pix_fmt', 'yuv420p',
        '-preset', 'slow',
        '-b:v', '15M',  # 设定平均比特率
        '-maxrate', '20M',  # 最大比特率
        '-bufsize', '40M',  # 缓冲区大小
        output_file_path
    ]
    # command = [
    #     'ffmpeg', '-y',
    #     '-f', 'concat',
    #     '-safe', '0',
    #     '-i', output_file_tmp,
    #     '-c:v', 'libx264',
    #     '-pix_fmt', 'yuv420p',
    #     '-preset', 'slow',
    #     '-crf', '18',
    #     output_file_path
    # ]
    subprocess.run(command)
    # subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', output_file_tmp,
    #                 '-c:v', 'libx264', '-preset', 'fast', '-an', output_file_path])
    # 清理临时文件
    os.remove(output_file_tmp)
    delete_files(video_info_list)
    loguru.logger.info(
        f'\n视频拼接:视频拼接完成, 输出文件为[{output_file_path}], 总共耗时[{time.time() - start_time:.2f}s]\n')
    return output_file_path

def merge_video_direct1(config: Config, good: VideoGoods, max_sec, video_paths, is_bill):
    start_time: float = time.time()
    if is_bill:
        video_path_list = get_mp4_by_goods_name(good['video_path'], good['goods_name'])
    else:
        video_path_list = get_mp4_files_path(
            f"{good['video_path']}" if video_paths is None else video_paths)
    if len(video_path_list) < 1:
        loguru.logger.info("合并视频时没有合适的视频，请等待视频分割处理完成")
        return
    video_info_list: List[VideoInfo] = get_video_info(video_path_list, max_sec)
    loguru.logger.info(f'视频拼接:获取视频信息完成,共计{len(video_info_list)}个视频:{video_info_list}')
    output_file_path = f"{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp4"

    # 假设你的文件夹列表
    output_file_tmp = get_temp_path('.txt')
    # 创建一个文本文件，列出所有视频文件
    with open(output_file_tmp, 'w', encoding='utf-8') as f:
        for video in video_info_list:
            f.write(f"file '{os.path.abspath(video.video_path)}'\n")

    # 使用 ffmpeg 合并视频
    # subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'filelist.txt', '-c', 'copy', output_file_path])
    # subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', output_file_tmp,
    #                 '-c:v', 'libx264', '-c:a', 'aac', output_file_path])
    command = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', output_file_tmp,
        '-c:v', 'h264_nvenc',
        '-pix_fmt', 'yuv420p',
        '-preset', 'slow',
        '-crf', '18',
        '-c:a', 'aac',
        output_file_path
    ]
    subprocess.run(command)
    # subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', output_file_tmp,
    #                 '-c:v', 'libx264', '-preset', 'fast', '-an', output_file_path])
    # 清理临时文件
    os.remove(output_file_tmp)

    loguru.logger.info(
        f'\n视频拼接:视频拼接完成, 输出文件为[{output_file_path}], 总共耗时[{time.time() - start_time:.2f}s]\n')
    return output_file_path


# 直接拼接，避免色彩失真
# def merge_video_direct(config: Config, good: VideoGoods, max_sec, video_paths, is_bill):
#     if is_bill:
#         video_path_list = get_mp4_by_goods_name(good['video_path'], good['goods_name'])
#     else:
#         video_path_list = get_mp4_files_path(
#             f"{good['video_path']}" if video_paths is None else video_paths)
#
#     if len(video_path_list) < 1:
#         loguru.logger.info("合并视频时没有合适的视频，请等待视频分割处理完成")
#         return
#     output_file_path = f"{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp4"
#     video_info_list: List[VideoInfo] = get_video_info(video_path_list, max_sec)
#     loguru.logger.info(f'视频拼接:获取视频信息完成,共计{len(video_info_list)}个视频:{video_info_list}')
#     # 创建 file_list.txt
#     video_file_path = f"{config.video_temp}{int(time.time())}_{uuid.uuid4()}.txt"
#     with open(video_file_path, 'w', encoding='utf-8') as f:
#         for video in video_info_list:
#             f.write(f"file '{os.path.abspath(video.video_path)}'\n")
#     # 使用 FFmpeg 拼接视频
#     # os.system(f"ffmpeg -y  -f concat -safe 0 -i {video_file_path} -c copy {output_file_path}")
#     # os.system(f"ffmpeg -y -f concat -safe 0 -i {video_file_path} -c:v h264_nvenc -an {output_file_path}")
#     os.system(f"ffmpeg -y -f concat -safe 0 -i {video_file_path} -vf format=yuv420p -c:v h264_nvenc -an {output_file_path}")
#
#
#     # os.system(f"ffmpeg -y -f concat -safe 0 -i {video_file_path} -c:v h264_nvenc -preset fast -b:v 5M -c:a copy {output_file_path}")
#
#
#     # 删除 file_list.txt
#     if os.path.exists(video_file_path):
#         os.remove(video_file_path)
#     return output_file_path




if __name__ == '__main__':
    sourcePath = "D:/IDEA/workspace/auto_publish_videos//video/source//"
    # output_file_path = "D:/IDEA/workspace/\auto_publish_videos\\video\source\\1.mp4"
    fps = 30
    # best_width = 1280
    # best_height = 720
    merge_video(sourcePath, 10, fps)
