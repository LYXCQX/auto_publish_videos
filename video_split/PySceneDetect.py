from scenedetect import split_video_ffmpeg, detect, open_video, SceneManager
from scenedetect.detectors import ContentDetector


def split_video_into_scenes(video_path, output_path, threshold=27.0):
    # 打开我们的视频，创建场景管理器，并添加检测器.
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video, show_progress=True)
    scene_list = scene_manager.get_scene_list(start_in_scene=True)
    split_video_ffmpeg(video_path, scene_list, output_path, '$VIDEO_NAME-$SCENE_NUMBER.mp4',
                       arg_override='-map 0:v -c:v libx264 -preset veryfast -crf 22',
                       show_progress=True)
    # scene_list = detect(video_path, ContentDetector())
    # split_video_ffmpeg(video_path, scene_list, output_path)


if __name__ == '__main__':
    split_video_into_scenes('D:/IDEA/workspace/auto_publish_videos/video/download/aa/11.mp4',
                            'D:/IDEA/workspace/auto_publish_videos/video/source/')
