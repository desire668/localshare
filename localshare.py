from flask import Flask, request, send_file, jsonify, render_template_string
import os
import time

app = Flask(__name__)

# 配置文件上传目录
UPLOAD_FOLDER = 'uploads'
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
                file.save(file_path)
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
    file_path = os.path.join(UPLOAD_FOLDER, file_id)
    if os.path.exists(file_path):
        return send_file(file_path, 
                        as_attachment=True,
                        download_name=file_id)
    return jsonify({'error': '文件不存在'}), 404

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
            
            if (fileInput.files.length === 0) return;

            uploadBtn.disabled = true;
            uploadBtn.textContent = '上传中...';
            
            const formData = new FormData();
            for (let file of fileInput.files) {
                formData.append('files', file);
            }

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    showStatus('上传成功！', 'success');
                    fileInput.value = '';
                    refreshFileList();
                } else {
                    throw new Error('上传失败');
                }
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)