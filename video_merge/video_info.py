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
        last_sec += total_seconds
        loguru.logger.debug(f'当前时长 {total_seconds} 当前帧率{fps} 累计时长：{last_sec} 需要{max_sec}')
        if last_sec > float(max_sec):
            return video_info_list
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
