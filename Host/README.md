# 上位机 — 画 28×28 数字，串口让 FPGA 识别

单文件 tkinter 程序：画板上写数字 → 预处理成 28×28 uint8 → 串口发给
**FPGA 上的 CNN**（`../FPGA_CNN/`）→ 回传 10 个类别的 logit / 置信度。

## 运行

```bash
python mnist_host.py                 # 图形界面，连 FPGA
python mnist_host.py --sim           # 仿真模式（不需要硬件）
python mnist_host.py --model D:/.../weights/x28   # 指定模型目录
```

依赖：Python 3.8+、tkinter（Windows 自带）、`pip install pyserial`（仅真串口
需要）、numpy（仿真模式和自检需要，训练环境已装）。

自检（无窗口、无硬件）：

```bash
python selftest.py
# crc16 CCITT-FALSE vector OK
# frame build/parse/CRC-reject OK
# SimBoard LOAD_IMAGE/INFER/READ_SCORES OK
# preprocess OK (bbox 20 px, centre of mass 13.5,13.0)
# model28 matches the exported RTL vectors (8/8)
# softmax OK
# SELFTEST PASS
```

## 使用流程

1. 选串口、**921600**（与当前比特流一致；旧版 115200 的 .sof 要改成 115200），
   点"连接"。
2. 如果对端是 FPGA CNN（PING 返回 `CNN28-FPGA`），程序会**自动下载模型**
   （15,792 字节，约 1.4 s）。也可以随时点"下载模型"重发。
3. 在左侧画数字，点"识别"（或 `Ctrl+Enter`）。
4. 右侧 10 条置信度条由 logits 做 softmax 得到，红色是 argmax。
5. 勾选"实时"后，画的过程中就以最高约 30 帧/秒持续把当前画面发给 FPGA，
   松开鼠标也会保留最后一帧的结果，不用再点"识别"。

```
┌─ 串口 ─ [COM5 ▾] 115200 [连接] [下载模型] ☐仿真模式 ─── 状态 ─┐
│ ┌──────────────┐  ┌────────┐  ┌─ 置信度 ────────────────┐ │
│ │   画板       │  │28×28   │  │ 0 ██░░░░░░░░░░   3.1%   │ │
│ │  280×280     │  │输入预览│  │ 1 ████████████  91.2%   │ │
│ └──────────────┘  └────────┘  │ 结果：1                 │ │
│ [清空] 笔刷 ───●──  [实时☐][温度 3] [识别] └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 图像预处理

与训练时一致（`FPGA_CNN/train_export.py`）：

1. 280×280 画布 → 10×10 盒式平均 → 28×28 灰度；
2. 墨迹包围盒长边缩放到 **20 px**（双线性）；
3. 按**质心**居中到 28×28 中心（MNIST 的 20×20 居中口径）；
4. 取整到 0..255，按行优先得到 784 字节。

"归一化（20px 居中）"可以关掉第 2、3 步做对比。

## 与 FPGA 的协议

```
上位机 → FPGA : A5 5A | CMD | LEN_L LEN_H | PAYLOAD | CRC_L CRC_H
FPGA → 上位机 : 5A A5 | STAT | LEN_L LEN_H | PAYLOAD | CRC_L CRC_H
```

CRC-16/CCITT-FALSE，覆盖 CMD/STAT + 长度 + 负载。命令：

| CMD | 名称 | 负载 | 响应 |
|-----|------|------|------|
| 0x01 | PING | — | `"CNN28-FPGA"` |
| 0x02 | LOAD_IMAGE | 784 B | `01` |
| 0x03 | INFER | — | 40 B logits + result + errcode + flags |
| 0x04 | READ_SCORES | — | 40 B logits |
| 0x05 | RESET | — | `01` |
| 0x06 | STATUS | — | flags + result + errcode |
| 0x07 | LOAD_MEM | `sel,addrL,addrH,nL,nH,data` | `01` |
| 0x08 | READ_MEM | `sel,addrL,addrH,nL,nH` | n B（n ≤ 64） |

FPGA 的 sel 映射：0=图像(784) 1=conv1 权重(200) 2=conv2(1152) 3=fc1(12800)
4=fc2(320) 5=偏置(264) 6=logits(40，只读) 7=qparam(1056)。
`Link.load_model()` 按这个映射把 `weights/x28/model.bin` 分块下载（500 B/帧）。

FPGA 的回复缓冲是 64 B，所以 `READ_MEM` 单次最多读 64 B；`LOAD_MEM` 单帧负载
上限 1019 B（1 KiB 帧缓冲减 5 B 头）。

INFER 的 40 字节是 10 个 **int32 小端** logit（FC2 的定点输出，同一比较
尺度），后 3 字节是 `result`、`error_code`、`flags`
（bit0=RESULT_VALID，bit1=ERROR，bit2=DONE）。

## 置信度怎么读

FC2 输出的是 **int32 定点 logit**（数量级几万），直接做 softmax 会全部下溢成
0，只剩最大值 100%——这是之前"非 0 即 100"的原因。现在做了两件事：

1. **反量化**：用 `metadata.json` 里 fc2 的 `scale_in × s_w[c]` 把 logit 还原成
   浮点量级（`Host/protocol.py:load_output_scales`）；
2. **显示温度**：工具栏的"温度"把 logit 再除以 T（默认 3），让次优类也能看见。

日志里的"真实置信度 xx.xx%"是 **T=1** 的原始 softmax，也就是模型本来的把握；
置信度条是 T=3 的显示值。这个模型在 MNIST 上很自信，真实置信度经常是 99.9x%，
所以想比较各类差异就把温度调大（4~6）。

## 实时识别

勾选"实时"后，串口 I/O 全部放进一个后台线程，UI 只负责把最新画面丢进队列：

* 绘制事件把 `dirty` 置位，12 ms 的定时器在空闲时提交当前帧；
* 队列只保留最新一帧（画面更新快时自动丢旧帧）；
* 上限 50 帧/秒，实际速率由链路决定：921600 时单帧往返约 20.7 ms ≈ 48 帧/秒，
  Tk 定时器（约 15.6 ms 粒度）把实际刷新限制在 **30 帧/秒**左右；
* 实时模式下日志每秒最多一条，不会刷屏。

## 仿真模式

`protocol.SimBoard` 在进程内实现同一套协议，并且**执行与 RTL 位精确一致的
整数模型**（`model28.py`，纯 NumPy）。所以 `--sim` 是真的能识别数字的，
不是占位符：它和 FPGA 的唯一区别是速度（毫秒 vs 11 ms 推理 + 串口传输）。

如果 `weights/x28` 不存在，仿真模式退回全 0 分数并在日志里说明。

## 常见问题

| 现象 | 原因/处理 |
|------|-----------|
| 串口下拉框为空 | 没装 pyserial，或驱动未识别 |
| PING 失败：`0.05` | 旧版上位机的 bug（把读超时当成了读取字节数），已修；更新 `protocol.py` 即可 |
| PING 失败（其它） | 波特率不对、TX/RX 未交叉、FPGA 未配置；现在日志会带异常类型 |
| 连上但识别结果全 0 | 模型没下载成功（看日志），或 PING 不是 `CNN28` |
| 下载模型失败 STAT=6 | 分块地址越界（模型文件与 RTL 的 sel 大小不匹配） |
| 推理 STAT=4 | FPGA 3 s 内没有 done：检查时钟/复位 |
| 结果总是同一类 | 画得太小或太偏；归一化会把墨迹拉满 20 px，尽量写满画板 |
| 仿真模式无模型 | `weights/x28` 不存在，先跑 `FPGA_CNN/train_export.py` |

## 文件

| 文件 | 内容 |
|------|------|
| `mnist_host.py` | 界面、绘图、预处理、串口/仿真连接、模型下载 |
| `protocol.py` | 帧格式、CRC、`SerialLink`、`SimBoard`、`load_model`、softmax |
| `model28.py` | 28×28 整数推理参考模型（与 RTL 位精确） |
| `selftest.py` | 无界面自检 |
