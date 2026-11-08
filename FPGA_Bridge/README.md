# FPGA 桥接器（EP4CE10）— UART ↔ B12 并行装载口

## 1. 这块 FPGA 做什么

```
上位机 (Python/tkinter)
       │  USB 虚拟串口, 115200 8N1, 带 CRC 的帧
       ▼
   EP4CE10  ── 电平转换 ──  B12 (S10/S04 的 J5/J6/J7)
   host_bridge.v              │
                              ├─ 784 B 图像 → MEM_SEL=0
                              ├─ IMAGE_DONE_N 脉冲
                              ├─ START_RAW 脉冲
                              └─ 读回 10×int32 logits (MEM_SEL=6)
```

**FPGA 不计算 CNN。** 它只做三件事：把上位机发来的 28×28 图像写进 S04 的图像
SRAM、触发板卡 START、等 RESULT_VALID 后把 40 字节分数读回来。卷积/池化/全连接
全部由 74 系列板完成——这正是本项目要验证的对象。

原因：EP4CE10 只有 414 kbit（51.75 KB）片上 RAM，而板上 S04 的 SRAM/EEPROM 阵列
（含 8 KB 级 6264 与 28C256）远超这个量级，且 74 系列方案本身就是被验证的硬件。
FPGA 在这里的角色是"USB 串口到 24 位并行装载口"的时序发生器，综合后约 500–700
个逻辑单元。

## 2. 文件

| 文件 | 作用 |
|------|------|
| `uart_rx.v` | 8N1 接收，3 级同步 + 中点采样 + 假起始位剔除 |
| `uart_tx.v` | 8N1 发送，`{stop,data,start}` 移位 |
| `b12_port.v` | 单字节装载时序：地址建立 8 clk → nWE/nOE 16 clk → 保持 8 clk |
| `host_bridge.v` | 协议引擎：收帧/CRC、执行命令、回帧 |
| `tb_host_bridge.v` | 行为级 B12 模型 + 主机 UART 模型的自检测试台 |
| `run_sim.sh` | 一键 ModelSim 回归 |

编译参数：`CLK_HZ`、`BAUD`、`TIMEOUT_MS`。默认 50 MHz / 115200 / 3000 ms。

### 仿真

```bash
./run_sim.sh          # 需要 ModelSim ASE，默认路径 C:/intelFPGA/18.0/modelsim_ase
```

测试台用 16 MHz / 1 Mbaud 跑（只为缩短 784 字节的上传时间，模块本身与参数无关），
覆盖：PING、LOAD_IMAGE（并核对写入 SRAM 的内容）、INFER（40 字节分数 + 结果/错误码/
标志）、READ_MEM、STATUS、坏 CRC 拒收、以及 74LVC245 方向与 WE/OE 的一致性。
当前结果：**21 项 PASS，TB RESULT: PASS**。

## 3. 串口协议

帧格式（两个方向 SOF 不同，防止回环误收）：

```
上位机 → FPGA : A5 5A | CMD | LEN_L LEN_H | PAYLOAD | CRC_L CRC_H
FPGA → 上位机 : 5A A5 | STAT | LEN_L LEN_H | PAYLOAD | CRC_L CRC_H
```

CRC-16/CCITT-FALSE（poly 0x1021，init 0xFFFF，MSB first），覆盖 CMD/STAT + 长度 +
负载，不含两个 SOF 字节。`Host/protocol.py` 与 `host_bridge.v` 是同一套实现。

| CMD | 名称 | 负载 | 响应 |
|-----|------|------|------|
| 0x01 | PING | — | `"MNIST74\x01"`（8 B） |
| 0x02 | LOAD_IMAGE | 784 B | `01` = 已写入并已发 IMAGE_DONE_N |
| 0x03 | INFER | — | 40 B logits + `result` + `error_code` + `flags`（43 B） |
| 0x04 | READ_SCORES | — | 40 B logits |
| 0x05 | RESET | — | `01`（RESET_RAW 拉低 10 ms） |
| 0x06 | STATUS | — | `flags` + `result` + `error_code`（3 B） |
| 0x07 | LOAD_MEM | `sel,addrL,addrH,nL,nH,data...` | `01`，仅 sel ≤ 7（SRAM） |
| 0x08 | READ_MEM | `sel,addrL,addrH,nL,nH` | n 字节 |

STATUS 的 `flags`：bit0=BUSY，bit1=DONE，bit2=ERROR，bit3=RESULT_VALID
（与板上 J7 的极性一致）。INFER 的 `flags`：bit0=RESULT_VALID，bit1=ERROR，
bit2=DONE。

STAT：0=OK，1=CRC 错，2=长度错，3=未知命令，4=板卡超时，5=板卡 ERROR，
6=参数错（例如对 EEPROM 区写 LOAD_MEM）。

**注意**：`LOAD_MEM` 只允许 sel ≤ 7。28C256 的单字节写入是毫秒级，脚本式逐字节
烧写不现实，权重/偏置 EEPROM 必须离线烧录（见第 7 节）。

## 4. 时序与吞吐

| 步骤 | 时间 |
|------|------|
| 上传 784 B @115200 | ≈ 68 ms（8 位数据 + 起始/停止） |
| 写进 6264（每字节 ~33 clk @50 MHz） | ≈ 0.5 ms |
| 板卡推理（8 MHz 全链仿真值） | ≈ 105 ms |
| 读回 40 B + 回帧 | ≈ 4 ms |
| **一次识别合计** | **≈ 180 ms** |

## 5. 电气连接（重要）

板上是 **5 V 逻辑**（74HCT/74HC，VCC=5 V），Cyclone IV E 的 I/O **不耐 5 V**
（绝对最大 4.6 V）。而且 FPGA 的 3.3 V 高电平对 74HC 输入不够：
74HC 在 5 V 供电时 V_IH ≈ 3.5 V，只有 74HCT 才是 2.0 V。所以**不能直连**，
中间必须有一块小的电平转换适配板：

| 器件 | 供电 | 方向 | 用途 |
|------|------|------|------|
| 74HCT541 | 5 V（J6.36/37） | FPGA → 板 | LOAD_EN、nWE、nOE、START、RESET、IMAGE_DONE_N、MODEL_DONE_N（输入 3.3 V 满足 HCT 的 V_IH=2.0 V，输出 5 V） |
| 74LVC245A | 3.3 V（FPGA 板） | 双向 | H_D0..7 数据总线；输入耐 5.5 V，A 侧接板、B 侧接 FPGA |
| 74LVC244A ×2 | 3.3 V | 板 → FPGA | J7 的 16 根状态线（5 V → 3.3 V） |
| 1 kΩ 串联 | — | — | RESET_RAW 线上串 1 kΩ：板上 SW1 按下时限制 541 的输出电流 |

地址 A0..A14、MEM_SEL0..4、nWE/nOE 也可以直连（它们只进 74HCT541/245，V_IH=2.0 V），
但为了布线整齐，建议一并走 HCT541，空余通道接地。

### J6（2×20，PARAM PROG）— 所有存储访问都走这里

| J6 脚 | 板内网络 | 适配板/FPGA |
|-------|----------|-------------|
| 1, 2 | GND | GND |
| 3..10 | H_D0..H_D7 | 74LVC245A（B 侧）= `ld_d[7:0]` |
| 11..25 | H_A0..H_A14 | `ld_a[14:0]`（A15 未引出） |
| 26..30 | H_MEM_SEL0..4 | `ld_sel[4:0]` |
| 31 | LOAD_EN | 541 ← `ld_en` |
| 32 | H_LOAD_nWE | 541 ← `ld_nwe` |
| 33 | H_LOAD_nOE | 541 ← `ld_noe` |
| 34 | MODEL_DONE_N | 541 ← `model_done_n` |
| 35 | MODEL_READY | 244 → `st_model_ready`（本桥未使用） |
| 36, 37 | +5 V | 适配板 5 V |
| 38, 39, 40 | GND | GND |

### J5（2×16，IMAGE LOAD）— 只用到第 27 脚

| J5 脚 | 板内网络 | 连接 |
|-------|----------|------|
| 27 | IMAGE_DONE_N | 541 ← `image_done_n` |
| 28 | IMAGE_READY | 244 → `st_image_ready`（本桥未使用；板上 D6 LED 可见） |

图像数据本身就写在 MEM_SEL=0，J5 的其余引脚不需要接。

### J7（2×10，STATUS）

| J7 脚 | 网络 | FPGA |
|-------|------|------|
| 3 / 4 | ST_BUSY / ST_DONE | `st_busy` / `st_done` |
| 5 / 6 | ST_RESULT_VALID / ST_ERROR | `st_result_valid` / `st_error` |
| 7..10 | ST_RESULT0..3 | `st_result[3:0]` |
| 11..14 | ST_ERROR_CODE0..3 | `st_error_code[3:0]` |
| 15 / 16 | ST_IMAGE_READY / ST_MODEL_READY | 可接到 `st_image_ready` / `st_model_ready`（仅监视） |
| 1, 2, 19, 20 | GND | GND |

### J2 START / J3 RESET

| 脚 | 网络 | 连接 |
|----|------|------|
| J2.1 | START_RAW | 541 ← `start_raw`（板上 R2 10k 下拉，必须主动驱动高） |
| J3.1 | RESET_RAW | 541 ← `reset_raw`，**串 1 kΩ**（板上 100k 上拉 + 1 µF + SW1） |
| J2.2 / J3.2 | GND | GND |

`reset_raw` 正常为高、`CMD_RESET` 时拉低 10 ms。上电时 FPGA 尚未配置，
板上 R1/C90 已产生一次上电复位，因此桥接器不需要额外复位脉冲。

## 6. Quartus 引脚约束模板

引脚号取决于你的 EP4CE10F17C8N 开发板（正点原子板载 USB-UART 与扩展口），
下面只给出信号名与约束写法，`PIN_xx` 需要按板卡原理图替换：

```tcl
# 时钟与串口（板载 USB-UART）
set_location_assignment PIN_xx -to clk          ;# 50 MHz
set_location_assignment PIN_xx -to uart_rx      ;# USB-UART TXD → FPGA
set_location_assignment PIN_xx -to uart_tx      ;# FPGA → USB-UART RXD

# J6 数据/地址/选择
set_location_assignment PIN_xx -to ld_d[0]
# ... ld_d[7], ld_a[0..14], ld_sel[0..4] ...
set_location_assignment PIN_xx -to ld_dir
set_location_assignment PIN_xx -to ld_oe_n

# 控制输出（经 74HCT541）
set_location_assignment PIN_xx -to ld_en
set_location_assignment PIN_xx -to ld_nwe
set_location_assignment PIN_xx -to ld_noe
set_location_assignment PIN_xx -to start_raw
set_location_assignment PIN_xx -to reset_raw
set_location_assignment PIN_xx -to image_done_n
set_location_assignment PIN_xx -to model_done_n

# 状态输入（经 74LVC244A）
set_location_assignment PIN_xx -to st_busy
# ... st_done, st_result_valid, st_error, st_result[0..3],
#     st_error_code[0..3], st_image_ready, st_model_ready ...
```

I/O 标准统一 `3.3-V LVTTL`。`ld_d` 是 inout，其余按方向设置。

## 7. 限制与注意事项

1. **权重必须先烧进 EEPROM。** 桥接器不发权重：28C256 写一个字节要毫秒级，
   不适合逐字节走串口。`model_done_n` 在图像装载后跟随 `image_done_n` 脉冲，
   表示"模型已离线就绪"。若 EEPROM 是空的，板卡会算出全 0 的分数。
2. **一问一答。** 收发共用 1 KB 帧缓冲，主机必须等上一次响应收完再发下一帧
   （`protocol.Link.request` 已保证）。
3. **RESULT_VALID 是粘滞的**，下一次被接受的 START 才会清掉；`INFER` 返回的
   flags 里同时给出 DONE 与 RESULT_VALID，便于诊断"只 DONE 无结果"的情况。
4. **LOAD_MEM 只写 SRAM（sel ≤ 7）**，对 8..15 的 EEPROM 区返回 STAT=6。
5. `TIMEOUT_MS` 默认 3000 ms，远大于板卡 105 ms 的推理时间；若板卡没装好
   （无时钟、无 START 回读），`INFER` 会等到超时并回 STAT=4。
6. 板卡推理时间是 8 MHz 下的仿真值（105 ms），实际取决于 X1 振荡器频率
   （标称 8 MHz）。上位机只按"收到 RESULT_VALID"判断，不依赖固定延时。
