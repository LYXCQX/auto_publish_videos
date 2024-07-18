import re

import edge_tts
import ffmpeg
import loguru
from pydub import AudioSegment

from video_dedup.config_parser import Config


def merge_and_adjust_volumes(origin_audio, bgm_audio, max_sec, volume_a=1.5, volume_b=0.1):
    # 获取音频a的时长
    # probe = ffmpeg.probe(origin_audio_file)
    # duration_a = float(next(stream for stream in probe['streams'] if stream['codec_type'] == 'audio')['duration'])

    # 输入音频a和b，设置音量
    origin_audio = origin_audio.filter('volume', volume=volume_a)
    bgm_audio = bgm_audio.filter('volume', volume=volume_b)

    # 截取音频b以匹配音频a的时长
    audio_b_trimmed = bgm_audio.filter('atrim', duration=max_sec)

    # 合并音频a和截取后的音频b
    merged_audio = ffmpeg.filter([origin_audio, audio_b_trimmed], 'amix', duration='longest')
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


def create_audio(text, audio_path, p_voice, p_rate, p_volume, srt_path):
    communicate = edge_tts.Communicate(
        text=text, voice=p_voice, rate=p_rate, volume=p_volume
    )
    sub_maker = CustomSubMaker()
    with open(audio_path, "wb") as file:
        for chunk in communicate.stream_sync():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                sub_maker.create_sub(
                    (chunk["offset"], chunk["duration"]), chunk["text"]
                )
                loguru.logger.info(f"WordBoundary: {chunk}")
    with open(srt_path, "w", encoding="utf-8") as file:
        file.write(sub_maker.generate_cn_subs(text))


class CustomSubMaker(edge_tts.SubMaker):
    def generate_cn_subs(self, sub_title):
        self.text_list = split_text_len(sub_title)
        if len(self.subs) != len(self.offset):
            raise ValueError("subs and offset are not of the same length")
        data = ""
        j = 0
        for index, sub_text in enumerate(self.text_list):
            sub_t = sub_text
            if '\n' in sub_text:
                sub_t = sub_text.replace('\n', '')
            try:
                start_time = self.offset[j][0]
            except IndexError:
                return data
            try:
                while self.subs[j + 1] in sub_t:
                    j += 1
            except IndexError:
                pass
            sub_mak = edge_tts.submaker.formatter(start_time, self.offset[j][1], sub_t)
            data += f'{index}\r\n{sub_mak if sub_text == sub_t else sub_mak.replace(sub_t, sub_text)}'
            j += 1
        return data


def split_text_len(sub_text, max_length=11):
    # 使用正则表达式按符号分割字符串
    split_text = re.split(r'\W+(?<![-./| ])', sub_text)

    # 移除空字符串
    split_text = [s for s in split_text if s]

    # 对于任何超过 max_length 的部分，进一步分割
    final_split = []
    for part in split_text:
        part = part.replace('|', " ")
        if len(part) > max_length:
            # 进一步分割为每个不超过 max_length 的部分
            # final_split.append()
            split_num(final_split, wrap_text(part, max_length))

        else:
            final_split.append(part)

    return final_split


# 每两个\n分割一下
def split_num(final_split, txt):
    start = 0
    newline_count = 0
    for i, char in enumerate(txt):
        if char == '\n':
            newline_count += 1
        if newline_count == 2:
            final_split.append(txt[start:i])
            start = i + 1
            newline_count = 0
    # 如果有任何剩余文本，请添加最后一段
    if start < len(txt):
        final_split.append(txt[start:])


def wrap_text(text, width):
    """
    将字符串按指定宽度换行，尽量保持字母和数字在一起
    :param text: 输入字符串
    :param width: 每行的字符数
    :return: 处理后的字符串
    """
    wrapped_text = ''
    # 使用正则表达式将文本分割为字母/数字组合和其他字符组合
    parts = re.findall(r'[\da-zA-Z]+|[^a-zA-Z\d\s]', text)
    current_line = ''
    for part in parts:
        if len(current_line) + len(part) <= width:
            current_line += part
        else:
            wrapped_text += current_line.strip() + '\n'
            current_line = part
    if current_line:
        wrapped_text += current_line.strip()
    return wrapped_text


if __name__ == "__main__":
    text = '【龙虾到家-六斤龙虾】敞开吃(六斤小龙虾含配菜)，多种口味可选，蒜香，麻辣，原价328.04，仅需94，外卖到家，坐等开吃'
    srt_path = r'D:\IDEA\workspace\auto_publish_videos\video\srt\aa.srt'
    print(split_text_len(text))
