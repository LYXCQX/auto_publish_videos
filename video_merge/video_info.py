import random
from collections import Counter
from typing import List, Tuple

import cv2
import loguru

from video_merge.datacls import VideoInfo, CropInfo
from video_merge.enums import Orientation


def get_video_info(video_path_list, max_sec) -> List[VideoInfo]:
    video_info_list: List[VideoInfo] = []
    last_sec = 0
    video_count = len(video_path_list)
    video_indexes = []
    for _ in range(video_count):
        video_index = random_int_not_in_list(video_count, video_indexes)
        video_path = video_path_list[video_index]
        video_indexes.append(video_index)
        video = cv2.VideoCapture(video_path)
        fps = int(video.get(cv2.CAP_PROP_FPS))
        width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        total_seconds = total_frames / fps
        loguru.logger.debug(f'正在获取视频信息[{video_path}]')
        video_info_list.append(VideoInfo(video_path, fps, total_frames, width, height, total_seconds))
        if last_sec + total_seconds > float(max_sec):
            return video_info_list
        last_sec += total_seconds
        continue
        # # 先判断是否有黑边(获取视频中随机的10帧)
        # random_frames = random.sample(range(total_frames), 10 if total_frames > 10 else total_frames)
        # is_black = False
        # for i in random_frames:
        #     video.set(cv2.CAP_PROP_POS_FRAMES, i)
        #     ret, frame = video.read()
        #     if not ret:
        #         break
        # if not is_black:
        #     video_info_list.append(VideoInfo(video_path, fps, total_frames, width, height, total_seconds))
        #     video.release()
        #     continue
        #
        # # 如果有黑边则需要获取主体区域坐标(只获取部分百比分帧)
        # sample_frames = int(total_frames * sample_rate)
        # # 计算每次需要跳过的帧数
        # skip_frames = total_frames // sample_frames if sample_frames else 0
        #
        # coordinates = []
        # for i in range(0, total_frames, skip_frames):
        #     video.set(cv2.CAP_PROP_POS_FRAMES, i)
        #     ret, frame = video.read()
        #
        #     # 获取进度条增加的数量
        #     if not ret:
        #         break
        #     # Use BlackRemover to get the coordinates of the frame without black borders
        #
        # video.release()
        #
        # # Get the most common coordinates
        # most_common_coordinates = Counter(coordinates).most_common(1)[0][0]
        #
        # # 把坐标转化成x, y, w, h
        # most_common_coordinates = (
        #     most_common_coordinates[0],
        #     most_common_coordinates[1],
        #     most_common_coordinates[2] - most_common_coordinates[0],
        #     most_common_coordinates[3] - most_common_coordinates[1]
        # )
        #
        # x, y, w, h = most_common_coordinates
        #
        # # 如果视频是横向的，且宽度小于高度，或者视频是纵向的，且宽度大于高度，则交换宽高
        # if ((orientation == Orientation.HORIZONTAL and w < h)
        #         or (orientation == Orientation.VERTICAL and w > h)):
        #     most_common_coordinates = (x, y, h, w)
        # video_info_list.append(
        #     VideoInfo(video_path, fps, total_frames, width, height, total_seconds, CropInfo(*most_common_coordinates)))
    return video_info_list


def get_most_compatible_resolution(video_info_list: list[VideoInfo]) -> Tuple[int, int]:
    """获取最合适的视频分辨率"""
    resolutions: list[Tuple[int, int]] = []
    for each in video_info_list:
        if each.crop:
            resolutions.append((each.crop.w, each.crop.h))
            continue
        resolutions.append((each.width, each.height))

    aspect_ratios: list[float] = []
    for i in resolutions:
        aspect_ratios.append(i[0] / i[1])
    most_common_ratio = Counter(aspect_ratios).most_common(1)[0][0]
    compatible_resolutions = [res for res in resolutions if (res[0] / res[1]) == most_common_ratio]
    compatible_resolutions.sort(key=lambda x: (x[0] * x[1]), reverse=True)
    width, height = compatible_resolutions[0][:2]
    return width, height


def random_int_not_in_list(count, used):
    if len(used) >= count:
        return ''

    while True:
        random_int = random.randint(0, count - 1)  # 假设整数范围是0到100，根据需要修改范围
        if random_int not in used:
            return random_int
