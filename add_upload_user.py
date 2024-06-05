import asyncio
import os.path
import time

import loguru
from flask import Flask, request, jsonify, render_template

from util.db.sql_utils import getdb
from util.file_util import get_upload_login_path, get_account_file
from video_upload.kuaishou.kuaishou_upload import kuaishou_cookie_gen

app = Flask(__name__)

# 模拟存储用户信息和图片URL
user_data = {}
EXPIRATION_TIME = 120


def cleanup_expired_entries():
    while True:
        time.sleep(60)  # Run cleanup every 60 seconds
        current_time = time.time()
        keys_to_delete = [key for key, value in user_data.items() if current_time > value['kuaishou']['expiry']]
        for key in keys_to_delete:
            del user_data[key]
            try:
                qr_path = get_upload_login_path('kuaishou')
                if os.path.exists(qr_path):
                    os.remove(qr_path)
            except:
                loguru.logger.info('删除二维码文件失败')
            loguru.logger.info(f"Deleted expired entry for UUID: {key}")


# 添加用户的模拟函数
def add_user(platform, login_type, phone_number=None, verification_code=None):
    if platform == 'kuaishou':
        u_id, u_name = asyncio.run(kuaishou_cookie_gen(get_account_file('')))
        db = getdb()
        user_info = db.fetchone(f"select * from user_info where user_id = '{u_id}'")
        if user_info == '' or user_info is None:
            insert_sql = "INSERT INTO user_info (user_id, username, type) VALUES (%s, %s, %s)"
            insert_values = (u_id, u_name, 1)
            db.execute(insert_sql,insert_values)
    user_data[request.remote_addr] = {
        platform: {'status': True,
                   'expiry': time.time() + EXPIRATION_TIME}
    }
    return True


# 获取图片的模拟函数
def get_image(platform):
    if os.path.exists(get_upload_login_path(platform)):
        return f"http://49.232.31.208/img/upload/{platform}_{request.remote_addr}_login.png"
    else:
        return None


@app.route('/add_upload_user', methods=['GET'])
def add_user_route():
    platform = request.args.get('platform')
    login_type = request.args.get('loginType')
    phone_number = request.args.get('phoneNumber')
    verification_code = request.args.get('verificationCode')
    if platform != 'kuaishou':
        return jsonify({'success': False, 'message': '暂不支持该平台'})
    if login_type == 'phone' and (not phone_number or not verification_code):
        return jsonify({'success': False, 'message': '手机号和验证码不能为空'})

    success = add_user(platform, login_type, phone_number, verification_code)
    if success:
        return jsonify({'success': True, 'message': '登录成功'})
    else:
        return jsonify({'success': False, 'message': '登录失败'})


@app.route('/get_qr_image', methods=['GET'])
def get_image_route():
    platform = request.args.get('platform')
    login_type = request.args.get('loginType')
    image_url = get_image(platform)
    if image_url:
        return jsonify({'success': True, 'imageUrl': image_url})
    elif request.remote_addr in user_data and user_data[request.remote_addr][platform]['status']:
        return jsonify({'success': True, 'message': '登录成功'})
    else:
        return jsonify({'success': False, 'message': '未找到图片或用户未登录'})


@app.route('/')
def index():
    return render_template('add_upload_user.html')


if __name__ == '__main__':
    app.run(debug=True, port=6891)
