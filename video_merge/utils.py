import time
from functools import wraps

import loguru




def calculate_dimensions(width: int, height: int, target_width: int, target_height: int):
    if width == 0 or height == 0:
        loguru.logger.critical("视频的宽度或高度为0, 请检查视频")
        raise ValueError("Width or height is 0")
    scale = min(target_width / width, target_height / height)
    new_width = int(width * scale)
    new_height = int(height * scale)
    pad_top = (target_height - new_height) // 2
    pad_bottom = target_height - new_height - pad_top
    pad_left = (target_width - new_width) // 2
    pad_right = target_width - new_width - pad_left
    return new_width, new_height, pad_top, pad_bottom, pad_left, pad_right


def evenly_distribute_numbers(current_num: int, target_num: int) -> list[int]:
    """平滑抽帧"""
    if current_num <= target_num:
        raise ValueError("current_num must be greater than target_num")

    diff = current_num - target_num  # 需要移除的数字个数
    interval = current_num / diff  # 平均间隔

    # 生成初始列表
    numbers = list(range(current_num))

    # 移除均匀间隔位置的数字
    for i in range(diff):
        remove_index = int(round(i * interval))
        if remove_index < len(numbers):
            numbers.pop(remove_index)

    return numbers


def evenly_interpolate_numbers(current_num: int, target_num: int) -> list[int]:
    """平滑插值"""
    if current_num >= target_num:
        raise ValueError("current_num must be less than target_num")

    diff = target_num - current_num  # 需要增加的数字个数
    interval = (current_num - 1) / (diff + 1)  # 插入位置的平均间隔

    # 生成初始列表
    numbers = list(range(current_num))
    new_numbers = []

    # 计算所有插入点
    insert_positions = [round((i + 1) * interval) for i in range(diff)]

    # 均匀插入数字
    insert_index = 0
    for i in range(current_num):
        new_numbers.append(numbers[i])
        # 在插入点插入数字
        if insert_index < diff and i + 1 >= insert_positions[insert_index]:
            new_numbers.append(numbers[i])
            insert_index += 1

    return new_numbers


if __name__ == '__main__':
    # 抽帧示例用法
    # current_num = 180000
    # target_num = 150000
    # result = evenly_distribute_numbers(current_num, target_num)
    # loguru.logger.info(f"抽帧:{result}")
    # loguru.logger.info(len(result))

    # 插帧示例用法
    current_num = 1148
    target_num = 1500
    start = time.time()
    result = evenly_interpolate_numbers(current_num, target_num)
    loguru.logger.info(time.time() - start)
    loguru.logger.info(f"插帧:{result}")
