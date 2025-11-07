import torch

print("=== PyTorch CUDA / GPU 檢測 ===")

# PyTorch 版本
print(f"PyTorch 版本: {torch.__version__}")

# 是否支援 CUDA
cuda_available = torch.cuda.is_available()
print(f"CUDA 可用: {cuda_available}")

# GPU 個數
gpu_count = torch.cuda.device_count()
print(f"偵測到 GPU 個數: {gpu_count}")

if cuda_available and gpu_count > 0:
    for i in range(gpu_count):
        print(f"GPU {i} 名稱: {torch.cuda.get_device_name(i)}")
        print(f"GPU {i} Memory (總量 MB): {torch.cuda.get_device_properties(i).total_memory / 1024**2:.2f}")
else:
    print("沒有可用 GPU 或 PyTorch 未編譯 CUDA 版本。")

# 嘗試建立一個 tensor 並移到 GPU
try:
    device = torch.device("cuda" if cuda_available else "cpu")
    x = torch.tensor([1.0, 2.0, 3.0], device=device)
    print(f"Tensor 建立在: {x.device}")
except Exception as e:
    print(f"Tensor 移動到 CUDA 時發生錯誤: {e}")
