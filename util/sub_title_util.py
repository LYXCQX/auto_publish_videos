import os
import random
import shutil
import subprocess

import cv2
import numpy as np
from paddleocr import PaddleOCR
import whisper
# os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


def has_audio(video_path):
    """检查视频是否有音频"""
    command = f'ffprobe -i "{video_path}" -show_streams -select_streams a -loglevel error'
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return bool(result.stdout.strip())


def get_ocr_result(video_path, segment_start_time=None):
    """获取OCR结果，如果有音频则从最长字幕段落获取，否则随机选取10帧"""
    ocr = PaddleOCR(use_angle_cls=True, lang='ch')
    video_capture = cv2.VideoCapture(video_path)
    ocr_result = []
    try:
        if segment_start_time:
            video_capture.set(cv2.CAP_PROP_POS_MSEC, segment_start_time * 1000)
            success, frame = video_capture.read()
            if success:
                ocr_result = ocr.ocr(frame)
        else:
            video_length = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            for _ in range(10):
                random_frame = random.randint(0, video_length - 1)
                video_capture.set(cv2.CAP_PROP_POS_FRAMES, random_frame)
                success, frame = video_capture.read()
                if success:
                    ocr_result = ocr.ocr(frame)
                    if ocr_result:
                        break
            else:
                ocr_result = []
    finally:
        video_capture.release()
    return frame if ocr_result else None, ocr_result


def get_subtitle_areas(ocr_result, frame_height, padding):
    """获取字幕区域"""
    subtitle_areas = []
    for line in ocr_result:
        if line is not None:
            for word in line:
                bbox = word[0]
                _, y1 = map(int, bbox[0])
                _, y2 = map(int, bbox[2])
                y1 = max(0, y1 - padding)
                y2 = min(frame_height, y2 + padding)
                subtitle_areas.append((y1, y2))
    subtitle_areas.sort()
    return subtitle_areas


def get_non_subtitle_areas(subtitle_areas, frame_height):
    """获取非字幕区域"""
    non_subtitle_areas = []
    last_y = 0
    for (y1, y2) in subtitle_areas:
        if last_y < y1:
            non_subtitle_areas.append((last_y, y1))
        last_y = y2
    if last_y < frame_height:
        non_subtitle_areas.append((last_y, frame_height))
    return non_subtitle_areas


def apply_blur_to_frame(frame, largest_non_subtitle_area):
    """对最大无字幕区域进行模糊处理并居中显示"""
    y1, y2 = largest_non_subtitle_area
    height = y2 - y1
    center_y = frame.shape[0] // 2
    start_y = center_y - height // 2

    non_subtitle_frame = frame[y1:y2, :]
    frame_blurred = cv2.GaussianBlur(frame, (51, 51), 0)
    frame_blurred[start_y:start_y + height, :] = non_subtitle_frame
    return frame_blurred


def patch_match_inpainting(frame, ocr_result, mask, padding):
    """PatchMatch填充的实现"""
    height, width = frame.shape[:2]

    for line in ocr_result:
        if line is not None:
            for word in line:
                bbox = word[0]
                x1, y1 = int(bbox[0][0]), int(bbox[0][1])
                x2, y2 = int(bbox[2][0]), int(bbox[2][1])

                # 扩展字幕区域并确保在边界内
                x1 = np.clip(x1 - padding, 0, width)
                y1 = np.clip(y1 - padding, 0, height)
                x2 = np.clip(x2 + padding, 0, width)
                y2 = np.clip(y2 + padding, 0, height)

                mask[y1:y2, x1:x2] = 255

    # 使用 PatchMatch 算法进行修复
    unpainted_frame = cv2.inpaint(frame, mask, 3, cv2.INPAINT_NS)
    return unpainted_frame


def apply_texture_fill(frame, ocr_result, mask, padding):
    """使用纹理填充字幕区域"""
    for (y1, y2) in get_subtitle_areas(ocr_result, frame.shape[0], padding):
        mask[y1:y2, :] = 255

    dst = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
    for line in ocr_result:
        if line is not None:
            for word in line:
                bbox = word[0]
                _, y1 = map(int, bbox[0])
                _, y2 = map(int, bbox[2])
                y1 = max(0, y1 - padding)
                y2 = min(frame.shape[0], y2 + padding)
                height = y2 - y1

                patch = None
                if y1 > height and is_non_subtitle_region(mask, 0, y1 - height, frame.shape[1], y1):
                    patch = frame[y1 - height:y1, :]
                elif y2 + height < frame.shape[0] and is_non_subtitle_region(mask, 0, y2, frame.shape[1], y2 + height):
                    patch = frame[y2:y2 + height, :]

                if patch is not None and patch.shape[1] == frame.shape[1] and patch.shape[0] == height:
                    dst[y1:y2, :] = patch

    return dst


def is_non_subtitle_region(mask, x1, y1, x2, y2):
    """判断区域是否为非字幕区域"""
    region = mask[y1:y2, x1:x2]
    return np.mean(region) == 0


def fill_subtitles(frame, ocr_result, model):
    """填充字幕区域"""
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    padding = 10

    subtitle_areas = get_subtitle_areas(ocr_result, frame.shape[0], padding)
    if not subtitle_areas:
        return frame

    non_subtitle_areas = get_non_subtitle_areas(subtitle_areas, frame.shape[0])
    largest_non_subtitle_area = max(non_subtitle_areas, key=lambda area: area[1] - area[0])
    non_subtitle_ratio = (largest_non_subtitle_area[1] - largest_non_subtitle_area[0]) / frame.shape[0]

    if non_subtitle_ratio < 0.2:
        print("最大的无字幕区域小于20%，删除视频。")
        os.remove(input_video_path)
        return
    elif non_subtitle_ratio < 0.3:
        return apply_blur_to_frame(frame, largest_non_subtitle_area)
    else:
        if model == 'texture':
            return apply_texture_fill(frame, ocr_result, mask, padding)
        else:
            return patch_match_inpainting(frame, ocr_result, mask, padding)


def process_video(input_video_path, output_video_path, model):
    # 确保目标文件夹存在，如果不存在则创建它
    os.makedirs(os.path.dirname(output_video_path), exist_ok=True)
    """处理视频"""
    if has_audio(input_video_path):
        print("视频有音频。使用 Whisper 检测最长的字幕段落。")

        def get_longest_segment(audio_path):
            model = whisper.load_model("base")
            result = model.transcribe(audio_path)
            if not result['segments']:
                return None
            longest_segment = max(result['segments'], key=lambda x: x['end'] - x['start'])
            return longest_segment

        longest_segment = get_longest_segment(input_video_path)
        segment_start_time = random.uniform(longest_segment['start'], longest_segment['end'])
        frame, ocr_result = get_ocr_result(input_video_path, max(0, segment_start_time - 0.05))
    else:
        print("视频没有音频。随机选择帧以检测字幕。")
        for _ in range(10):
            frame, ocr_result = get_ocr_result(input_video_path)
            if ocr_result:
                break

    if not ocr_result:
        print("在采样的帧中未检测到字幕。直接移动文件")
        # 移动视频文件
        shutil.move(input_video_path, output_video_path)
        return

    video_capture = cv2.VideoCapture(input_video_path)
    fps = video_capture.get(cv2.CAP_PROP_FPS)
    width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
    try:
        frame_count = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
        for i in range(1, frame_count):  # 跳过第一帧
            success, frame = video_capture.read()
            if not success:
                break

            frame = fill_subtitles(frame, ocr_result, model)
            video_writer.write(frame)
    finally:
        video_capture.release()
        video_writer.release()

    print("处理完成，输出视频路径：", output_video_path)


if __name__ == '__main__':
    input_video_path = 'D:/IDEA/workspace/auto_publish_videos/video/download/aa/9.mp4'
    output_video_path = 'D:/IDEA/workspace/auto_publish_videos/video/download/aa/10.mp4'

    process_video(input_video_path, output_video_path, 'patchmatch')
