import decimal

import loguru
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()


class DownloadVideoInfo(Base):
    __tablename__ = 'download_video_info'
    video_md5 = Column(String(500), primary_key=True)
    video_id = Column(String(500))
    video_url = Column(Text)
    target_pub_user_id = Column(Text)
    target_pub_account = Column(Text)
    download_url = Column(Text)
    video_title = Column(Text)
    source_platform_user_id = Column(Text)
    video_tags = Column(Text)
    local_path = Column(Text)
    deduplicated_video_path = Column(Text)
    video_status = Column(String(50))
    pub_date = Column(Date)
    pub_time = Column(DateTime)
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class ShipinhaoUserInfo(Base):
    __tablename__ = 'shipinhao_user_info'
    shipinhao_user_id = Column(String(200), primary_key=True)
    shipinhao_username = Column(String(200))
    publish_hours = Column(String(200))
    latest_pub_time = Column(DateTime)
    machine_seq = Column(Integer)
    cookies = Column(Text)
    pub_num = Column(Integer)
    update_time = Column(DateTime)


class HomepageScanRecord(Base):
    __tablename__ = 'homepage_scan_record'
    homepage_url_md5 = Column(String(500), primary_key=True)
    homepage_url = Column(String(500))
    gap_minutes = Column(Integer)
    empty_cnt = Column(Integer)
    latest_update_time = Column(DateTime)
    next_scan_time = Column(DateTime)


class VideoGoods(Base):
    __tablename__ = 'video_goods'
    id = Column(Integer, primary_key=True)
    goods_id = Column(String(250))
    goods_name = Column(String(250))
    goods_title = Column(String(500))
    goods_des = Column(Text)
    commission_rate = Column(String)
    real_price = Column(String)
    goods_price = Column(String)
    sales_volume = Column(Integer)
    brand = Column(String(50))
    sales_script = Column(Text)
    top_sales_script = Column(String(255))
    state = Column(Integer)
    create_time = Column(DateTime)
    longitude = Column(String)
    dimension = Column(String)
    tips = Column(Text)


engine = create_engine('mysql+pymysql://root:leyuan521@49.232.31.208:3306/video_tools?charset=utf8mb4')
Session = sessionmaker(bind=engine)


def get_session():
    return Session()


loguru.logger.info(datetime.date.today())
