# server.py
from flask import Flask, jsonify, request, send_from_directory, render_template
import os

app = Flask(__name__)

BASE_DIRS = {
    'Directory 1': 'D:/IDEA/workspace/auto_publish_videos/video',
    'Directory 2': 'D:/system/Desktop/fsdownload',
}


@app.route('/')
def index():
    return render_template('video_manage.html')


def get_directory_structure(directory):
    dir_structure = {}
    for root, dirs, files in os.walk(directory):
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
    directory, filename = os.path.split(filename)
    s8b_path = directory.replace(directory.split('/')[0], '')
    if s8b_path.startswith('/'):
        s8b_path = s8b_path[1:]
    file_path = os.path.join(BASE_DIRS[directory.split('/')[0]], s8b_path)
    print(file_path)
    return send_from_directory(file_path, filename)


@app.route('/delete', methods=['POST'])
def delete_files():
    files_to_delete = request.json.get('files', [])
    for file in files_to_delete:
        file_path = os.path.join(*file.split('/'))
        if os.path.exists(file_path):
            os.remove(file_path)
    return '', 204


if __name__ == '__main__':
    app.run(port=6892, debug=True)
