import os.path
import shutil

from model.model import VideoGoods
from util.audio_util import *
from util.ffmpeg_python_util import *
from util.file_util import *
from util.opencv_video_util import *
from video_dedup.config_parser import Config
from video_dedup.video_service import VideoService


def process_dedup_by_config(config: Config, good: VideoGoods, goods_des, is_bill):
    time0 = time.time()
    audio_path_tmp = f'{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp3'
    srt_path_tmp = get_temp_path('.srt')
    opencv_tmp = ''
    input_video = ''
    try:
        create_audio(goods_des.replace(" ", ""), audio_path_tmp, random.choice(config.role), config.rate, config.volume,
                     srt_path_tmp)
        audio_duration = AudioSegment.from_file(audio_path_tmp).duration_seconds
        loguru.logger.info(f'音频时间{audio_duration}')
        max_sec = audio_duration if audio_duration > float(config.max_sec) else config.max_sec

        if is_bill:
            video_path_list = get_mp4_by_goods_name(good['video_path'], good['goods_name'])
        else:
            video_path_list = get_mp4_files_path(f"{good['video_path']}")
        if len(video_path_list) < 1:
            loguru.logger.info("合并视频时没有合适的视频，请等待视频分割处理完成")
            return
        # video_info_list: List[VideoInfo] = get_video_info(video_path_list, max_sec)
        # loguru.logger.info(f'视频拼接:获取视频信息完成,共计{len(video_info_list)}个视频:{video_info_list}')
        video_service = VideoService(video_path_list, audio_path_tmp, max_sec, config)
        print("normalize video")
        video_service.normalize_video()
        video_file = video_service.generate_video_with_audio()

        # 解析同步后的新视频原数据
        audio_stream, video_stream = get_video_audio(video_file)
        width, height, duration, bit_rate = video_properties(video_file)
        is_xh = random.choice([False])

        img_y = 250
        img_dz_y = 1500
        img_w = 260
        img_h = 270
        img_x = 40
        # 9. 虚化背景
        if is_xh:
            video_stream = add_blurred_background(video_stream, video_file, width=width, height=height,
                                                  top_percent=random.choice([0, 1, 2]),
                                                  bottom_percent=random.choice([0, 1, 2]),
                                                  y_percent=random.choice([0, 1]))
            img_y = 125
            img_dz_y = 1000
            img_w = 200
            img_h = 210
        # 6. 添加文字 or 图片 or 视频水印
        # if config.watermark_text != '':
        video_stream = add_watermark(video_stream, config, img_x, img_dz_y, img_y, img_w, img_h,
                                     watermark_type=config.watermark_type,
                                     direction=config.watermark_direction, duration=duration)
        # 商品购买界面
        goods_info_image_path = f"{config.goods_info_watermark_image_path}{good['brand_base']}/{good['goods_name']}.png"
        if os.path.isfile(goods_info_image_path):
            video_stream = add_img_goods(goods_info_image_path, video_stream, 530, 340)

        # 8. 添加字幕 -- 对于视频时长太短的小视频，不需要加字幕
        # audio_path_tmp = ''
        if duration > config.srt_duration:
            video_stream = add_subtitles(video_stream, srt_path_tmp, config)
        # 10. 添加title 和 description
        if good['top_sales_script'] != '' and random.choice([True, False]):
            video_stream = add_title(video_stream, config, title=good['top_sales_script'],
                                     title_gap=config.top_title_gap, title_position='top')

        if good['sales_script'] != '':
            video_stream = add_title(video_stream, config, title=good['sales_script'],
                                     title_gap=config.bottom_title_gap, title_position='bottom')
        # ffmpeg处理结束
        if is_bill:
            final_video_path = f'video/bill_pub/{int(time.time())}_{uuid.uuid4()}.mp4'
        else:
            final_video_path = f'{config.save_path}{int(time.time())}_{uuid.uuid4()}.mp4'
        save_stream_to_video(video_stream, audio_stream, final_video_path, bit_rate)
        time1 = time.time()
        loguru.logger.info('视频去重耗时: {}, 视频时长：{}'.format(time1 - time0, duration))
    finally:
        if srt_path_tmp != '':
            os.remove(srt_path_tmp)
        if audio_path_tmp != '':
            os.remove(audio_path_tmp)
        if opencv_tmp:
            os.remove(opencv_tmp)
        if input_video:
            os.remove(input_video)
        if os.path.exists(video_file):
            os.remove(video_file)
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
