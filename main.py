from flask import Flask, request, send_file, jsonify, render_template_string, Response
import os
import time
import socket
import hashlib
import urllib.parse

app = Flask(__name__)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

# 配置文件上传目录
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 扫描本地文件
def scan_local_files():
    files = []
    try:
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                # 获取文件信息
                stat = os.stat(file_path)
                files.append({
                    'id': filename,
                    'name': filename,
                    'path': file_path,
                    'size': stat.st_size,
                    'timestamp': int(stat.st_mtime * 1000),
                    'exists': True
                })
    except Exception as e:
        print(f"扫描本地文件失败: {e}")
    return files

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        return jsonify({'error': '没有文件'}), 400
    
    uploaded_files = request.files.getlist('files')
    
    for file in uploaded_files:
        if file.filename:
            original_filename = file.filename
            file_path = os.path.join(UPLOAD_FOLDER, original_filename)
            
            # 处理重名文件
            counter = 1
            base_name, ext = os.path.splitext(original_filename)
            while os.path.exists(file_path):
                new_filename = f"{base_name}_{counter}{ext}"
                file_path = os.path.join(UPLOAD_FOLDER, new_filename)
                original_filename = new_filename
                counter += 1
            
            try:
                # 使用流式写入，不限制速度
                chunk_size = 4 * 1024 * 1024  # 4MB
                total_size = 0
                
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = file.stream.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        total_size += len(chunk)
                        # 发送进度到客户端
                        if request.headers.get('X-Progress-ID'):
                            progress = total_size / int(request.headers['Content-Length'])
                            print(f"上传进度: {progress:.2%}")  # 调试信息
                
                # 设置文件修改时间为当前时间
                os.utime(file_path, (time.time(), time.time()))
            except Exception as e:
                print(f"保存文件失败: {e}")
                return jsonify({'error': '文件保存失败'}), 500
    
    return jsonify({'message': '上传成功'})

@app.route('/files')
def list_files():
    files = scan_local_files()
    # 按时间排序
    files.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(files)

@app.route('/download/<file_id>')
def download_file(file_id):
    try:
        # 解码文件名
        file_name = file_id
        file_path = os.path.join(UPLOAD_FOLDER, file_name)
        
        print(f"下载文件路径: {file_path}")  # 调试信息
        
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")  # 调试信息
            return jsonify({'error': '文件不存在'}), 404
        
        # 获取文件信息
        file_size = os.path.getsize(file_path)
        print(f"文件大小: {file_size} bytes")  # 调试信息
        
        # 设置响应头
        response_headers = {
            'Content-Type': 'application/octet-stream',
            'Content-Disposition': f'attachment; filename="{urllib.parse.quote(file_name)}"',
            'Content-Length': str(file_size),
            'Cache-Control': 'public, max-age=3600',
            'Accept-Ranges': 'bytes',
            'ETag': hashlib.md5(file_name.encode()).hexdigest()
        }

        # 支持断点续传
        range_header = request.headers.get('Range')
        if range_header:
            start, end = range_header.replace('bytes=', '').split('-')
            start = int(start)
            end = int(end) if end else file_size - 1
            
            if start >= file_size:
                return jsonify({'error': '无效的Range请求'}), 416
                
            length = end - start + 1
            response_headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response_headers['Content-Length'] = str(length)
            
            return Response(
                file_sender(file_path, start, end),
                206,
                headers=response_headers,
                direct_passthrough=True
            )
        else:
            # 完整文件下载
            return Response(
                file_sender(file_path, 0, file_size - 1),
                headers=response_headers,
                direct_passthrough=True
            )
            
    except Exception as e:
        print(f"下载文件出错: {str(e)}")
        return jsonify({'error': '文件下载失败'}), 500

def file_sender(file_path, start, end):
    try:
        print(f"开始发送文件: {file_path}")  # 调试信息
        with open(file_path, 'rb') as f:
            f.seek(start)
            remaining = end - start + 1
            chunk_size = 16 * 1024 * 1024  # 16MB chunks
            
            while remaining > 0:
                read_size = min(chunk_size, remaining)
                try:
                    chunk = f.read(read_size)
                    if not chunk:
                        print("文件读取完成")  # 调试信息
                        break
                    yield chunk
                    remaining -= read_size
                except Exception as e:
                    print(f"文件读取出错: {str(e)}")  # 调试信息
                    raise
    except Exception as e:
        print(f"文件发送出错: {str(e)}")  # 调试信息
        raise

def rate_limited_stream(stream, max_speed, chunk_size=4*1024*1024):
    buffer = b''
    for chunk in stream:
        buffer += chunk
        while len(buffer) >= chunk_size:
            yield buffer[:chunk_size]
            buffer = buffer[chunk_size:]
            time.sleep(chunk_size / max_speed)
    if buffer:
        yield buffer

# HTML模板保持不变，但移除用户ID相关的HTML部分
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>局域网文件共享</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .upload-section {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 30px 20px;
            text-align: center;
        }
        .file-list {
            margin-top: 20px;
        }
        .file-item {
            background: #f8f9ff;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .file-info {
            flex-grow: 1;
        }
        .download-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 24px;
            border-radius: 25px;
            text-decoration: none;
            transition: all 0.3s;
            text-align: center;
            display: inline-block;
            min-width: 120px;
        }
        .download-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .status {
            margin-top: 10px;
            padding: 10px;
            border-radius: 4px;
            display: none;
        }
        .status.success {
            background-color: #e8f5e9;
            color: #2e7d32;
        }
        .status.error {
            background-color: #ffebee;
            color: #c62828;
        }
        
        /* 进度条样式 */
        .progress-container {
            width: 100%;
            max-width: 400px;
            background-color: #f1f1f1;
            border-radius: 25px;
            margin: 15px 0;
            overflow: hidden;
        }
        
        .progress-bar {
            width: 0;
            height: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            text-align: center;
            line-height: 20px;
            color: white;
            transition: width 0.3s ease;
        }
        
        /* 文件选择按钮样式 */
        .file-input-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 15px;
            margin-bottom: 20px;
            width: 100%;
            max-width: 400px;
        }

        .custom-file-input {
            display: none;
        }

        .file-select-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 24px;
            border-radius: 25px;
            cursor: pointer;
            text-align: center;
            transition: all 0.3s;
            border: none;
            font-size: 16px;
            width: 200px;
        }

        .file-select-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        #uploadBtn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 24px;
            border-radius: 25px;
            cursor: pointer;
            border: none;
            font-size: 16px;
            width: 200px;
            transition: all 0.3s;
        }

        #uploadBtn:hover {
            transform: translateY(-2px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        #uploadBtn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .selected-files {
            margin: 10px 0;
            color: #666;
            font-size: 0.9em;
            text-align: center;
        }
        
        /* 移动端适配样式 */
        @media screen and (max-width: 768px) {
            body {
                padding: 10px;
            }
            
            .container {
                padding: 10px;
            }
            
            .file-item {
                flex-direction: column;
                gap: 15px;
                padding: 15px;
            }
            
            .file-info {
                width: 100%;
            }
            
            .file-actions {
                width: 100%;
            }
            
            .download-btn {
                width: 100%;
                padding: 15px;
                font-size: 16px;
                box-sizing: border-box;
                margin-top: 5px;
            }
            
            .download-btn:hover {
                transform: none;
            }
            
            .download-btn:active {
                opacity: 0.9;
                transform: translateY(1px);
            }
            
            #fileInput {
                width: 100%;
                margin-bottom: 10px;
            }
            
            #uploadBtn {
                width: 80%;
                padding: 15px;
                font-size: 16px;
                margin: 0 auto;
                display: block;
            }
            
            .file-name {
                font-size: 1.1em;
                margin-bottom: 5px;
                word-break: break-all;
            }
            
            .file-details {
                font-size: 0.9em;
                color: #666;
            }

            .file-input-container {
                width: 100%;
                padding: 20px 0;
            }

            .file-select-btn {
                width: 80%;
                padding: 15px;
                font-size: 16px;
            }

            #uploadBtn {
                width: 80%;
                padding: 15px;
                font-size: 16px;
                margin: 0 auto;
                display: block;
            }

            .upload-section {
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 20px 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="upload-section">
            <h2>上传文件</h2>
            <div class="file-input-container">
                <input type="file" id="fileInput" class="custom-file-input" multiple>
                <button class="file-select-btn" onclick="document.getElementById('fileInput').click()">
                    选择文件
                </button>
                <div class="selected-files" id="selectedFiles">未选择文件</div>
            </div>
            <button id="uploadBtn" onclick="uploadFiles()">上传</button>
            <div class="progress-container">
                <div class="progress-bar" id="progressBar">0%</div>
            </div>
            <div class="status"></div>
        </div>

        <div class="file-list">
            <h2>共享文件列表</h2>
            <div id="fileList"></div>
        </div>
    </div>

    <script>
        function showStatus(message, type) {
            const status = document.querySelector('.status');
            status.textContent = message;
            status.className = 'status ' + type;
            status.style.display = 'block';
            setTimeout(() => status.style.display = 'none', 3000);
        }

        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        async function uploadFiles() {
            const fileInput = document.getElementById('fileInput');
            const uploadBtn = document.getElementById('uploadBtn');
            const progressBar = document.getElementById('progressBar');
            
            if (fileInput.files.length === 0) return;

            uploadBtn.disabled = true;
            uploadBtn.textContent = '上传中...';
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
            
            const formData = new FormData();
            for (let file of fileInput.files) {
                formData.append('files', file);
            }

            try {
                const xhr = new XMLHttpRequest();
                
                xhr.upload.addEventListener('progress', function(e) {
                    if (e.lengthComputable) {
                        const percent = Math.round((e.loaded / e.total) * 100);
                        progressBar.style.width = percent + '%';
                        progressBar.textContent = percent + '%';
                    }
                });

                xhr.addEventListener('load', function() {
                    if (xhr.status === 200) {
                        showStatus('上传成功！', 'success');
                        fileInput.value = '';
                        refreshFileList();
                    } else {
                        throw new Error('上传失败');
                    }
                });

                xhr.addEventListener('error', function() {
                    throw new Error('上传失败');
                });

                xhr.open('POST', '/upload');
                xhr.send(formData);
                
            } catch (error) {
                showStatus('上传失败：' + error.message, 'error');
            } finally {
                uploadBtn.disabled = false;
                uploadBtn.textContent = '上传';
            }
        }

        async function downloadFile(fileId, fileName) {
            try {
                window.location.href = `/download/${fileId}`;
            } catch (error) {
                showStatus('下载失败：' + error.message, 'error');
            }
        }

        async function refreshFileList() {
            try {
                const response = await fetch('/files');
                const files = await response.json();
                
                const fileList = document.getElementById('fileList');
                if (files.length === 0) {
                    fileList.innerHTML = '<div style="text-align: center; color: #666;">暂无文件</div>';
                    return;
                }
                
                fileList.innerHTML = files.map(file => `
                    <div class="file-item">
                        <div class="file-info">
                            <div class="file-name">${file.name}</div>
                            <div class="file-details">
                                大小: ${formatFileSize(file.size)} | 
                                时间: ${new Date(file.timestamp).toLocaleString()}
                            </div>
                        </div>
                        <div class="file-actions">
                            <a href="javascript:void(0)" 
                               onclick="downloadFile('${file.id}', '${file.name}')" 
                               class="download-btn">下载</a>
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('获取文件列表失败：', error);
            }
        }

        refreshFileList();
        setInterval(refreshFileList, 5000);

        // 添加文件选择监听器
        document.getElementById('fileInput').addEventListener('change', function(e) {
            const selectedFiles = e.target.files;
            const selectedFilesDiv = document.getElementById('selectedFiles');
            
            if (selectedFiles.length > 0) {
                if (selectedFiles.length === 1) {
                    selectedFilesDiv.textContent = `已选择: ${selectedFiles[0].name}`;
                } else {
                    selectedFilesDiv.textContent = `已选择 ${selectedFiles.length} 个文件`;
                }
            } else {
                selectedFilesDiv.textContent = '未选择文件';
            }
        });
    </script>
</body>
</html>
'''

def main():
    host = '0.0.0.0'
    port = 5000
    print(f"服务器运行在: http://{get_local_ip()}:{port}")
    app.run(host=host, port=port)

if __name__ == '__main__':
    main()
