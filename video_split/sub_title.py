import cv2
import numpy as np

def detect_subtitle_area(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    kernel = np.ones((5, 5), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=1)
    eroded = cv2.erode(dilated, kernel, iterations=1)
    contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    subtitle_areas = []
    frame_height = frame.shape[0]

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > 50 and h > 10 and y > frame_height / 2:
            subtitle_areas.append((x, y, w, h))

    return subtitle_areas

def merge_subtitle_areas(areas):
    if not areas:
        return None

    areas = sorted(areas, key=lambda x: (x[1], x[0]))
    merged_area = areas[0]

    for current in areas:
        x1 = min(merged_area[0], current[0])
        y1 = min(merged_area[1], current[1])
        x2 = max(merged_area[0] + merged_area[2], current[0] + current[2])
        y2 = max(merged_area[1] + merged_area[3], current[1] + current[3])
        merged_area = (x1, y1, x2 - x1, y2 - y1)

    return merged_area

def crop_and_restore_video(video_path, output_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: 无法打开视频文件")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    subtitle_areas = []
    sample_interval = max(1, frame_count // 10)
    for i in range(0, frame_count, sample_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            break
        areas = detect_subtitle_area(frame)
        subtitle_areas.extend(areas)

    merged_area = merge_subtitle_areas(subtitle_areas)
    if merged_area is None:
        print("未能检测到字幕区域")
        return

    x, y, w, h = merged_area
    print(f"检测到的字幕区域: x={x}, y={y}, width={w}, height={h}")

    top = 0
    bottom = y
    left = 0
    right = frame_width

    bottom = min(y, frame_height)

    cropped_height = bottom - top
    cropped_width = right - left
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    for _ in range(frame_count):
        ret, frame = cap.read()
        if not ret:
            break

        cropped_frame = frame[top:bottom, left:right]

        mid_section = cropped_frame[cropped_height//4:3*cropped_height//4, :]
        top_padding = cv2.resize(mid_section, (cropped_width, cropped_height//2))
        bottom_padding = cv2.resize(mid_section, (cropped_width, frame_height - bottom - cropped_height//2))

        top_padding = cv2.GaussianBlur(top_padding, (25, 25), 0)
        bottom_padding = cv2.GaussianBlur(bottom_padding, (25, 25), 0)

        restored_frame = np.vstack((top_padding, cropped_frame, bottom_padding))

        out.write(restored_frame)

    cap.release()
    out.release()
    print(f"字幕已成功裁剪并恢复原尺寸，处理后的视频保存为 {output_path}")


# 示例调用
if __name__ == '__main__':
    video_path = "D:\IDEA\workspace\\auto_publish_videos\\video\download\\1.mp4"
    output_path = "D:\IDEA\workspace\\auto_publish_videos\\video\download\\2.mp4"
    crop_and_restore_video(video_path, output_path)