<template>
  <div>
    <h4>合併上傳 (TXT + data 圖片)</h4>
    <p style="color: #666;">
      請先選擇一個 .txt 檔案。點擊下方按鈕後，將會先上傳您選擇的 .txt 檔案，
      接著自動上傳 'data' 資料夾中的所有圖片。上傳完成後，將會顯示每張圖片的比對結果。
    </p>

    <div class="step-one">
      <label>1. 選擇 TXT 檔案 (必須)：</label>
      <input 
        type="file" 
        @change="onTxtFileSelected" 
        accept=".txt, text/plain" 
        style="margin-left: 10px;"
      />
    </div>

    <button 
      @click="startCombinedUpload" 
      :disabled="!selectedTxtFile || isUploading"
      class="upload-button"
    >
      {{ isUploading ? '正在處理...' : '開始合併上傳並比對' }}
    </button>
    
    <div v-if="uploadResults.length > 0" class="upload-status">
      <h5>上傳/處理狀態：</h5>
      <ul>
        <li v-for="(status, index) in uploadResults" :key="index" :class="status.status">
          <strong>{{ status.path }}</strong>: {{ status.message }}
        </li>
      </ul>
    </div>

    <div v-if="comparisonResults.length > 0" class="comparison-display">
      <h5>圖片比對結果：</h5>
      <div class="image-grid">
        <div 
          v-for="item in comparisonResults" 
          :key="item.filename" 
          :class="['image-item', { 'correct-border': item.is_correct, 'incorrect-border': !item.is_correct }]"
        >
          <img :src="item.dataUrl" :alt="item.filename" />
          <p>{{ item.filename }}</p>
          <p :class="{ 'text-correct': item.is_correct, 'text-incorrect': !item.is_correct }">
            {{ item.is_correct ? '✔ 正確' : '✘ 錯誤' }}
          </p>
        </div>
      </div>
    </div>

  </div>
</template>

<script>
import axios from 'axios';

export default {
  data() {
    return {
      selectedTxtFile: null, 
      isUploading: false,      
      uploadResults: [],     // 儲存所有上傳任務的日誌
      comparisonResults: [], // 儲存比對結果，包含圖片 dataUrl
    };
  },
  methods: {
    /**
     * 當使用者選擇 TXT 檔案時
     */
    onTxtFileSelected(event) {
      const file = event.target.files[0];
      if (file) {
        this.selectedTxtFile = file;
      } else {
        this.selectedTxtFile = null;
      }
      this.uploadResults = []; 
      this.comparisonResults = []; // 清空比對結果
    },

    /**
     * (主要流程) - 點擊「開始合併上傳並比對」時觸發
     */
    async startCombinedUpload() {
      if (!this.selectedTxtFile) return; 

      this.isUploading = true;
      this.uploadResults = []; 
      this.comparisonResults = []; // 每次開始都清空
      let allUploadStatuses = []; // 暫存所有上傳的結果
      let allImagePaths = []; // 暫存所有上傳的圖片路徑，用於後續獲取 dataUrl

      try {
        // --- 流程 1: 上傳 TXT 檔案 ---
        this.uploadResults.push({ path: this.selectedTxtFile.name, status: 'info', message: 'TXT 檔案上傳中...' });
        try {
          const txtResult = await this.uploadTxtFileHelper(this.selectedTxtFile);
          allUploadStatuses.push(txtResult);
        } catch (txtError) {
          allUploadStatuses.push(txtError); // TXT 上傳失敗
          // 如果 TXT 檔案上傳失敗，可能後續比對也無意義，這裡可選擇停止或繼續
          // 為了演示，我們繼續，但記錄錯誤
          console.error("TXT 檔案上傳失敗，但繼續處理圖片:", txtError);
        }
        this.uploadResults = [...allUploadStatuses]; // 更新 UI 顯示 TXT 結果

        // --- 流程 2: 上傳 data 資料夾中的所有圖片 ---
        this.uploadResults.push({ path: 'data/', status: 'info', message: '正在獲取圖片列表...' });
        const imagePaths = await window.electronAPI.listImagesInDataDir();
        allImagePaths = imagePaths; // 儲存所有圖片的相對路徑

        if (imagePaths.length === 0) {
          allUploadStatuses.push({ path: 'data/', status: 'info', message: '未找到圖片，跳過上傳。' });
        } else {
          const uploadPromises = imagePaths.map(path => this.uploadSingleFileHelper(path));
          const imageUploadResults = await Promise.allSettled(uploadPromises);
          imageUploadResults.forEach(res => {
            allUploadStatuses.push((res.status === 'fulfilled') ? res.value : res.reason);
          });
        }
        this.uploadResults = [...allUploadStatuses]; // 更新 UI 顯示圖片上傳結果
        
        // --- 流程 3: 觸發後端比對功能 ---
        if (allImagePaths.length > 0 || this.selectedTxtFile) { // 至少有圖片或txt才去比對
          this.uploadResults.push({ path: 'Backend', status: 'info', message: '正在請求後端進行比對...' });
          const response = await axios.post('http://localhost:5000/compare'); // 呼叫新的比較 API
          const backendComparisonResults = response.data; // 得到後端回傳的 [(filename, is_correct), ...]

          // --- 流程 4: 獲取圖片 Data URL 並顯示 ---
          if (backendComparisonResults && backendComparisonResults.length > 0) {
            this.uploadResults.push({ path: 'Frontend', status: 'info', message: '正在獲取本地圖片預覽...' });
            const previewPromises = backendComparisonResults.map(async item => {
              try {
                // 從原始的 allImagePaths 找到對應的相對路徑
                const relativePath = allImagePaths.find(p => p.endsWith(item.filename));
                if (relativePath) {
                  const fileBuffer = await window.electronAPI.readUserDataFile(relativePath);
                  const mimeType = this.getMimeType(item.filename) || 'application/octet-stream';
                  const fileBlob = new Blob([fileBuffer], { type: mimeType });
                  const dataUrl = await this.blobToDataURL(fileBlob); // 將 Blob 轉換為 Data URL
                  return {
                    filename: item.filename,
                    is_correct: item.is_correct,
                    dataUrl: dataUrl
                  };
                } else {
                  // 如果找不到對應的圖片，可能該圖片上傳失敗了
                  return { filename: item.filename, is_correct: item.is_correct, dataUrl: '' };
                }
              } catch (previewError) {
                console.error(`獲取圖片預覽失敗 (${item.filename}):`, previewError);
                return { filename: item.filename, is_correct: item.is_correct, dataUrl: '' }; // 預覽失敗
              }
            });
            this.comparisonResults = await Promise.all(previewPromises);
            this.uploadResults.push({ path: 'Frontend', status: 'success', message: '所有圖片比對結果已顯示。' });
          } else {
            this.uploadResults.push({ path: 'Backend', status: 'info', message: '後端未回傳比對結果或沒有圖片可比對。' });
          }
        } else {
          this.uploadResults.push({ path: 'Process', status: 'info', message: '沒有任何檔案被上傳或比對。' });
        }

      } catch (overallError) {
        console.error("合併上傳或比對過程中發生總體錯誤:", overallError);
        allUploadStatuses.push({ 
          path: 'Overall', 
          status: 'error', 
          message: `處理過程中發生錯誤: ${overallError.message}` 
        });
      } finally {
        this.isUploading = false;
        this.uploadResults = [...allUploadStatuses]; // 確保最終狀態更新
      }
    },

    /**
     * (輔助函數) 上傳單一 TXT 檔案
     */
    async uploadTxtFileHelper(file) {
      const formData = new FormData();
      formData.append('file', file, file.name);
      try {
        const response = await axios.post('http://localhost:5000/upload', formData);
        return { path: file.name, status: 'success', message: response.data.message };
      } catch (error) {
        let errorMessage = error.message;
        if (error.response && error.response.data && error.response.data.error) {
          errorMessage = error.response.data.error;
        } else if (error.request) {
          errorMessage = '無法連接伺服器。';
        }
        throw { path: file.name, status: 'error', message: `上傳失敗: ${errorMessage}` };
      }
    },

    /**
     * (輔助函數) 上傳 data 資料夾中的單一圖片
     */
    async uploadSingleFileHelper(filePath) {
      try {
        const fileBuffer = await window.electronAPI.readUserDataFile(filePath);
        if (!fileBuffer) throw new Error('檔案內容為空。');

        const mimeType = this.getMimeType(filePath) || 'application/octet-stream';
        const fileBlob = new Blob([fileBuffer], { type: mimeType });
        const formData = new FormData();
        const simpleFilename = filePath.split(/[\\/]/).pop() || 'uploaded_file';
        formData.append('file', fileBlob, simpleFilename);
        
        const response = await axios.post('http://localhost:5000/upload', formData);
        return { path: filePath, status: 'success', message: response.data.message };
      } catch (error) {
        let errorMessage = error.message;
        if (error.response && error.response.data && error.response.data.error) {
          errorMessage = error.response.data.error;
        } else if (error.request) {
          errorMessage = '無法連接伺服器。';
        }
        throw { path: filePath, status: 'error', message: `上傳失敗: ${errorMessage}` };
      }
    },

    /**
     * (輔助函數) 獲取 Mime Type
     */
    getMimeType(filename) {
      const ext = (filename.split('.').pop() || '').toLowerCase();
      if (ext === 'png') return 'image/png';
      if (ext === 'jpg' || ext === 'jpeg') return 'image/jpeg';
      if (ext === 'gif') return 'image/gif';
      if (ext === 'webp') return 'image/webp';
      return null;
    },

    /**
     * (輔助函數) 將 Blob 轉換為 Data URL
     */
    blobToDataURL(blob) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    }
  }
};
</script>

<style scoped>
.step-one {
  background-color: #f4f4f4;
  padding: 15px;
  border-radius: 5px;
  border: 1px dashed #ccc;
  margin-bottom: 15px;
}
.upload-button {
  margin-top: 15px;
  font-size: 16px;
  padding: 10px 15px;
}
.upload-status {
  margin-top: 15px;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  max-height: 200px;
  overflow-y: auto;
  background-color: #f9f9f9;
}
.upload-status ul {
  list-style: none;
  padding: 0;
  margin: 0;
}
.upload-status li {
  padding: 3px 0;
  border-bottom: 1px solid #eee;
}
.upload-status li.success {
  color: green;
}
.upload-status li.error {
  color: red;
}
.upload-status li.info {
  color: #555;
}

.comparison-display {
  margin-top: 20px;
  padding: 15px;
  border: 1px solid #aaddaa;
  background-color: #eaffea;
  border-radius: 8px;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 15px;
  margin-top: 10px;
}

.image-item {
  border: 3px solid transparent; /* 預設透明邊框 */
  padding: 5px;
  border-radius: 8px;
  text-align: center;
  overflow: hidden; /* 防止圖片溢出邊框 */
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  background-color: #fff;
}

.image-item img {
  max-width: 100%;
  height: auto;
  display: block; /* 移除圖片底部的空白 */
  margin: 0 auto 5px;
  max-height: 100px; /* 限制圖片高度 */
  object-fit: contain; /* 確保圖片不變形 */
}

.image-item p {
  margin: 0;
  font-size: 0.9em;
  word-break: break-all; /* 長檔名可以斷行 */
  padding: 2px 0;
}

.correct-border {
  border-color: #4CAF50; /* 綠色 */
}

.incorrect-border {
  border-color: #F44336; /* 紅色 */
}

.text-correct {
  color: #4CAF50;
  font-weight: bold;
}

.text-incorrect {
  color: #F44336;
  font-weight: bold;
}
</style>