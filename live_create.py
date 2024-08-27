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


def process_dedup_by_config(config: Config, oral_text):
    time0 = time.time()
    # audio_path_tmp = f'{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp3'
    bgm_path_tmp = f'{config.video_temp}{int(time.time())}_{uuid.uuid4()}.mp3'
    audio_path_tmp = "E:\IDEA\workspace\\auto_publish_videos\\video\live\\audio.wav"
    input_video = ''
    ffmpeg_tmp = ''
    try:
        # create_audio(oral_text, audio_path_tmp, random.choice(config.role), config.rate, config.volume, srt_path_tmp)
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
        input_video = merge_video(config, {"brand_base": "团油"}, max_sec, 'E:\团油\快手通用素材库')
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
        f"{config.video_path}{good['brand_base']}" if video_paths is None else video_paths)
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
    process_dedup_by_config(config, "打开咱们下面的小团子" +
                            "咱们给大家上新了很多的优惠链接" +
                            "家人们都可以点击下方的小团子，直接去冲 " +
                            "都可以直接去拍，主播直播间主打的就是一个经济实惠，" +
                            "今天的一号链接是团邮代金券， 让你的加油成本降低，让每一滴油都更加经济实惠，89元抵100元代金券，让你的购物更加划算，咱们直接在线上买，到时候加油的时候可以直接用，大家都知道，线下加油是不会有任何优惠的，一毛钱也不会给你便宜，" +
                            "购买了咱们得团油优惠券，就可以享受到优惠，那么省下来的钱，自己买点东西吃不好么，对吧，所以说可以在咱们直播间直接下单，" +
                            "如果说您在主播直播间拍完之后，您觉得贵了或者不想要了，这个都没关系，如果过期咱还没有使用，会自动给大家退款，真的是非常实惠 ，非常划算的，" +
                            "大家刷到主播，咱们趁着有优惠咱们多拍上几单，抢到就是赚到，今天就是说咱们在线上做一个推广，" +
                            "直播间下单更优惠呢，拍完省很多钱，使用方式和你去线下实体店消费是一样的呢，" +
                            "可以点开小团子下单，体验一下宝宝们，先直播间左上角点点关注 ，点关注之后，再打开下方小团子抢优惠，咱们今天直播间下单，都享受安心购，无忧购，随时退，全额退，不收你任何一分一毛手续费，" +
                            "放心拍 大胆拍 不用担心用不了，这个商品是咱们直播间宠粉福利，机会难得 手快有 手慢无，大家赶紧下单啦，咱们这次的商品价格真的是超值的优惠，绝对物超所值 买到就是赚到，家人们 点下方团子冲，" +
                            "给大家推荐一款爆款商品，那就是咱们的二号链接，二号链接是178元抵200元代金券，相当于八折购买，让你的购物更加划算，咱们直接在线上买，到时候加油的时候可以直接用，大家都知道，线下加油是不会有任何优惠的，一毛钱也不会给你便宜，" +
                            "购买了咱们得团油优惠券，就可以享受到优惠，那么省下来的钱，自己出去吃顿饭不香么，对吧，所以说可以在咱们直播间直接下单，" +
                            "这里是快手和合作的团购福利专场，大家喜欢的朋友们都可以往咱们的直播间进一进，" +
                            "咱们今天所有的商品放心去拍 放心去囤，错过了这次 ，下次就要等好久了，点击下方的团子赶紧买起来吧，" +
                            "主播直播间主打的就是一个经济实惠，如果说您在主播直播间拍完之后，您觉得贵了，或者不想要了，这个都没关系，如果过期咱还没有使用，会自动给大家退款，" +
                            "这个价格的话真的不需要多介绍，因为宝宝们在线下门店消费过买过的，一眼就能对比出来咱们价格到底有多么划，算多么有竞争力，所以能囤的抓紧囤，今天就是说在线上做一个推广直播间，下单更优惠，" +
                            "拍完省很多钱，使用方式和你去线下实体店消费是一样的，可以点开小团子下单体验一下，除了直播间介绍的商品，咱们还给大家安排了一些我们快手的其他团购商品，都是给大家打到很低的价格，十分划算，大家有兴趣的可以看一看，" +
                            "囤一囤，我们任何商品都支持随时退，过期退，不收任何手续费，再提醒下直播间的家人们，咱们的优惠套餐都是限量折扣，" +
                            "大家可以看一下咱们得另一款商品，那就是咱们的三号链接，三号链接是178元抵200元代金券，相当于八折购买，让你的购物更加划算，咱们直接在线上买，到时候加油的时候可以直接用，大家都知道，线下加油是不会有任何优惠的，一毛钱也不会给你便宜，" +
                            "购买了咱们得团油优惠券，就可以享受到优惠，那么省下来的钱，自己买点东西吃不好么，对吧，所以说可以在咱们直播间直接下单，"
                            )
