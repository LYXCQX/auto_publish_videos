import re

import edge_tts
import ffmpeg
import loguru
from pydub import AudioSegment
from snownlp import SnowNLP


def merge_and_adjust_volumes(origin_audio, bgm_audio, origin_duration, volume_a=1.2, volume_b=0.3):
    # 获取音频a的时长
    # probe = ffmpeg.probe(origin_audio_file)
    # duration_a = float(next(stream for stream in probe['streams'] if stream['codec_type'] == 'audio')['duration'])

    # 输入音频a和b，设置音量
    origin_audio = origin_audio.filter('volume', volume=volume_a)
    bgm_audio = bgm_audio.filter('volume', volume=volume_b)

    # 截取音频b以匹配音频a的时长
    audio_b_trimmed = bgm_audio.filter('atrim', duration=origin_duration)

    # 合并音频a和截取后的音频b
    merged_audio = ffmpeg.filter([origin_audio, audio_b_trimmed], 'amix', duration='first')

    return merged_audio


def read_ffmpeg_audio_from_file(audio_path):
    return ffmpeg.input(audio_path).audio


def adjust_audio_duration(input_audio_path, output_audio_path, target_duration_seconds):
    # 打开输入音频文件
    audio = AudioSegment.from_file(input_audio_path)

    # 计算当前音频的持续时间（秒）
    current_duration_seconds = len(audio) / 1000.0

    # 计算速率调整因子
    speed_factor = current_duration_seconds / target_duration_seconds

    # 根据速率调整因子来调整音频速率
    adjusted_audio = audio.speedup(playback_speed=speed_factor)

    # 保存调整后的音频
    adjusted_audio.export(output_audio_path, format="wav")


def merge_audio_files(input_files, output_file):
    # 初始化一个空的音频段
    merged_audio = AudioSegment.empty()

    # 合并音频文件
    for input_file in input_files:
        audio_segment = AudioSegment.from_file(input_file)
        merged_audio += audio_segment

    # 保存合并后的音频
    merged_audio.export(output_file, format="wav")


def merge_audio_files_with_pause(input_files, output_file, pause_duration_ms=200):
    # 初始化一个空的音频段
    merged_audio = AudioSegment.empty()

    # 合并音频文件
    for input_file in input_files:
        audio_segment = AudioSegment.from_file(input_file)

        # 在每个音频文件后插入静音段
        if len(merged_audio) > 0:
            pause_segment = AudioSegment.silent(duration=pause_duration_ms)
            merged_audio += pause_segment

        merged_audio += audio_segment

    # 保存合并后的音频
    merged_audio.export(output_file, format="wav")


def create_audio(text, audio_path, p_voice, p_rate, p_volume):
    communicate = edge_tts.Communicate(
        text=text, voice=p_voice, rate=p_rate, volume=p_volume
    )
    with open(audio_path, "wb") as file:
        for chunk in communicate.stream_sync():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                loguru.logger.info(f"WordBoundary: {chunk}")


def gen_srt(text, srt_path):
    # popboy：将文本分成多个句子
    sentences = []
    t = SnowNLP(text)
    for sen in t.sentences:
        # loguru.logger.info(sen + "\n")
        sentences.append(sen)

    # 逐句进行再判断，如果大于15个字符则再进行分割。
    captions = []
    # delimiter_set = {'。', '#', '?', '？', '$', ':', '：'}
    # for sen in sentences:
    #     if len(sen) > 10:
    #         sub_sen = re.split(r'[{char_set}]'.format(char_set=delimiter_set), sen)
    #         for i in sub_sen:
    #             captions.append(i)
    #     else:
    #         captions.append(sen)
    # 使用正则表达式按符号分割字符串
    split_text = re.split(r'\W+(?<![-])', text)
    # 移除空字符串
    split_text = [s for s in split_text if s]
    # 对于任何超过 max_length 的部分，进一步分割
    max_length = 10
    for part in split_text:
        if len(part) > max_length:
            # 进一步分割为每个不超过 max_length 的部分
            captions.extend([part[i:i + max_length] for i in range(0, len(part), max_length)])
        else:
            captions.append(part)
    # 计算每个句子的持续时间
    end_time = 0
    srt = ''
    for i, sentence in enumerate(captions):
        start_time = end_time + 0
        start_time_str = "{:02d}:{:02d}:{:02d},{}".format(int(start_time // 3600), int((start_time % 3600) // 60),
                                                          int(start_time % 60), "000")
        duration = len(sentence) * 0.225
        end_time = start_time + duration
        end_time_str = "{:02d}:{:02d}:{:02d},{}".format(int(end_time // 3600), int((end_time % 3600) // 60),
                                                        int(end_time % 60), "000")
        srt += "{}\n{} --> {}\n{}\n\n".format(i + 1, start_time_str, end_time_str, sentence)

    # 保存srt文件
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(srt)
    loguru.logger.info(f'字幕srt文件已保存到{srt_path}')


def split_text_len(text, max_length=10):
    # 使用正则表达式按符号分割字符串
    split_text = re.split(r'\W+(?<![-])', text)

    # 移除空字符串
    split_text = [s for s in split_text if s]

    # 对于任何超过 max_length 的部分，进一步分割
    final_split = []
    for part in split_text:
        if len(part) > max_length:
            # 进一步分割为每个不超过 max_length 的部分
            final_split.extend([part[i:i + max_length] for i in range(0, len(part), max_length)])
        else:
            final_split.append(part)

    return final_split


if __name__ == "__main__":
    text = '【龙虾到家-六斤龙虾】敞开吃(六斤小龙虾含配菜)，多种口味可选，蒜香，麻辣，原价328.04，仅需94，外卖到家，坐等开吃'
    srt_path = r'D:\IDEA\workspace\auto_publish_videos\video\srt\aa.srt'
    print(split_text_len(text))
