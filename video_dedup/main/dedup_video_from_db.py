# 轮训形式查询数据库中记录，进行去重
from datetime import datetime

import loguru
from apscheduler.schedulers.blocking import BlockingScheduler

from common.constant import VideoStatus
from model.model import get_session, DownloadVideoInfo
from video_dedup.config_parser import read_dedup_config
from video_dedup.video_dedup_by_config import process_dedup_by_config

config = read_dedup_config()
save_path = config.save_path


def deduplicate_from_database():
    loguru.logger.info('-------------- start scheduler time ', datetime.now(), '---------------')
    session = get_session()
    pending_videos = session.query(DownloadVideoInfo).filter_by(video_status=VideoStatus.PENDING).all()
    for pending_video in pending_videos:
        video_title = pending_video.video_title
        if save_path.endswith('/'):
            video_path = save_path + video_title + '.mp4'
        else:
            video_path = save_path + '/' + video_title + '.mp4'
        process_dedup_by_config(pending_video.local_path, video_good)
        # 去重完毕，更新download_video_info表对应记录的 video_status为deduplicated
        loguru.logger.info('update video_md5 -> ', pending_video.video_md5)
        session.query(DownloadVideoInfo).filter_by(video_md5=pending_video.video_md5).update(
            {DownloadVideoInfo.video_status: VideoStatus.DEDUPLICATED, DownloadVideoInfo.deduplicated_video_path: video_path, DownloadVideoInfo.update_time: datetime.now()})
    session.commit()
    loguru.logger.info('-------------- end scheduler time ', datetime.now(), '---------------\n\n')


if __name__ == '__main__':
    scheduler = BlockingScheduler()
    now = datetime.now()
    initial_execution_time = datetime.now().replace(hour=now.hour, minute=now.minute + 1, second=0, microsecond=0)
    scheduler.add_job(deduplicate_from_database, 'interval', seconds=30, start_date=initial_execution_time)  # 每30s执行一次
    scheduler.start()
