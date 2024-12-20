# server.py
import os

from flask import Flask, jsonify, request, send_from_directory, render_template
app = Flask(__name__)

BASE_DIRS = {
    '视频': 'E:\IDEA\workspace/auto_publish_videos/video/source\益禾堂\益禾堂素材拍摄2\益禾烤奶，薄荷奶绿',
    '登录图片': '/opt/img/',
}


@app.route('/')
def index():
    return render_template('video_manage.html')


import os

def get_directory_structure(directory):
    dir_structure = {}
    for root, dirs, files in os.walk(directory):
        if files:
            subdir = dir_structure
            for part in root.replace(directory, '').split(os.sep):
                if part:
                    subdir = subdir.setdefault(part, {})
            subdir['files'] = files
    return dir_structure



@app.route('/files', methods=['GET'])
def get_files():
    result = {}
    for name, path in BASE_DIRS.items():
        result[name] = get_directory_structure(path)
    return jsonify(result)


@app.route('/media/<path:filename>', methods=['GET'])
def serve_media(filename):
    file_path, filename = get_file_path(filename)
    return send_from_directory(file_path, filename)


def get_file_path(filename):
    directory, filename = os.path.split(filename)
    sub_path = directory.replace(directory.split('/')[0], '')
    if sub_path.startswith('/'):
        sub_path = sub_path[1:]
    file_path = os.path.join(BASE_DIRS[directory.split('/')[0]], sub_path)
    return file_path, filename


@app.route('/delete', methods=['POST'])
def delete_files():
    files_to_delete = request.json.get('files', [])
    for file in files_to_delete:
        file_path, filename = get_file_path(file)
        real_file = os.path.join(file_path, filename)
        if os.path.exists(real_file):
            os.remove(real_file)
    return '', 204


if __name__ == '__main__':
    app.run(port=6892, debug=True)
