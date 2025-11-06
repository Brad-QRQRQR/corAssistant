import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename # 用于获取安全的文件名

from inference import get_inference_result

# --- 配置 ---
UPLOAD_FOLDER = 'uploads' # 设定文件保存的文件夹
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'txt'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 启用 CORS (跨域资源共享)，允许您的 Vue 应用访问这个后端
# 在开发中， "*" 允许所有来源，生产环境中应设置更严格的规则
CORS(app) 

# --- 辅助函数 ---
def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- API 路由 ---
@app.route('/')
def hello():
    return "Python Uploader Backend is running!"

@app.route('/upload', methods=['POST'])
def upload_file():
    # 1. 检查 'file' 是否在请求的 files 部分
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400
    
    file = request.files['file']

    # 2. 检查文件名
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # 3. 检查文件类型并保存
    if file and allowed_file(file.filename):
        # 使用 secure_filename 防止路径遍历等安全问题
        filename = secure_filename(file.filename)
        
        # 确保 uploads 文件夹存在
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        
        return jsonify({
            "message": f"File '{filename}' uploaded successfully",
            "filename": filename
        }), 200
    else:
        return jsonify({"error": "File type not allowed"}), 400

def compare_to_answer():
    result = get_inference_result()
    upload_dir = os.path.join(os.getcwd(), "uploads")
    answer = None

    if not os.path.isdir(upload_dir):
        print(f"找不到資料夾：{upload_dir}")
    else:
        # 搜尋 .txt 檔案
        for f in os.listdir(upload_dir):
            if f.endswith(".txt"):
                answer = open(os.path.join(upload_dir, f), "r", encoding="utf-8").read().splitlines()
                
                corrected = [
                    { "filename": img, "is_correct": (user_ans == corr_ans) }
                    for (img, user_ans), corr_ans in zip(result, answer)
                ]
                print(answer)
                print(result)
                print(corrected)

                return corrected
    
    return [False] * len(result)

@app.route('/compare', methods=['POST']) # 使用 POST 保持一致性，或 GET 也可以
def get_comparison_results():
    try:
        results = compare_to_answer()
        return jsonify(results), 200
    except Exception as e:
        print(f"比對過程中發生錯誤: {e}")
        return jsonify({"error": "比對過程中發生錯誤。"}), 500        

# --- 启动服务 ---
if __name__ == '__main__':
    app.run(debug=True, port=5000) # 运行在 localhost:5000