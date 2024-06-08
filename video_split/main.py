import os
import time

import loguru

from merge import scheduled_job
from util.file_util import get_mp4_files_path
from video_split.PySceneDetect import split_video_into_scenes


def split_video(folder_path, source_path):
    video_files = get_mp4_files_path(folder_path)
    loguru.logger.info(f"分割视频需要处理的数据有{len(video_files)}条")
    last_time = time.time()
    for video_path in video_files:
        video_folder = os.path.dirname(video_path)
        output_folder = os.path.join(source_path, video_folder.replace(folder_path, ''))
        split_video_into_scenes(video_path, output_folder)
        # 每次运行完校验一下上次的运行时间，如果超过半个小时，则看一下有没有需要合并的数据
        if last_time - time.time() > 1800:
            scheduled_job()
            last_time = time.time()


if __name__ == '__main__':
    # remove_audio("D:/IDEA/workspace//auto_publish_videos//video/download",
    #              "D:/IDEA/workspace//auto_publish_videos//video/source//")
    split_video("D:/IDEA/workspace/auto_publish_videos/video/download/",
                "D:/IDEA/workspace/auto_publish_videos/video/source/")
    # split_video("D:\IDEA\workspace\\auto_publish_videos\\video\source\\tes")
