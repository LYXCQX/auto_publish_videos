import functools
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from model.model import VideoGoods
from util.audio_util import *
from util.ffmpeg_python_util import *
from util.file_util import *
from util.opencv_video_util import *
from util.video_pingyu_util import process_frame
from video_dedup.config_parser import Config
from video_merge.main import merge_video


def process_dedup_by_config(config: Config, good: VideoGoods):
    time0 = time.time()
    audio_path_tmp = f'{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp3'
    srt_path_tmp = get_temp_path('.srt')
    opencv_tmp = ''
    output_video_tmp = ''
    input_video = ''
    try:
        goods_des = good['goods_des']
        create_audio(goods_des, audio_path_tmp, random.choice(config.role), config.rate, config.volume, srt_path_tmp)
        audio_stream = read_ffmpeg_audio_from_file(audio_path_tmp)
        merged_audio = AudioSegment.from_file(audio_path_tmp)
        audio_duration = AudioSegment.from_file(audio_path_tmp).duration_seconds
        config.max_sec = audio_duration if audio_duration > float(config.max_sec) else config.max_sec
        # 按照配置合并视频
        input_video = merge_video(config, good)

        width, height, origin_duration, bit_rate = video_properties(input_video)

        # 1. 先检测静默音频，并删除部分静默音频对应片段，获取到处理后的音频 & 视频
        video_stream, video_duration = remove_silent_video(input_video, origin_duration, config.silent_db,
                                                           config.silent_duration, config.silent_ratio)

        # 2. 视频镜像
        if random.choice([True, False]):
            video_stream = mirror_video(video_stream)

        # 3. 视频旋转3度
        if config.reverse_angle > 0:
            video_stream = rotate_video(video_stream, config.reverse_angle)

        # 4. 调整亮度(默认不变值0)、对比度（默认不变值1）、饱和度（默认不变值1）
        if config.enable_sbc:
            video_stream = adjust_video_properties(video_stream, saturation=config.saturation,
                                                   brightness=config.brightness,
                                                   contrast=config.contrast)

        # 5. 裁剪视频
        if config.crop_size > 0:
            video_stream = crop_video(video_stream, width, height, config.crop_size)

        # 6. 添加文字 or 图片 or 视频水印
        # if config.watermark_text != '':
        video_stream = add_watermark(video_stream, config, config.watermark_text,
                                     watermark_type=config.watermark_type,
                                     direction=config.watermark_direction, duration=video_duration)

        # bgm_path = '/Users/zhonghao/PycharmProjects/video_ai/demo/bgm_silient.m4a'
        if config.bgm_audio_path != '':
            loguru.logger.info('config.bgm_audio_path -> ', config.bgm_audio_path)
            bgm_audio = read_ffmpeg_audio_from_file(random.choice(config.bgm_audio_path))
            merged_audio = merge_and_adjust_volumes(audio_stream, bgm_audio, config)

        tt = time.time()
        loguru.logger.info('step1 cost time ', tt - time0)

        # 8. 添加字幕 -- 对于视频时长太短的小视频，不需要加字幕
        # audio_path_tmp = ''
        if origin_duration > config.srt_duration:
            # 先存储音频文件到本地
            # audio_path_tmp = get_temp_path('.mp3')
            # save_audio_stream(audio_stream, audio_path_tmp)
            # 依据音频调用模型得到结果
            # srt_result = whisper_model(audio_path_tmp)
            video_stream = add_subtitles(video_stream, srt_path_tmp, config)

        # 初步持久化
        output_video_tmp = get_temp_path('.mp4')
        save_stream_to_video(video_stream, merged_audio, output_video_tmp, bit_rate)

        # 解析同步后的新视频原数据
        audio_stream, video_stream = get_video_audio(output_video_tmp)
        width, height, duration, avg_bit_rate = video_properties(output_video_tmp)

        # 9. 虚化背景
        if random.choice([True, False]):
            video_stream = add_blurred_background(video_stream, output_video_tmp, width=width, height=height,
                                                  top_percent=random.choice([0, 1, 2]),
                                                  bottom_percent=random.choice([0, 1, 2]),
                                                  y_percent=random.choice([0, 1]))

        # 10. 添加title 和 description
        if good['top_sales_script'] != '':
            video_stream = add_title(video_stream, config, title=good['top_sales_script'],
                                     title_gap=config.top_title_gap, title_position='top')

        if good['sales_script'] != '':
            video_stream = add_title(video_stream, config, title=good['sales_script'],
                                     title_gap=config.bottom_title_gap, title_position='bottom')

        # 11. 视频淡入淡出
        if 0 < config.fadein_duration < duration:
            video_stream = fadein_video(video_stream, config.fadein_duration)

        if 0 < config.fadeout_duration < duration:
            video_stream = fadeout_video(video_stream, video_duration=duration, fade_duration=config.fadeout_duration)

        # ffmpeg处理结束
        ffmpeg_tmp = get_temp_path('.mp4')
        save_stream_to_video(video_stream, audio_stream, ffmpeg_tmp, bit_rate)
        time00 = time.time()
        loguru.logger.info('opencv前耗时', (time00 - time0))
        # 12. opencv随机进行高斯模糊
        opencv_tmp = get_temp_path('.mp4')
        video_capture = opencv_read_video_from_path(ffmpeg_tmp)
        frames = read_frames(video_capture)
        if random.choice([True, False]):
            frames = 每隔x帧随机选择一帧加随机模糊区域(frames, config.gauss_step, config.gauss_kernel,
                                                       config.gauss_area_size)

        if config.switch_frame_step > 0:
            frames = switch_frames_with_step(frames, step=config.switch_frame_step)

        if config.color_shift:
            frames = adjust_colors(frames)

        if config.add_hzh:
            frames = huazhonghua_by_config(frames, config.hzh_factor, config.hzh_video_path)

        # 创建一个带有默认参数的函数
        if config.enable_scrambling > 0 or config.enable_texture_syn or config.enable_edge_blur:
            partial_process_frame = functools.partial(process_frame, config=config)
            with ThreadPoolExecutor(max_workers=5) as executor:
                frames = list(executor.map(partial_process_frame, frames))

        # 先将frames生成得到静音的视频
        frames_to_video(frames, opencv_tmp)

        # ffmpeg读取静音视频，用于后续和音频进行合并
        silent_audio, silent_video = get_video_audio(opencv_tmp)
        # 合并音频和视频
        final_video_path = f'{config.save_path}{int(time.time())}_{uuid.uuid4()}.mp4'
        save_stream_to_video(silent_video, merged_audio, final_video_path, bit_rate)

        time1 = time.time()
        loguru.logger.info('视频去重耗时: {}, 视频时长：{}'.format(time1 - time0, origin_duration))
    finally:
        if srt_path_tmp != '':
            os.remove(srt_path_tmp)
        if audio_path_tmp != '':
            os.remove(audio_path_tmp)
        if opencv_tmp:
            os.remove(opencv_tmp)
        if output_video_tmp:
            os.remove(output_video_tmp)
        if input_video:
            os.remove(input_video)
        # if ffmpeg_tmp:
        #     os.remove(ffmpeg_tmp)
        pass
    return final_video_path


def get_mp4_files(folder_path):
    mp4_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".mp4"):
                path = os.path.join(root, file)
                mp4_files.append({"path": path, "file_name": file})
    return mp4_files


def frames_to_video_with_ffmpeg(frames, output_file, bit_rate):
    image_paths, temp_dir = save_frames_as_images(frames)
    images_to_video(image_paths, temp_dir, output_file, bit_rate)
    # 清理临时文件
    shutil.rmtree(temp_dir)
