from timeit import default_timer
import time

import loguru
import pymysql
from dbutils.pooled_db import PooledDB
from pymysql.cursors import DictCursor


class MySQLConfig:
    def __init__(self, host, user, password, database, port=3306, charset='utf8mb4'):
        self.host = host
        self.port = port
        self.db = database
        self.user = user
        self.password = password
        self.charset = charset


class DBPool:
    """db连接池"""
    __pool = None
    __MAX_CONNECTIONS = 100  # 创建连接池的最大数量
    __MIN_CACHED = 10  # 连接池中空闲连接的初始数量
    __MAX_CACHED = 20  # 连接池中空闲连接的最大数量
    __MAX_SHARED = 10  # 共享连接的最大数量
    __BLOCK = True  # 超过最大连接数量时候的表现，为True等待连接数量下降，为false直接报错处理
    # __MAX_USAGE = 10000000  # 单个连接的最大重复使用次数
    '''
        set_session:可选的SQL命令列表，可用于准备
                    会话，例如[“将日期样式设置为...”，“设置时区...”]
                    重置:当连接返回池中时，应该如何重置连接
                    (False或None表示回滚以begin()开始的事务，
                    为安全起见，始终发出回滚命令)
    '''
    __RESET = True
    __SET_SESSION = ['SET AUTOCOMMIT = 0']  # 设置自动提交

    def __init__(self, config: MySQLConfig):
        if not self.__pool:
            self.__class__.__pool = PooledDB(creator=pymysql,
                                             host=config.host,
                                             port=config.port,
                                             user=config.user,
                                             password=config.password,
                                             database=config.db,
                                             charset=config.charset,
                                             maxconnections=self.__MAX_CONNECTIONS,
                                             mincached=self.__MIN_CACHED,
                                             maxcached=self.__MAX_CACHED,
                                             maxshared=self.__MAX_SHARED,
                                             blocking=self.__BLOCK,
                                             setsession=self.__SET_SESSION,
                                             reset=self.__RESET)

    def get_connect(self):
        return self.__pool.connection()


class MySQLDB:
    def __init__(self, pool, log_path='', commit=True, log_time=True, log_label='总用时'):
        """

        :param commit: 是否在最后提交事务(设置为False的时候方便单元测试)
        :param log_time:  是否打印程序运行总时间
        :param log_label:  自定义log的文字
        """
        self.pool = pool
        self._commit = commit
        self._log_time = log_time
        self._log_path = log_path
        self._log_label = log_label

    def __enter__(self):

        # 如果需要记录时间
        if self._log_time is True:
            self._start = default_timer()

        # 从连接池获取数据库连接
        conn = self.pool.get_connect()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        self._conn = conn
        self._cursor = cursor
        return self

    def __exit__(self, *exc_info):
        # 提交事务
        if self._commit:
            self._conn.commit()
        # 在退出的时候自动关闭连接和cursor

        self._cursor.close()
        self._conn.close()

        if self._log_time:
            diff = default_timer() - self._start
            if len(self._log_path) == 0:
                loguru.logger.info('%s: %.6f 秒' % (self._log_label, diff))
            else:
                self._log('%s: %.6f 秒' % (self._log_label, diff))

    def execute(self, sql):
        # self._log(f"sql: {sql}")
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    @property
    def connect(self):
        return self._conn

    @property
    def cursor(self):
        return self._cursor

    def _log(self, s):
        t = time.time()
        str_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))
        with open(self._log_path, "a", encoding='utf-8') as logger:
            logger.write(f"[{str_time}-db]: {str(s)}\n")


class DBUtils:
    def __init__(self, config, log_path):
        self._pool = DBPool(config)
        self._log_path = log_path

    def execute(self, sql):
        with MySQLDB(self._pool, self._log_path) as db:
            return db.execute(sql)

    def transaction(self):
        return MySQLDB(self._pool, self._log_path)
