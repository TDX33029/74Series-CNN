"""
GPU 训练版：MNIST → 16×16 灰度 → CNN → 量化权重导出
优先使用 GPU（CUDA），fallback 到 CPU
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import struct
import os


# ============================================================
# 数据加载
# ============================================================

def read_idx_images(filepath):
    with open(filepath, 'rb') as f:
        magic, num, rows, cols = struct.unpack('>IIII', f.read(16))
        assert magic == 2051, f"Magic number mismatch: {magic}"
        data = np.frombuffer(f.read(), dtype=np.uint8)
        return data.reshape(num, rows, cols)


def read_idx_labels(filepath):
    with open(filepath, 'rb') as f:
        magic, num = struct.unpack('>II', f.read(8))
        assert magic == 2049, f"Magic number mismatch: {magic}"
        return np.frombuffer(f.read(), dtype=np.uint8)


class MNIST16Dataset(Dataset):
    def __init__(self, image_path, label_path):
        images = read_idx_images(image_path)
        labels = read_idx_labels(label_path)

        import torch.nn.functional as F
        imgs_tensor = torch.from_numpy(images).float().unsqueeze(1)
        imgs_16 = F.interpolate(imgs_tensor, size=(16, 16), mode='bilinear', align_corners=False)
        self.images = (imgs_16 / 255.0 * 63.0).to(torch.float32)
        self.labels = torch.from_numpy(labels).long()

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.images[idx], self.labels[idx]


# ============================================================
# 网络定义
# ============================================================

class SimpleCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels=1, out_channels=3,
                               kernel_size=3, stride=1, padding=1)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv2 = nn.Conv2d(in_channels=3, out_channels=8,
                               kernel_size=3, stride=1, padding=1)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(128, 36)
        self.relu3 = nn.ReLU()
        self.fc2 = nn.Linear(36, 10)

    def forward(self, x):
        x = self.pool1(self.relu1(self.conv1(x)))   # [B, 3, 8, 8]
        x = self.pool2(self.relu2(self.conv2(x)))   # [B, 8, 4, 4]
        x = self.flatten(x)                          # [B, 128]
        x = self.relu3(self.fc1(x))                  # [B, 36]
        x = self.fc2(x)                              # [B, 10]
        return x


# ============================================================
# 量化与导出
# ============================================================

def quantize_weights(params_dict, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    all_values = []
    weight_names = [k for k in params_dict.keys() if 'weight' in k]
    for name in weight_names:
        all_values.append(params_dict[name].detach().cpu().numpy().ravel())

    all_weights = np.concatenate(all_values)
    max_abs = np.max(np.abs(all_weights))
    scale = 31.0 / max_abs
    print(f"\n量化信息:")
    print(f"  权重绝对值最大值: {max_abs:.6f}")
    print(f"  缩放因子 scale: {scale:.6f}")

    q_dict = {}
    for name, tensor in params_dict.items():
        arr = tensor.detach().cpu().numpy().ravel()
        q_arr = np.round(arr * scale).astype(np.int32)
        q_arr = np.clip(q_arr, -32, 31)

        q_dict[name] = q_arr

        filename = f"{name.replace('.', '_')}.txt"
        filepath = os.path.join(out_dir, filename)
        np.savetxt(filepath, q_arr, fmt='%d')
        print(f"  已导出: {filename}  ({len(q_arr)} values)")

    return q_dict, scale


def dequantize_params(q_dict, scale):
    dq_dict = {}
    for name, q_arr in q_dict.items():
        dq_dict[name] = q_arr.astype(np.float32) / scale
    return dq_dict


def apply_params_to_model(model, params_dict):
    state_dict = model.state_dict()
    for name, arr in params_dict.items():
        orig_shape = state_dict[name].shape
        state_dict[name] = torch.from_numpy(arr.reshape(orig_shape))
    model.load_state_dict(state_dict)


# ============================================================
# 评估函数
# ============================================================

def evaluate(model, loader, device):
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    return correct / total


# ============================================================
# 主函数
# ============================================================

def main():
    # 优先使用 GPU，fallback 到 CPU
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"使用设备: {device}")
    if device.type == 'cuda':
        print(f"  GPU 名称: {torch.cuda.get_device_name(0)}")
    print()

    # 数据路径
    data_dir = os.path.join('..', 'MNIST')
    train_img_path = os.path.join(data_dir, 'train-images-idx3-ubyte', 'train-images.idx3-ubyte')
    train_lbl_path = os.path.join(data_dir, 'train-labels-idx1-ubyte', 'train-labels.idx1-ubyte')
    test_img_path  = os.path.join(data_dir, 't10k-images-idx3-ubyte', 't10k-images.idx3-ubyte')
    test_lbl_path  = os.path.join(data_dir, 't10k-labels-idx1-ubyte', 't10k-labels.idx1-ubyte')

    # 数据集
    train_dataset = MNIST16Dataset(train_img_path, train_lbl_path)
    test_dataset  = MNIST16Dataset(test_img_path, test_lbl_path)

    train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
    test_loader  = DataLoader(test_dataset,  batch_size=64, shuffle=False)

    print(f"训练集: {len(train_dataset)} 张图片")
    print(f"测试集: {len(test_dataset)} 张图片")

    # 模型
    model = SimpleCNN().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # 训练
    num_epochs = 20
    print("\n开始训练...")
    for epoch in range(1, num_epochs + 1):
        model.train()
        running_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * images.size(0)

        epoch_loss = running_loss / len(train_dataset)
        train_acc = evaluate(model, train_loader, device)
        test_acc  = evaluate(model, test_loader, device)
        print(f"Epoch [{epoch:2d}/{num_epochs}]  "
              f"Loss: {epoch_loss:.4f}  "
              f"Train Acc: {train_acc:.4f}  "
              f"Test Acc: {test_acc:.4f}")

    # 导出量化权重
    out_dir = 'exported_weights'
    params_to_export = {
        'conv1.weight': model.conv1.weight,
        'conv1.bias':   model.conv1.bias,
        'conv2.weight': model.conv2.weight,
        'conv2.bias':   model.conv2.bias,
        'fc1.weight':   model.fc1.weight,
        'fc1.bias':     model.fc1.bias,
        'fc2.weight':   model.fc2.weight,
        'fc2.bias':     model.fc2.bias,
    }

    q_dict, scale = quantize_weights(params_to_export, out_dir)

    # 量化后精度验证
    print("\n验证量化后精度（反量化权重重新测试）...")
    dq_dict = dequantize_params(q_dict, scale)
    q_model = SimpleCNN().to(device)
    apply_params_to_model(q_model, dq_dict)
    q_test_acc = evaluate(q_model, test_loader, device)
    print(f"量化前测试准确率: {test_acc:.4f}")
    print(f"量化后测试准确率: {q_test_acc:.4f}")
    print(f"精度变化: {q_test_acc - test_acc:+.4f}")

    print("\n训练和导出完成！")


if __name__ == '__main__':
    main()
