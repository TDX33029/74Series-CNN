# 74 系列 CNN 系统工程 —— 仿真修正变更报告（KiCad → 嘉立创 EDA 同步用）

- 工程：`Cache/CNN_74xx_System/CNN_74xx_System.kicad_sch`（12 块板卡方案 A）
- 对照基线：`Cache/_backup_before_fix_20261108/`（修改前的 KiCad 工程与 `top_before.net`）
- 当前网表：`Cache/CNN_74xx_System/output/top.net`（由修改后的生成器重新导出）
- 引脚级差异清单（机器可读、权威）：`Cache/CNN_74xx_System/review/net_diff_v1_v11.txt`
- 仿真工程：`Simulation/`（ModelSim ASE，897+ 封装行为模型，按真实引脚号连接）

> 本报告只描述**电气连接/器件/ROM 内容**的变化。嘉立创 EDA 里的重绘工程请按
> 「第 3 节 逐板操作」和「第 4 节 器件增删表」修改；若两处冲突，以
> `review/net_diff_v1_v11.txt` 的逐引脚记录为准。

---

## 1. 结论速览

| 编号 | 板卡/图页 | 问题 | 修改性质 |
|------|-----------|------|----------|
| V1 | B12 S10_Top_IO | 主机 16 位地址不够，ADDR[23:16] 靠 10k 上拉恒为 0xFF | 删除 RN3，改由 MEM_SEL 生成页号 |
| V2 | B04 / B06 / B08 / B09 | 74HC688 的 `P=R` 是**低有效**，23 个 `*_LAST` 直接当高有效用 | 每个比较器输出加反相器 |
| V3 | B04 / B08 / B09 | 8 位比较器被用于 10 位 / 9 位计数（高位被截断） | 增加第二片 688 + 74HC02 级联 |
| V4 | B08/B09 S09+S17 | FC2 每个神经元要写 4 字节，原设计只写 1 字节且握手会死锁 | S09 加 BYTE 计数器与 A12；S17 改 2 级 DFF 握手 |
| V5 | B04 | 曾怀疑 C1 的 POINT_LAST 接错 | **复检为误报，不改** |
| V6 | — | H_A15 未引出影响在线编程 | **评估后不改**（27C512 离线烧录） |
| V7 | B04 / B06 | 嵌套循环计数器只看自身 `*_LAST` 就同步装载，外层计数器被提前清零 | 装载条件改为「所有内层也到末值」且受 MAC_EN 门控 |
| V8 | B04 / B06 / B08 / B09 | 状态译码器 Y0 把 state 8（requant）也译成 0，每个输出点清一次全部循环计数器 | 译码器 `~E1` 改接 ST3 |
| V9 | B04 / B06 / B08 / B09 | 写请求保持到 MEM_DONE，控制器回到 IDLE 时 REQ 仍为高 → 每次写执行两遍 | 引擎微码改为 MEM_ACK 释放 REQ（S02 原理图不变） |
| V10 | B06 | C2 外层循环使能错位一级，IC 永不计数，引擎只在 ky/kx 上打转 | 4 个 74HC08 改接 |
| V11 | B08 / B09 | FC 的 NEURON 计数器重载未受 MAC_EN 门控，最后一个神经元提前回零，IMAGE_LAST 永不置位 | 1 个 74HC00 改接 |

修改后整链仿真（C1 → POOL1 → C2 → POOL2 → FC1 → FC2 → ARGMAX）见第 6 节。

---

## 2. 同步前必须知道的三件事

1. **B02（S02 时序控制器）没有电气变化。** 中途曾给 S02 加过 REQ 边沿检测，
   后来发现会破坏 POOL/ARGMAX 的「REQ 常高、连续突发」用法，已完整回退。
   现在 `top.net` 里 B02 与基线**逐引脚一致**，只需替换 ROM 内容（timing.hex 未变）。
2. **S09（FC1/FC2）与 S17 是「区域重构」**，参考位号在 U9125…U9145 /
   U9325…U9345 之间发生了整体位移，出现「同一位号换了器件型号」的情况。
   第 4 节给出了完整的「删除 / 新增 / 同号换型」清单，请按清单整块替换，
   不要试图逐引脚微调。
3. **ROM 映像必须同步更新**：`model/microcode/c1_rom1/2`、`c2_rom1/2`、
   `fc_rom1/2` 的 `.hex` 与 `.bin` 都重新生成过（V9 改了写状态的退出条件，
   V4 改了 A12 的含义）。`init/timing.hex`（S02）不变。

---

## 3. 逐板操作

### 3.1 B12 S10_Top_IO（V1）

- 删除电阻排 **RN10003**（10k，8 位，把 H_A16..H_A23 上拉）。
- U10006（74HC245，地址高位缓冲）输入端改为：

| U10006 引脚 | 原网络 | 新网络 |
|-------------|--------|--------|
| 2 (A0) | H_A16 | `MEM_SEL0` |
| 3 (A1) | H_A17 | `MEM_SEL1` |
| 4 (A2) | H_A18 | `MEM_SEL2` |
| 5 (A3) | H_A19 | `MEM_SEL3` |
| 6 (A4) | H_A20 | `MEM_SEL4` |
| 7 (A5) | H_A21 | `GND` |
| 8 (A6) | H_A22 | `GND` |
| 9 (A7) | H_A23 | `GND` |

结果：ADDR[23:16] = {GND, GND, GND, MEM_SEL[4:0]}。H_A16..H_A23 这 8 个网络
在新工程中**不存在**（底板也不需要走这 8 根线）；底板只需 A0..A15 + MEM_SEL[4:0]。

### 3.2 B04 S07_Conv1（V2/V3/V7/V8/V9）

新增 3 个器件：

| 位号 | 型号 | 作用 |
|------|------|------|
| U7155 | 74HC04 | C1 的 6 个比较器输出反相（V2） |
| U7156 | 74HC688 | C1_SP 高 2 位比较（V3，10 位计数器） |
| U7157 | 74HC02 | C1_SP 两段比较结果 NOR 成 `C1_SP_LAST`（V3） |

改接（共 19 个引脚，详见 diff）：

- 6 个 688 的 19 脚由 `C1_*_LAST` 改名为 `C1_*_LAST_LO_N`，经 74HC04 反相后
  才驱动 `C1_*_LAST`（V2）。
- U7021/U7022（74HC00）的输入按 V7 重排：装载（~PE）只在
  「本层到末值 **且** 所有内层也到末值 **且** MAC_EN=1」时有效（V7）。
- U7137（74HC138，状态译码）的 5 脚（~E1）由 GND 改接 `C1_ST3`（V8）。
- U7139（74HC02）多余门用于 SP 比较器级联（V3）。

### 3.3 B06 S08_Conv2（V2/V3/V7/V8/V9/V10）

新增 2 个器件：U8155、U8156（均为 74HC04，用于 7 个比较器的反相）。

改接要点（共 24 个引脚）：

- 7 个 688 的 19 脚 → `*_LAST_LO_N` + 反相器（V2）。
- U8019/U8020（74HC00）装载条件按 V7 重排。
- U8019 的 4 个使能输入按 V10 改接：
  `IC_EN` ← `KXKY`、`OX_EN` ← `ICKY`、`OY_EN` ← `ICX`、`OC_EN` ← `ICXO`。
  （原来是 ICKY/ICX/ICXO/IMG_LAST，全部错位一级，导致 IC 永不计数。）
- U8137（74HC138）5 脚改接 `C2_ST3`（V8）。

### 3.4 B08 S09_FC1 / B09 S09_FC2（V2/V3/V4/V8/V9/V11）

两张图结构相同，只是位号前缀 91xx / 93xx 不同。**建议整块重画 U91xx…U9145
（U93xx…U9345）这一段**，因为参考位号发生了位移。

新增（每张图，U9142 借用原测试点位号）：

| 位号 | 型号 | 作用 |
|------|------|------|
| U9142 | 74HC688 | `INDEX399` 高位比较（9 位 INDEX 的第 9 位，V3） |
| U9143 | 74HC02 | 两组级联 NOR：`INDEX399`、`INDEX31`（V3） |
| U9144 | 74HC688 | `INDEX31` 高位比较（第 9 位，V3） |
| U9145 | 74HC04 | 5 个比较器结果反相（NEURON31/NEURON9/INDEX399/INDEX31/BYTE_LAST，V2） |

（NEURON 的 32 / 9 比较器仍用原有 U9003/U9004，只把 19 脚改名并加反相。）

功能改动：

- **V4（4 字节写循环）**：新增 2 位 BYTE 计数器（74HC161，0..3），
  使能 = `FC_ST10 & MEM_ACK`；`BYTE_LAST = (BYTE==3)` 接 ROM 的 A12；
  输出地址 = `NEURON*4 + BYTE`（FC2）；FC1 仍为 `NEURON`。
- **V9**：`BYTE_EN` 的第二个输入由 `MEM_DONE` 改为 `MEM_ACK`（写状态提前一拍退出）。
- **V8**：U9123/U9323（74HC138，状态译码）5 脚改接 `FC_ST3`。
- **V11**：`NEURON_PE_N = NAND(NEURON_LAST, NEURON_EN)`（原为 `INDEX_LAST`），
  即神经元计数器只在 MAC 沿重载。

### 3.5 B08 S17_FC1 / B09 S17_FC2（V4）

删除（每张图 3 个器件）：

| 位号（FC1 / FC2） | 型号 | 原作用 |
|-------------------|------|--------|
| U16022 / U16222 | 74HC74 | requant 忙标志 |
| U16023 / U16223 | 74HC08 | 字节计数译码 |
| U16024 / U16224 | 74HC157 | 字节选择 mux |

新增/改接：

- 用 **2 级 74HC74 移位链**做 `FC_REQ_QSTB`、`FC_REQ_DONE` 握手
  （原 U16020 74HC161 字节计数器改为 74HC74，位号不变）。
- 字节选择改为全局网络 `FC_BYTE0` / `FC_BYTE1`（由 S09 的 BYTE 计数器驱动），
  原 `FC_RQ_BC0/BC1/BC2` 网络全部取消。
- `FC_REQ_BUSY` = `START | QSTB | DONE`（两片 74HC32）。

> 注意：S17 的 requant 数据通路（LUT、加法器、饱和）**未改动**，只改了握手和
> 字节选择。

---

## 4. 器件增删表（相对基线）

差异统计：**新增 11 个封装、删除 7 个封装、同号换型 20 个、共 567 个引脚连接变化**。
各图页变化引脚数：B04 = 19，B06 = 24，B08_S09 = 216，B08_S17 = 42，
B09_S09 = 216，B09_S17 = 42，B12 = 8；**B02 无变化**。

### 4.1 新增（11 个）

| 位号 | 型号 | 图页 |
|------|------|------|
| U7155 | 74HC04 | B04 S07_Conv1 |
| U7156 | 74HC688 | B04 S07_Conv1 |
| U7157 | 74HC02 | B04 S07_Conv1 |
| U8155 | 74HC04 | B06 S08_Conv2 |
| U8156 | 74HC04 | B06 S08_Conv2 |
| U9143 | 74HC02 | B08 S09_FC1 |
| U9144 | 74HC688 | B08 S09_FC1 |
| U9145 | 74HC04 | B08 S09_FC1 |
| U9343 | 74HC02 | B09 S09_FC2 |
| U9344 | 74HC688 | B09 S09_FC2 |
| U9345 | 74HC04 | B09 S09_FC2 |

（另有 U9142 / U9342 由原 TestPoint 位号改放 74HC688，见 4.3。）

### 4.2 删除（7 个）

| 位号 | 型号 | 图页 |
|------|------|------|
| U16022 | 74HC74 | B08 S17_FC1 |
| U16023 | 74HC08 | B08 S17_FC1 |
| U16024 | 74HC157 | B08 S17_FC1 |
| U16222 | 74HC74 | B09 S17_FC2 |
| U16223 | 74HC08 | B09 S17_FC2 |
| U16224 | 74HC157 | B09 S17_FC2 |
| RN10003 | R_Network08 10k | B12 S10_Top_IO |

### 4.3 同号换型（20 个，全部在 S09/S17）

| 位号 | 原型号 | 新型号 |
|------|--------|--------|
| U9125 | 74HC08 | 74HC04 |
| U9126 | 74HC161 | 74HC08 |
| U9127 | 74HC00 | 74HC161 |
| U9130 | 74HC04 | 74HC74 |
| U9131 | 74HC74 | 74HC08 |
| U9132 | 74HC08 | 74HC138 |
| U9133 | 74HC138 | 74HCT541 |
| U9136 | 74HCT541 | TestPoint |
| U9142 | TestPoint | 74HC688 |
| U16020 | 74HC161 | 74HC74 |
| U9325 | 74HC08 | 74HC04 |
| U9326 | 74HC161 | 74HC08 |
| U9327 | 74HC00 | 74HC161 |
| U9330 | 74HC04 | 74HC74 |
| U9331 | 74HC74 | 74HC08 |
| U9332 | 74HC08 | 74HC138 |
| U9333 | 74HC138 | 74HCT541 |
| U9336 | 74HCT541 | TestPoint |
| U9342 | TestPoint | 74HC688 |
| U16220 | 74HC161 | 74HC74 |

**处理建议**：这 20 个位号不要「换件」，而是把对应图页的
U912x～U914x / U932x～U934x 区域整体删除后按新工程重画——
位号顺序变了，逐脚替换会越改越乱。

---

## 5. 网络名变化（跨板/全局）

| 旧网络 | 新网络 | 说明 |
|--------|--------|------|
| `FC_RQ_BC0` / `FC_RQ_BC1` | `FC_BYTE0` / `FC_BYTE1` | 字节选择改为 S09 的 BYTE 计数器驱动，全局网 |
| `FC_RQ_BC2` | 无 | 4 字节只需 2 位 |
| `FC_RQ_RUN` / `FC_RQ_RUN_HOLD` / `FC_RQ_BC_ANY*` | 无 | 旧握手删除 |
| `H_A16` … `H_A23` | 无 | B12 内部改由 MEM_SEL 生成（V1） |
| `C1_*_LAST`（C2/FC 同理） | 语义不变，但源改为「688 → 反相器」 | 见 V2 |

所有**板间排针信号**（`DATA[7:0]`、`MEM_*`、`C*_ADDR`、`C*_MEM_*`、
`POOL_*`、`FC_*`、`ARG_*`）名称与位置**未变**，底板走线不受影响。

---

## 6. 验证记录（整链仿真）

在 `Simulation/rtl` 下用 `run.bat`（ModelSim ASE 10.5b）跑完整推理，
时钟取自板上 8 MHz 有源晶振模型，全部存储器为行为模型（内容为 0，
只验证协议与结构，不验证 CNN 数值）。

最终一次完整运行（`tb_cnn74.v`，16 M 时钟 = 2 s 上限，实际 105 ms 结束）：

| 事件 | 时间 | 写入次数 |
|------|------|----------|
| C1_DONE（CONV1，575 点） | 40.51 ms | 577 |
| P1_DONE（POOL1，1152 字节） | 46.85 ms | 1152 |
| C2_DONE（CONV2，1600 点） | 66.80 ms | 1600 |
| P2_DONE（POOL2，400 字节） | 68.99 ms | 400 |
| FC1_DONE（32 神经元） | 104.24 ms | 32 |
| FC2_DONE（10 神经元 × 4 字节） | 105.17 ms | 40 |
| ARGMAX_DONE | 105.23 ms | — |
| DONE | 105.23 ms | — |

```
PASS: RESET_N follows RESET_RAW
PASS: clock reaches CLK_SEL
PASS: status idle after reset
PASS: SRAM0[0..7] 写读 8/8
PASS: EEPROM[0..3] 写读 4/4
PASS: IMAGE_READY / MODEL_READY
PASS: DONE pulsed at end of chain
PASS: no error reported
PASS: RESULT_VALID latched
PASS: ARGMAX returns class 0        (全 0 输入，10 类分数相同 -> 0)
TB RESULT: PASS
```

写入次数与输出点数一一对应，证明 V9 的双写已消除；FC2 每神经元 4 次写
（40 = 10×4）证明 V4 的四字节循环正确。

> 复现命令：`cd Simulation/rtl && run.bat`（需要 ModelSim ASE 在
> `C:\intelFPGA\18.0\modelsim_ase`）。

---

## 7. 交付物清单

1. 修改后的 KiCad 工程：`Cache/CNN_74xx_System/*.kicad_sch`（12 板 + 根图）
2. 新网表：`Cache/CNN_74xx_System/output/top.net`
3. 引脚级差异：`Cache/CNN_74xx_System/review/net_diff_v1_v11.txt`
4. 新 ROM 映像：`Cache/CNN_74xx_System/model/microcode/*.hex|*.bin`
   （`c1_rom1/2`、`c2_rom1/2`、`fc_rom1/2`；S02 的 `timing.hex` 不变）
5. 仿真工程：`Simulation/`（`run.bat` 一键重建模型 + 编译 + 运行）
6. 本报告：`Cache/CNN_74xx_System/CHANGES_V1_V11_FOR_EASYEDA.md`

---

## 8. 同步检查清单（给嘉立创 EDA 对话）

- [ ] B12：删 RN10003，U10006 的 2..9 脚改接 MEM_SEL0..4 与 GND
- [ ] B04：加 U7155/U7156/U7157，6 个 688 输出改名，U7021/U7022 重排，U7137 脚 5 改接 C1_ST3
- [ ] B06：加 U8155/U8156，7 个 688 输出改名，U8019/U8020 重排，U8137 脚 5 改接 C2_ST3
- [ ] B08/B09 S09：整块重画 U91xx…U9145 / U93xx…U9345（含 BYTE 计数器、A12、NEURON_PE_N）
- [ ] B08/B09 S17：删 U1x022/23/24，U1x020 改 74HC74 两级链，字节选择改 FC_BYTE0/1
- [ ] 全局网络：新增 FC_BYTE0/FC_BYTE1，删除 FC_RQ_BC*/FC_RQ_RUN* 与 H_A16..23
- [ ] 更新 ROM 烧录文件（c1/c2/fc rom1/2）
- [ ] 回归：用 `Simulation/rtl/run.bat` 跑通整链
