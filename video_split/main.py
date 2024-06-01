import os

import loguru
from moviepy.editor import VideoFileClip

from video_split.transnetv2 import TransNetV2
from util.file_util import get_mp4_files_path, delete_file


def split_video(folder_path, source_path):
    model = TransNetV2()
    video_files = get_mp4_files_path(folder_path)
    loguru.logger.info(f"分割视频需要处理的数据有{len(video_files)}条")
    for video_path in video_files:
        split_video_one(video_path, folder_path, source_path,model)


def split_video_one(video_path, folder_path, source_path,model):
    try:
        video_name = os.path.basename(video_path)
        video_name_without_ext = os.path.splitext(video_name)[0]
        video_folder = os.path.dirname(video_path)
        output_folder = os.path.join(source_path,video_folder.replace(folder_path,''))
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        video_frames, single_frame_predictions, all_frame_predictions = model.predict_video_2(video_path)
        scenes = model.predictions_to_scenes(single_frame_predictions)

        with VideoFileClip(video_path) as video_clip:
            video_clip = video_clip.without_audio()
            for i, (start, end) in enumerate(scenes):
                start_time = start / video_clip.fps
                end_time = end / video_clip.fps
                segment_clip = video_clip.subclip(start_time, end_time)
                output_path = os.path.join(output_folder, f'{video_name_without_ext}_{i + 1}.mp4')
                try:
                    segment_clip.write_videofile(output_path, codec='libx264', fps=video_clip.fps)
                finally:
                    segment_clip.close()
        video_clip.close()
    except Exception as e:
        loguru.logger.info(f"Error processing {video_path}: {e}")
    finally:
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except PermissionError as e:
                loguru.logger.info(f"Could not delete {video_path}: {e}")


def remove_audio(video_path):
    video_files = get_mp4_files_path(video_path)
    for video_file in video_files:
        file_name = os.path.basename(video_file)
        video = ''
        video_without_audio = ''
        loguru.logger.info(file_name)
        try:
            video = VideoFileClip(video_file)
            video_without_audio = video.without_audio()
            video_without_audio.write_videofile(video_path + 'temp_' + file_name, codec='libx264', remove_temp=True)
        except Exception as e:
            loguru.logger.info(f"Error processing {file_name}: {e}")
        finally:
            video.close()
            video_without_audio.close()
            delete_file(video_file)


if __name__ == '__main__':
    remove_audio("D:/IDEA/workspace//auto_publish_videos//video/download",
                 "D:/IDEA/workspace//auto_publish_videos//video/source//")
    split_video("D:/IDEA/workspace//auto_publish_videos//video\source")
    # split_video("D:\IDEA\workspace\\auto_publish_videos\\video\source\\tes")
