<template>
  <div>
    <input type="file" @change="handleFileChange" accept="image/*" />

    <div v-if="imageUrl">
      <h3>已上传的图片:</h3>
      <img :src="imageUrl" alt="Uploaded Image" style="max-width: 300px; max-height: 300px;" />
    </div>
    <p v-else>请选择一张图片上传。</p>
  </div>
</template>

<script>
export default {
  data() {
    return {
      imageUrl: null, // 用于存储图片的 URL 或 Data URL
    };
  },
  methods: {
    handleFileChange(event) {
      const file = event.target.files[0];
      if (!file) {
        this.imageUrl = null;
        return;
      }

      // **核心步骤：将本地图片文件转换为 Data URL 或使用 file.path**
      
      // 方案一: 使用 FileReader 转换为 Data URL (推荐，跨平台兼容性好)
      this.convertToDataURL(file);

    },

    convertToDataURL(file) {
      const reader = new FileReader();
      
      // 当文件读取成功时触发
      reader.onload = (e) => {
        // e.target.result 就是图片的 Data URL (base64 编码)
        this.imageUrl = e.target.result; 
      };

      // 以 Data URL 格式读取文件内容
      reader.readAsDataURL(file);
    }
  }
};
</script>