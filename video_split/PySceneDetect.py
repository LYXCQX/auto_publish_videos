import os
import subprocess
from pathlib import Path

from scenedetect import split_video_ffmpeg, detect, open_video, SceneManager
from scenedetect.detectors import ContentDetector


def split_video_into_scenes(video_path, output_path, threshold=27.0):
    # 打开我们的视频，创建场景管理器，并添加检测器.
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video, show_progress=True)
    scene_list = scene_manager.get_scene_list(start_in_scene=True)
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    if len(scene_list) > 1:
        split_video_ffmpeg(video_path, scene_list, output_path, '$VIDEO_NAME-$SCENE_NUMBER.mp4',
                           # arg_override='-map 0:v -c:v h264_nvenc -pix_fmt yuv420p -preset slow',
                           show_progress=True)
    else:
        # 获取文件名，不包括扩展名
        file_name = Path(video_path).stem
        split_ml = f'ffmpeg -i {video_path} -c:v copy -c:a copy -reset_timestamps 1  -segment_time 5 -f segment "{output_path}/{file_name}-%03d.mp4"'
        # split_ml = f'ffmpeg -i {video_path} -c copy -pix_fmt yuv420p -reset_timestamps 1 -segment_time 5 -f segment "{output_path}/{file_name}-%03d.mp4"'
        # split_ml = f'ffmpeg -i {video_path} -c:v h264_nvenc -pix_fmt yuv420p -preset slow  -c:a copy -reset_timestamps 1 -segment_time 5 -f segment "{output_path}/{file_name}-%03d.mp4"'
        # 执行命令
        try:
            subprocess.run(split_ml, shell=True, check=True, encoding='utf-8')
            print("命令执行成功")
        except subprocess.CalledProcessError as e:
            print("命令执行失败:", e)
    # scene_list = detect(video_path, ContentDetector())
    # split_video_ffmpeg(video_path, scene_list, output_path)


if __name__ == '__main__':
    split_video_into_scenes("D:\system\Downloads\\1.mp4",
                            "E:\团油\团油\\2分钟")
