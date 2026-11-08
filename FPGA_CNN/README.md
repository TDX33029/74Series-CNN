# FPGA_CNN — 在 EP4CE10 上直接运行 28×28 CNN

这条路径让 **FPGA 自己完成推理**：图像从串口进来 → FPGA 做全部卷积/池化/全连接 →
回传 10 个 logit。它不经过 74 系列板，也不需要 EEPROM、下载器或任何外部存储。

> 与 `FPGA_Bridge/` 的区别：bridge 是"FPGA 当 74 系列板的下载器/连接器"（可选，
> 用于和 74 系列硬件对照）；本目录是"FPGA 就是 CNN 加速器"，用来先验证算法和
> 量化方案本身跑得通。

## 1. 网络与量化

拓扑（与 `CNN_74xx_MNIST_28x28_v1.txt` 一致）：

```
28×28×1 u8 → conv 5×5 1→8 (valid) → ReLU → pool 2×2 → 12×12×8
           → conv 3×3 8→16        → ReLU → pool 2×2 → 5×5×16 = 400
           → fc 400→32 → ReLU → fc 32→10 → argmax
```

243,520 次 MAC/推理，全部参数 15,792 B，全部放片上，不需要 SDRAM。

量化契约（`train_export.py` 与 RTL 逐位一致）：

```
ACC = Σ(q_x·q_w) − zp_w·Σ(q_x) + bias_int32      zp_w = 128, zp_x = 0
q   = clamp((ACC·M + 2^(S−1)) >> S, 0, 255)      conv / pool / fc1
logit = (ACC·M + 2^(S−1)) >> S                   fc2，int32，不 clamp
```

* 权重 uint8 = int8 + 128，逐输出通道对称缩放，M 为 16 bit、S ≤ 63；
* 每神经元一条 16 B qparam 记录：`zp_in, zp_w, zp_out, flags, M(4B LE), S`；
* 激活零点为 0，偏置已折算到 int32 累加器域。

训练结果（`train_export.py`，12 epoch，MNIST 官方测试集）：

| 模型 | 准确率 |
|------|--------|
| 浮点 | 98.56 % |
| int8 + 上述重量化 | **98.54 %** |

## 2. 存储器映射

核内是一条 16 位字节地址空间、单字节读写口，主机和 CNN 核分时复用：

| 区段 | 基址 | 容量 | 用途 | 主机 sel |
|------|------|------|------|----------|
| IMG | `0x0000` | 1024 | 28×28 输入（用 784） | 0 |
| W1 | `0x0400` | 512 | conv1 权重 8×25 | 1 |
| W2 | `0x0600` | 1280 | conv2 权重 16×8×9 | 2 |
| W3 | `0x0B00` | 12800 | fc1 权重 32×400 | 3 |
| W4 | `0x3D00` | 512 | fc2 权重 10×32 | 4 |
| C1 | `0x4000` | 4608 | conv1 输出 8×24×24 | — |
| P1 | `0x5200` | 1280 | pool1 输出 8×12×12 | — |
| C2 | `0x5700` | 1792 | conv2 输出 16×10×10 | — |
| P2 | `0x5E00` | 512 | pool2 输出 16×5×5 | — |
| F1 | `0x6000` | 64 | fc1 输出 32 | — |
| LOG | `0x6100` | 64 | 10×int32 logit（只读） | 6 |
| BIAS | `0x6200` | 264 | 32+64+128+40 B 偏置 | 5 |
| QP | `0x6400` | 1088 | 每神经元 16 B qparam | 7 |

sel 5 的 264 B 是 `conv1[:32] + conv2[:64] + fc1[:128] + fc2[:40]` 拼接，顺序与
`metadata.json` 的 section 顺序一致。

## 3. 串口协议

```
上位机 → FPGA : A5 5A | CMD | LEN_L LEN_H | PAYLOAD | CRC_L CRC_H
FPGA → 上位机 : 5A A5 | STAT | LEN_L LEN_H | PAYLOAD | CRC_L CRC_H
```

CRC-16/CCITT-FALSE（poly `0x1021`，init `0xFFFF`），覆盖 CMD/STAT + 长度 + 负载。

| CMD | 名称 | 负载 | 回复 |
|-----|------|------|------|
| 0x01 | PING | — | `"CNN28-FPGA"` |
| 0x02 | LOAD_IMAGE | 784 B | `01` |
| 0x03 | INFER | — | 40 B logits + result + errcode + flags |
| 0x04 | READ_SCORES | — | 40 B logits |
| 0x05 | RESET | — | `01` |
| 0x06 | STATUS | — | flags + result + errcode |
| 0x07 | LOAD_MEM | `sel, addrL, addrH, nL, nH, data` | `01` |
| 0x08 | READ_MEM | `sel, addrL, addrH, nL, nH` | n B（**n ≤ 64**） |

约束：单帧负载 ≤ 1024 B（含 5 B 头），回复缓冲 64 B，所以 `READ_MEM` 一次最多读
64 B，`LOAD_MEM` 一次最多写 1019 B。模型下载由上位机按 500 B 分块，约 1.4 s。

INFER 的 43 B：10 个 **int32 小端** logit（同一比较尺度）+ `result`、
`error_code`、`flags`（bit0 有效，bit1 错误，bit2 完成）。

## 4. RTL 结构

```
uart_rx ─┐
         ├─ cnn28_top ── 帧解析/CRC/命令执行 ──┬─ 16 位字节存储口 ── cnn28_core
uart_tx ─┘                                    └─ rxb(1024×8) / txb(64 B)
```

* **cnn28_core**：13 个简单双口 RAM（每区一个 M9K），一条共享字节口；FSM
  `SETUP → TERM(×N) → REQ → MUL → SH → WR`，每 MAC 2 拍（ph1 取激活、ph2 累加并
  取权重）。重量化拆成 `MUL`（32×16 乘）→ `SH`（64 位舍入右移）→ `WR`（clamp），
  这样 64 位变长移位不落在写 RAM 的数据通路上。
* **cnn28_top**：帧缓冲 `rxb` 用寄存器读口（地址比数据早一拍，`X_WRP/X_WR2`
  两态流水）；`txb` 只有 64 B，用寄存器实现，避免 1024:1 读 mux。
* 时钟 50 MHz，1 拍/字节的串口收发，无跨时钟域；
* 串口波特率是 `cnn28_top` 的参数 `BAUD`，当前比特流按 **921600** 编译
  （分频 54 → 925.9 kbaud，误差 0.47 %），上位机需选同一个值。

## 5. 综合与时序（EP4CE10F17C8，Quartus 18.0 Standard）

| 资源 | 用量 |
|------|------|
| Logic elements | **3,785 / 10,320（37 %）** |
| LAB | 284 / 645（44 %） |
| 寄存器 | 1,339 |
| M9K | **40 / 46（87 %）** |
| 存储位 | 218,112 / 423,936（51 %） |
| 嵌入式乘法器 | 2×18×18 + 1×9×9（5/46 个 9 位单元） |
| Fmax（slow 85 °C） | **54.8 MHz** |
| Fmax（slow 0 °C） | 58.6 MHz |
| Setup slack @50 MHz | **+1.751 ns** |
| Hold slack | +0.451 ns |

时序以 50 MHz 约束收敛。M9K 已用 87 %，再加缓存/多帧缓冲前要先算存储；逻辑侧
还有一半余量。

性能：

* 推理 **571,443 周期 = 11.43 ms @50 MHz**（流水化重量化后比原来多 6,250 拍），
  纯算力上限 **87.5 次/秒**；
* 端到端（8N1，一帧 = 上传 784 B + 推理 + 回传 43 B）：

  | 波特率 | 每帧 | 速率 |
  |--------|------|------|
  | 115200 | 85.7 ms | 11.7 次/秒 |
  | 460800 | 30.0 ms | 33.3 次/秒 |
  | **921600（当前）** | **20.7 ms** | **48.3 次/秒** |

  上限在串口，不在 CNN：上传 784 B 在 115200 下就要 68.7 ms。

## 6. 验证

| 测试 | 内容 | 结果 |
|------|------|------|
| `tb/tb_cnn28_core.v` | 8 张图（每类一张），逐位比对 10 个 logit + argmax | PASS 8/8 |
| `tb/tb_cnn28_top.v` | PING、15,792 B 模型下载、LOAD_IMAGE、INFER、READ_SCORES、STATUS、坏 CRC | PASS 13 项 |
| `Host/selftest.py` | CRC、帧、SimBoard、预处理、model28 与 RTL 向量一致 | PASS |
| 上位机联调 | 画"1"→ 结果 1（logit 16,422） | 通过 |

`model28.py` 是与 RTL 逐位一致的 NumPy 参考实现，`--sim` 模式就是用它，所以仿真
模式能真的识别数字，不是占位符。

## 7. 上板

1. 打开 `quartus/cnn28.qpf`（器件已设为 EP4CE10F17C8）。
2. **必须显式分配引脚**。工程里没有位置约束时 Quartus 每次编译都会自己挑脚，
   而且每次结果都不一样——UART 没落在你接的那两个脚上就是 `PING 超时`。

   | 信号 | 方向 | 说明 |
   |------|------|------|
   | `clk` | in | 50 MHz 时钟，取自板子晶振；频率不是 50 MHz 时改 `cnn28_top` 的 `CLK_HZ` 和 `cnn28.sdc` |
   | `rst_n` | in | 可选。给 `--rst` 时是低有效外部复位；不给就定义 `NO_EXT_RESET`，改用内部上电复位，端口不存在 |
   | `uart_rx` | in | 接 USB-UART 的 TX |
   | `uart_tx` | out | 接 USB-UART 的 RX |
   | `led` | out | 可选，约 1.5 Hz 心跳，用来确认设计在跑（需要定义 `LED_HEARTBEAT`） |

   命令行的做法：

   ```bash
   cd quartus
   python set_pins.py --clk E1 --rx R1 --tx T1 --rst M2 [--led P9]
   ```

   它会把这几个 `set_location_assignment` 写进 `cnn28.qsf`（带标记，重复运行会
   覆盖旧值）然后自动跑一遍全编译；`--show` 查看当前设置，`--no-build` 只改
   约束不编译，`--led` 会顺带打开心跳灯的宏。

   引脚号取自板子原理图/用户手册的引脚分配表，或厂家例程 `.qsf` 里的
   `set_location_assignment`；**要球号（Location，如 A13），不是 Pin Name
   （`DIFFIO_T19p` 这类内部名）**。不给 `--rst` 时会定义 `NO_EXT_RESET`，
   设计改用内部上电复位（配置后保持 128 拍），少接一根线。

   正点原子 EP4CE10F17C8N 核心板当前使用：

   ```bash
   python set_pins.py --clk E1 --rx B13 --tx A13 --baud 921600
   # clk=E1 是板上 50 MHz 晶振（Quartus 报告为 CLK1, DIFFCLK_0n）
   # A13/B13 是排针上的一对差分脚，当普通 I/O 用；不通信就把 rx/tx 对调
   # --baud 写进 QSF 覆盖 cnn28_top 的 BAUD 参数，必须和上位机一致
   ```

   I/O 为 3.3 V；Cyclone IV 不兼容 5 V，USB-UART 必须是 3.3 V 电平
   （CH340/CP2102 的 3.3 V 版即可）。
3. 全编译 → 下载 `.sof`（**掉电丢失**）或转 `.pof` 烧配置芯片。
4. `python ../Host/mnist_host.py` → 选串口 115200 → 连接。PING 返回 `CNN28-FPGA`
   时会自动下载模型（15,792 B）。

## 8. 重新生成权重

```bash
cd FPGA_CNN
python train_export.py --data ../MNIST --out ../weights/x28 --epochs 12
```

输出到 `weights/x28/`：

| 文件 | 内容 |
|------|------|
| `model.bin` | 15,792 B，按 `metadata.json` 的 section 偏移排布 |
| `metadata.json` | 逐通道 M/S、s_w、准确率、section 偏移 |
| `*_weight.hex` / `*_bias.hex` / `qparams.hex` | 给 testbench 的 `$readmemh` |
| `vectors/img_*.hex`, `logit_*.hex` | 8 组回归向量（每类一张） |

训练脚本同时打印浮点/int8 准确率，并用 `gold_infer`（与 RTL 同一套整数运算）
复核导出的参数，任何不一致会直接报错。

## 9. 文件

| 文件 | 内容 |
|------|------|
| `rtl/cnn28_core.v` | CNN 核：13 个 RAM、地址生成、MAC/重量化 FSM |
| `rtl/cnn28_top.v` | UART 前端、帧协议、命令执行、存储口仲裁 |
| `rtl/uart_rx.v`, `rtl/uart_tx.v` | 8N1 收发，参数化波特率 |
| `tb/tb_cnn28_core.v` | 逐位比对 8 组向量 |
| `tb/tb_cnn28_top.v` | 串口端到端（32 MHz / 4 Mbaud 加速仿真） |
| `quartus/cnn28.qpf/.qsf/.sdc` | 工程、器件、50 MHz 约束 |
| `train_export.py` | 训练、校准、量化、导出、golden 复核 |

仿真（ModelSim）：

```bash
cd sim
vlog ../rtl/*.v ../tb/tb_cnn28_core.v ../tb/tb_cnn28_top.v
vsim -c tb_cnn28_core -do "run -all; quit -f"
vsim -c tb_cnn28_top  -do "run -all; quit -f"
```

## 10. 已知边界

* 只支持 doc 里的这一种拓扑；换网络要改 `cnn28_core.v` 的 FSM 和地址映射。
* 单字节存储口，推理期间主机不能读写存储器（命令按帧串行，天然互斥）。
* `READ_MEM` 单次 64 B；要读大块就分多次。
* 复位是同步低有效，`rst_n` 释放前 `clk` 必须已经在跑。
* 50 MHz 下 55.3 MHz Fmax 只剩约 10 % 余量；改 RTL 后请重新看 `sta.rpt`。
