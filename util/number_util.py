import re
from decimal import Decimal


# 数字到中文数字的转换（处理整数和小数部分）
def number_to_chinese(number_b):
    s_com = {
        '0': "零", '1': "一", '2': "二", '3': "三", '4': "四",
        '5': "五", '6': "六", '7': "七", '8': "八", '9': "九"
    }
    s_unit = {
        0: '', 1: '十', 2: '百', 3: '千', 4: '万', 8: '亿'
    }
    re_re = ""
    if '.' in number_b:
        s_1 = number_b[0:number_b.find('.')]
        s_2 = number_b[number_b.find('.') + 1:]
        flag_1 = 0
        s_1 = s_1[::-1]

        for i in s_1:
            if flag_1 != 0 and flag_1 % 4 == 0:
                re_re += s_unit[flag_1]
            if i != '0':
                re_re += s_unit[flag_1 % 4]
            re_re += s_com[i]
            flag_1 += 1
        re_re = re_re[::-1]
        while re_re.endswith('零') and len(re_re) > 1:
            re_re = re_re[:-1]
        # 中文数字没有连续的零
        while "零零" in re_re:
            re_re = re_re.replace("零零", "零")
        re_re += '点'
        for i in s_2:
            re_re += s_com[i]
    else:
        s_1 = number_b
        s_1 = s_1[::-1]
        flag_1 = 0

        for i in s_1:
            if flag_1 != 0 and flag_1 % 4 == 0:
                re_re += s_unit[flag_1]
            if i != '0':
                re_re += s_unit[flag_1 % 4]
            re_re += s_com[i]
            flag_1 += 1
        re_re = re_re[::-1]
        while re_re.endswith('零') and len(re_re) > 1:
            re_re = re_re[:-1]
        # 中文数字没有连续的零
        while "零零" in re_re:
            re_re = re_re.replace("零零", "零")
    if re_re[1] == '十' and re_re[0] == '一':
        re_re = re_re[1:]
    return f'百分之{re_re}'


def number_to_chinese_percentage(match):
    num = Decimal(match.group(1))
    return number_to_chinese(format(num.normalize(), 'f'))


def num_to_chinese(num_txt):
    if '%' in num_txt:
        # 匹配百分比形式的数字
        pattern = re.compile(r'(\d+\.?\d*)%')
        result = pattern.sub(number_to_chinese_percentage, num_txt)
        return result
    else:
        return num_txt