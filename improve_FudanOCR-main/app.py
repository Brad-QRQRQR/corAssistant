import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename # 用于获取安全的文件名
import cv2

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
        for f in os.listdir(upload_dir):
            if f.endswith(".txt"):
                answer = open(os.path.join(upload_dir, f), "r", encoding="utf-8").read().splitlines()

                unverified_result = dict()
                for img_name, user_ans in result:
                    key = img_name.split('-')[0] + ".png"
                    if key not in unverified_result:
                        unverified_result[key] = list()
                    
                    unverified_result[key].append({
                        "position": list(map(int, img_name.strip(".png").split('-')[1:])),
                        "user_ans": user_ans,
                    })

                for info in unverified_result.values():
                    info.sort(key=lambda x: (x["position"][1], x["position"][0]))
                
                corrected = dict()
                for file_name, info in unverified_result.items():
                    corrected[file_name] = [
                        {
                            "position": res["position"],
                            "is_correct": (res["user_ans"] == corr_ans),
                            "user_ans": res["user_ans"],
                            "corr_ans": corr_ans,
                        }
                        for res, corr_ans in zip(info, answer)
                    ]

                print(corrected)
                return corrected
    
    return [False] * len(result)

def split_image(name, img, info):
    for box in info:
        cx, cy, w, h = map(float, box[1:])
        x1 = int(cx * img.shape[1] - 0.5 * img.shape[1] * w)
        x2 = int(cx * img.shape[1] + 0.5 * img.shape[1] * w)
        y1 = int(cy * img.shape[0] - 0.5 * img.shape[0] * h)
        y2 = int(cy * img.shape[0] + 0.5 * img.shape[0] * h)
        crop = img[y1:y2, x1:x2]
        cv2.imwrite(os.path.join(os.getcwd(), "judge_data", "-".join([name, str(x1), str(y1), str(x2), str(y2)])+ ".png"), crop)

def process():
    upload_dir = os.path.join(os.getcwd(), "uploads")
    yolo_dir = os.path.join(os.getcwd(), "yolo_result")
    judge_dir = os.path.join(os.getcwd(), "judge_data")
    img_suf = ALLOWED_EXTENSIONS.difference({"txt"})
    yolo_info = dict()

    for filename in os.listdir(yolo_dir):
        yolo_info[filename.split('.')[0] + ".png"] = [line.split(' ') for line in open(os.path.join(yolo_dir, filename), "r", encoding="utf-8").read().splitlines()]

    for filename in os.listdir(judge_dir):
        file_path = os.path.join(judge_dir, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"無法刪除檔案：{e}")


    for filename in os.listdir(upload_dir):
        if all(filename.endswith(suffix) is False for suffix in img_suf):
            continue
        print(filename)
        split_image(filename.split('.')[0], cv2.imread(os.path.join(upload_dir, filename)), yolo_info[filename])
        

@app.route('/compare', methods=['POST']) # 使用 POST 保持一致性，或 GET 也可以
def get_comparison_results():
    try:
        process()
        results = compare_to_answer()
        return jsonify(results), 200
    except Exception as e:
        print(f"比對過程中發生錯誤: {e}")
        return jsonify({"error": "比對過程中發生錯誤。"}), 500   

# --- 启动服务 ---
if __name__ == '__main__':
    app.run(debug=True, port=5000) # 运行在 localhost:5000