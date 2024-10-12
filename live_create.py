import os.path
import time
from typing import List

from model.model import VideoGoods
from util.audio_util import *
from util.ffmpeg_python_util import *
from util.file_util import *
from util.opencv_video_util import *
from video_dedup.config_parser import Config, read_dedup_config
from video_merge.datacls import VideoInfo
from video_merge.enums import Orientation, Rotation
from video_merge.main import merge_video
from video_merge.pipes import resize_video, rotation_video
from video_merge.utils import evenly_interpolate_numbers, evenly_distribute_numbers
from video_merge.video_info import get_video_info, get_most_compatible_resolution

config = read_dedup_config()


def process_dedup_by_config(config: Config, oral_text,audio_path_tmp):
    time0 = time.time()
    srt_path_tmp = get_temp_path('.srt')
    bgm_path_tmp = f'{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp3'
    input_video = ''
    ffmpeg_tmp = ''
    try:
        if audio_path_tmp is not None:
            if oral_text is not None:
                create_audio(oral_text.replace(" ", ""), audio_path_tmp, random.choice(config.role), config.rate, config.volume, srt_path_tmp)
            merged_audio = ffmpeg.input(audio_path_tmp)
            audio_duration = AudioSegment.from_file(audio_path_tmp).duration_seconds
            loguru.logger.info(f'音频时间{audio_duration}')
            max_sec = audio_duration if audio_duration > float(config.max_sec) else config.max_sec
            if config.live_bgm_audio_path != '':
                loguru.logger.info('config.live_bgm_audio_path -> ', config.live_bgm_audio_path)
                loop_audio_to_length(random.choice(config.live_bgm_audio_path), bgm_path_tmp, max_sec)
                bgm_audio = read_ffmpeg_audio_from_file(bgm_path_tmp)
                merged_audio = merge_and_adjust_volumes(merged_audio, bgm_audio, max_sec, 2.0, 0.1)
            # 按照配置合并视频
            input_video = merge_video(config, {"brand_base": "团油"}, max_sec, 'E:\团油\直播')
        if input_video is None:
            return

        width, height, origin_duration, bit_rate = video_properties(input_video)

        # 1. 先检测静默音频，并删除部分静默音频对应片段，获取到处理后的音频 & 视频
        video_stream, video_duration = remove_silent_video(input_video, origin_duration, config.silent_db,
                                                           config.silent_duration, config.silent_ratio)

        # 2. 视频镜像
        # if random.choice([True, False]):
        #     video_stream = mirror_video(video_stream)

        # 3. 视频旋转3度
        if config.reverse_angle > 0:
            video_stream = rotate_video(video_stream, config.reverse_angle)

        # 5. 裁剪视频
        if config.crop_size > 0:
            video_stream = crop_video(video_stream, width, height, config.crop_size)

        # 6. 添加文字 or 图片 or 视频水印
        # video_stream = add_watermark(video_stream, config, config.watermark_text,
        #                              watermark_type=config.watermark_type,
        #                              direction=config.watermark_direction, duration=video_duration)

        tt = time.time()
        loguru.logger.info('step1 cost time ', tt - time0)
        # 初步持久化
        final_video_path = f'{config.live_path}{int(time.time())}_{uuid.uuid4()}.mp4'
        save_stream_to_video(video_stream, merged_audio, final_video_path, bit_rate)
        time1 = time.time()
        loguru.logger.info('视频去重耗时: {}, 视频时长：{}'.format(time1 - time0, origin_duration))
    finally:
        if input_video:
            os.remove(input_video)
        if bgm_path_tmp and os.path.exists(bgm_path_tmp):
            os.remove(bgm_path_tmp)
        pass
    return final_video_path


# 处理视频功能
sample_rate: float = 0.5  # 该值表示从视频中采样的帧数占总帧数的比例
video_orientation: Orientation = Orientation.VERTICAL
horizontal_rotation: Rotation = Rotation.CLOCKWISE
vertical_rotation: Rotation = Rotation.CLOCKWISE


def loop_audio_to_length(audio_file_path, output_file_path , target_length_seconds=10):
    # 加载音频文件
    audio = AudioSegment.from_file(audio_file_path)

    # 获取音频长度（毫秒）
    audio_length_ms = len(audio)
    target_length_ms = target_length_seconds * 1000

    # 如果音频长度小于目标长度，则循环音频直到达到目标长度
    if audio_length_ms < target_length_ms:
        # 计算需要多少次循环才能达到目标长度
        loops = int(target_length_ms // audio_length_ms) + 1
        # 创建一个新的音频片段
        combined = audio * loops
        # 截取到目标长度
        combined = combined[:target_length_ms]
    else:
        # 如果音频长度已经足够长，直接使用原音频
        combined = audio[:target_length_ms]

    # 导出处理后的音频
    combined.export(output_file_path, format='mp3')
    print(f"原音频{audio_length_ms/1000}秒，需要{target_length_seconds}秒，音频已处理并保存为: {output_file_path}")


def merge_video(config: Config, good: VideoGoods, max_sec, video_paths):
    start_time: float = time.time()
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
        # is_distribute: bool = fps > config.fps
        # is_interpolate: bool = fps < config.fps
        # frame_index_list: list[int] = []

        # if is_interpolate:
        #     # frame_index_list = evenly_interpolate_numbers(fps, fps)
        #     frame_index_list = evenly_interpolate_numbers(total_frames, target_total_frames)
        #     loguru.logger.warning(f'视频拼接:视频帧率为{fps}, 目标帧率为{fps}, 采用平滑插帧')

        while True:
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
                output_video.write(frame)
            # 如果当前的 fps 小于目标 fps, 则需要重复一些帧
            # if is_interpolate:
            #     repeat_time = frame_index_list.count(current_frame_index)
            #     for _ in range(repeat_time):
            #         output_video.write(frame)
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


def save_stream_to_video(video_stream, audio_stream, output_path, target_bitrate=5000):
    loguru.logger.info(f'---{video_stream}---{audio_stream}---{output_path}')
    if audio_stream is None:
        stream = ffmpeg.output(video_stream, output_path, y='-y', vcodec='libx264', preset='medium',
                               crf=18, **{'b:v': str(target_bitrate) + 'k'}, shortest=None).global_args('-tag:v', 'hvc1')
    else:
        stream = ffmpeg.output(video_stream, audio_stream, output_path, y='-y', vcodec='libx264', preset='medium',
                               crf=18, **{'b:v': str(target_bitrate) + 'k'}, shortest=None).global_args('-tag:v', 'hvc1')
    ffmpeg.run(stream)


def get_mp4_files(folder_path):
    mp4_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".mp4"):
                path = os.path.join(root, file)
                mp4_files.append({"path": path, "file_name": file})
    return mp4_files


if __name__ == '__main__':
    audio_path = f'{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp3'
    process_dedup_by_config(config, None,audio_path)
