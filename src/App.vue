<template>
  <div ref="mainContainer"> <h4>合併上傳 (TXT + data 圖片)</h4>
    <p style="color: #666;">
      請先選擇存有答案的 .txt 檔。點擊按鈕後，將上傳該 .txt 和 'data' 資料夾中的*所有*圖片，
      然後後端將回傳所有圖片的切割區域和對照答案結果顯示，錯誤顯示紅色，正確顯示綠色。
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
      {{ isUploading ? '正在處理...' : '開始上傳並比對區域' }}
    </button>
    
    <div v-if="uploadResults.length > 0" class="upload-status">
      <h5>處理日誌：</h5>
      <ul>
        <li v-for="(status, index) in uploadResults" :key="index" :class="status.status">
          <strong>{{ status.path }}</strong>: {{ status.message }}
        </li>
      </ul>
    </div>

    <div class="multi-image-container">
      <div 
        v-for="item in displayItems" 
        :key="item.filename" 
        class="image-item-wrapper"
      >
        <h4>{{ item.filename }}</h4>
        <div class="image-display-container">
          
          <img 
            v-if="item.dataUrl" 
            :src="item.dataUrl" 
            @load="onImageLoad($event, item)" 
            :ref="(el) => setImageRef(el, item.filename)"
            class="base-image"
          />
          
          <div 
            v-for="(box, index) in calculateScaledBoxes(item)" 
            :key="index" 
            :style="box.style" 
            :class="['bbox', box.is_correct ? 'correct' : 'incorrect']"
          >
          </div>
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
      uploadResults: [],
      
      // === 修改：用於顯示多張圖片的 data ===
      displayItems: [], // 格式: [{ filename, relativePath, dataUrl, regions, naturalSize, displaySize }, ...]
      imageRefs: {},    // 儲存每張圖片的 DOM 元素 { "filename.png": <img_element> }
      resizeObserver: null,
    };
  },
  
  mounted() {
    // 監聽 *主容器* 的大小變化
    this.resizeObserver = new ResizeObserver(this.updateAllDisplayedSizes);
    
    if (this.$refs.mainContainer) {
      this.resizeObserver.observe(this.$refs.mainContainer);
    }
  },
  
  beforeDestroy() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  },

  methods: {
    /**
     * 當使用者選擇 TXT 檔案時
     */
    onTxtFileSelected(event) {
      const file = event.target.files[0];
      this.selectedTxtFile = file || null;
      // 重置所有顯示
      this.uploadResults = []; 
      this.displayItems = [];
      this.imageRefs = {};
    },

    /**
     * (輔助) 設置圖片 DOM 元素的 Ref
     */
    setImageRef(el, filename) {
      if (el) {
        this.imageRefs[filename] = el;
      }
    },

    /**
     * (主要流程) - 點擊「開始上傳並比對區域」
     */
    async startCombinedUpload() {
      if (!this.selectedTxtFile) return; 

      this.isUploading = true;
      this.uploadResults = [];
      this.displayItems = [];
      this.imageRefs = {}; // 清空舊的 refs
      let allUploadStatuses = [];

      try {
        // --- 流程 1: 上傳 TXT 檔案 ---
        this.logStatus('info', 'TXT', '檔案上傳中...');
        try {
          const txtResult = await this.uploadTxtFileHelper(this.selectedTxtFile);
          allUploadStatuses.push(txtResult);
        } catch (txtError) {
          allUploadStatuses.push(txtError); 
          throw new Error('TXT 檔案上傳失敗，中止流程。');
        }

        // --- 流程 2: 獲取 data/ 圖片列表並上傳 *所有* 圖片 ---
        this.logStatus('info', 'data/', '正在獲取圖片列表...');
        const imagePaths = await window.electronAPI.listImagesInDataDir();
        
        if (imagePaths.length === 0) {
          throw new Error('在 data/ 資料夾中未找到任何圖片。');
        }

        this.logStatus('info', 'data/', `找到 ${imagePaths.length} 張圖片，開始上傳...`);
        
        const uploadPromises = imagePaths.map(path => this.uploadSingleFileHelper(path));
        const uploadResults = await Promise.allSettled(uploadPromises);

        // 處理上傳結果
        uploadResults.forEach(res => {
          allUploadStatuses.push(res.status === 'fulfilled' ? res.value : res.reason);
        });

        // 檢查是否有圖片上傳失敗
        const failedUploads = uploadResults.filter(res => res.status === 'rejected');
        if (failedUploads.length > 0) {
          this.logStatus('warn', 'Upload', `有 ${failedUploads.length} 張圖片上傳失敗，將繼續比對成功的圖片。`);
        }

        // --- 流程 3: 觸發後端比對功能 ---
        this.logStatus('info', 'Backend', '正在請求後端進行比對...');
        // 假設後端 /compare 會自動處理 uploads/ 資料夾中的所有檔案
        const response = await axios.post('http://localhost:5000/compare');
        
        // 假設 response.data 格式為: { "filename.png": [regions], ... }
        const comparisonData = response.data;
        
        if (!comparisonData || Object.keys(comparisonData).length === 0) {
           this.logStatus('info', 'Backend', '後端回傳成功，但沒有比對結果。');
           return;
        }
        
        // --- 流程 4: 建立 displayItems 陣列 ---
        this.logStatus('info', 'Frontend', '正在處理後端回傳結果...');
        
        let tempDisplayItems = [];
        for (const relativePath of imagePaths) {
          const filename = relativePath.split(/[\\/]/).pop();
          console.log(filename)
          console.log(comparisonData)
          // 檢查後端是否回傳了這張圖片的資訊
          if (comparisonData.hasOwnProperty(filename)) {
            tempDisplayItems.push({
              filename: filename,
              relativePath: relativePath,
              dataUrl: null, // 稍後載入
              regions: comparisonData[filename] || [], // 獲取區域列表
              naturalSize: { width: 1, height: 1 },
              displaySize: { width: 1, height: 1 }
            });
          }
        }
        console.log(tempDisplayItems);
        this.displayItems = tempDisplayItems; // 觸發 Vue 渲染骨架

        // --- 流程 5: 異步載入所有圖片的 Data URL ---
        if (this.displayItems.length > 0) {
          this.logStatus('info', 'Frontend', '正在載入圖片預覽...');
          const loadPromises = this.displayItems.map(async (item) => {
            try {
              const fileBuffer = await window.electronAPI.readUserDataFile(item.relativePath);
              const mimeType = this.getMimeType(item.filename) || 'application/octet-stream';
              const fileBlob = new Blob([fileBuffer], { type: mimeType });
              item.dataUrl = await this.blobToDataURL(fileBlob);
            } catch (e) {
              this.logStatus('error', item.filename, `載入預覽失敗: ${e.message}`);
              item.dataUrl = null; // 載入失敗
            }
          });
          
          await Promise.all(loadPromises);
          this.logStatus('success', 'Frontend', '所有比對結果載入完畢。');
        }

      } catch (overallError) {
        this.logStatus('error', 'Overall', overallError.message);
      } finally {
        this.uploadResults = allUploadStatuses; // 顯示最終日誌
        this.isUploading = false;
      }
    },

    /**
     * (輔助) 當 <img> 標籤載入完成時觸發
     * @param {Event} event - DOM 事件
     * @param {Object} item - displayItems 中對應的項目
     */
    onImageLoad(event, item) {
      if (!event.target) return; 
      const img = event.target;
      
      // 1. 儲存圖片的*原始*尺寸
      item.naturalSize = { 
        width: img.naturalWidth || 1, 
        height: img.naturalHeight || 1 
      };
      
      // 2. 儲存圖片在螢幕上的*當前顯示*尺寸
      item.displaySize = { 
        width: img.offsetWidth || 1, 
        height: img.offsetHeight || 1 
      };
    },
    
    /**
     * (輔助) 更新 *所有* 圖片的*顯示*尺寸 (被 ResizeObserver 呼叫)
     */
    updateAllDisplayedSizes() {
      if (!this.displayItems || this.displayItems.length === 0) return;
      
      for (const item of this.displayItems) {
        const imgEl = this.imageRefs[item.filename];
        if (imgEl) {
          item.displaySize = { 
            width: imgEl.offsetWidth || 1, 
            height: imgEl.offsetHeight || 1 
          };
        }
      }
      
      // 強制 Vue 更新 (有時需要，因為我們在更新陣列中物件的巢狀屬性)
      this.$forceUpdate();
    },

    /**
     * (新方法) 計算單一張圖片的縮放方框
     * @param {Object} item - displayItems 中對應的項目
     */
    calculateScaledBoxes(item) {
      if (!item.dataUrl || !item.regions || item.regions.length === 0) {
        return [];
      }

      const { naturalSize, displaySize, regions } = item;
      
      const scaleX = displaySize.width / naturalSize.width;
      const scaleY = displaySize.height / naturalSize.height;

      if (!isFinite(scaleX) || !isFinite(scaleY) || scaleX === 0 || scaleY === 0) {
        return [];
      }

      return regions.map(region => {
        // (x1, y1) = 左上角, (x2, y2) = 右下角
        console.log(region.position)
        const [x1_orig, y1_orig, x2_orig, y2_orig] = region.position;

        const left_orig = x1_orig;
        const top_orig = y1_orig;
        const width_orig = x2_orig - x1_orig;
        const height_orig = y2_orig - y1_orig;

        const left_scaled = left_orig * scaleX;
        const top_scaled = top_orig * scaleY;
        const width_scaled = width_orig * scaleX;
        const height_scaled = height_orig * scaleY;

        return {
          style: {
            position: 'absolute',
            top: `${top_scaled}px`,
            left: `${left_scaled}px`,
            width: `${width_scaled}px`,
            height: `${height_scaled}px`,
          },
          is_correct: region.is_correct,
        };
      });
    },

    /**
     * (輔助) 紀錄狀態
     */
    logStatus(status, path, message) {
      this.uploadResults.push({ status, path, message });
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
     * (輔助函數) 獲取 Mime Type
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
     * (輔助函數) 上傳 data 資料夾中的單一圖片
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
  max-height: 250px;
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
.multi-image-container {
  margin-top: 20px;
}
.image-item-wrapper {
  margin-bottom: 25px;
}
.image-display-container {
  position: relative; /* 關鍵：設為方框的定位基準 */
  margin-top: 20px;
  max-width: 800px; /* 限制最大寬度，您可以自行調整 */
  border: 1px solid #ccc;
  line-height: 0; /* 移除圖片底部的空隙 */
}
.base-image {
  /* 關鍵：確保圖片自適應容器寬度 */
  max-width: 100%;
  height: auto;
  display: block;
}

.bbox {
  /* 關鍵：方框使用絕對定位 */
  position: absolute; 
  box-sizing: border-box; /* 確保 border 包含在 width/height 內 */
  opacity: 0.8;
}

.bbox.correct {
  border: 2px solid #4CAF50; /* 綠色 */
  background-color: rgba(76, 175, 80, 0.2);
}

.bbox.incorrect {
  border: 2px solid #F44336; /* 紅色 */
  background-color: rgba(244, 67, 54, 0.2);
}

/* (可選) 在方框內顯示標籤 */
.bbox-label {
  position: absolute;
  top: -20px;
  left: 0;
  font-size: 10px;
  color: #fff;
  background: rgba(0,0,0,0.6);
  padding: 2px;
  white-space: nowrap;
}
</style>