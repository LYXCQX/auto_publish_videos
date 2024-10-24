import os
import subprocess
import json

import cv2


def get_video_rotation(video_path):
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=rotation', '-of', 'json', video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        info = json.loads(result.stdout)
        rotation = info.get('streams', [{}])[0].get('rotation', '0')
        return int(rotation)
    return 0

def is_wide_but_portrait(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    rotation = get_video_rotation(video_path)
    return width > height and rotation in [90, 270]  # 宽大于高且旋转90度或270度

def find_wide_portrait_videos(folder):
    wide_portrait_videos = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(('.mp4', '.mov', '.avi')):  # 根据需要添加更多格式
                full_path = os.path.join(root, file)
                if is_wide_but_portrait(full_path):
                    print(full_path)
                    wide_portrait_videos.append(full_path)
    return wide_portrait_videos

folder_path = 'E:\IDEA\workspace\\auto_publish_videos\\video\source\益禾堂'
videos = find_wide_portrait_videos(folder_path)
print(videos)
