"""
CPU 训练版：MNIST → 16×16 灰度 → CNN → 导出原始 float32 权重（不量化）
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
        x = self.pool1(self.relu1(self.conv1(x)))
        x = self.pool2(self.relu2(self.conv2(x)))
        x = self.flatten(x)
        x = self.relu3(self.fc1(x))
        x = self.fc2(x)
        return x


# ============================================================
# 导出原始 float32 权重
# ============================================================

def export_float_weights(params_dict, out_dir):
    """导出原始 float32 权重为文本文件，每行一个浮点数。"""
    os.makedirs(out_dir, exist_ok=True)
    for name, tensor in params_dict.items():
        arr = tensor.detach().cpu().numpy().ravel()
        filename = f"{name.replace('.', '_')}.txt"
        filepath = os.path.join(out_dir, filename)
        np.savetxt(filepath, arr, fmt='%.8f')
        print(f"  已导出: {filename}  ({len(arr)} values)")


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
    device = torch.device('cpu')
    print(f"使用设备: {device}\n")

    # 数据路径（向上取到上级MNIST目录）
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

    # 导出原始 float32 权重（不量化）
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
    print("\n导出原始 float32 权重...")
    export_float_weights(params_to_export, out_dir)

    print("\n训练和导出完成！")


if __name__ == '__main__':
    main()
