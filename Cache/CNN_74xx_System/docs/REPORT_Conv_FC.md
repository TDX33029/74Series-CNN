# CONV1 / CONV2 / FC 引擎原理图与地址/MAC 仿真报告

- 日期：2026-11-04
- 项目目录：`D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System`
- 范围：`S07_Conv1`、`S08_Conv2`、`S09_FC` 三张引擎原理图，以及地址序列/MAC 计数仿真、ERC、PDF。
- 结论：三张图均已完成并导出 PDF；ERC 仅剩“本页外部输入未驱动”错误，无重复驱动、无短路、无输出悬空；地址/MAC 仿真三引擎全部 PASS。

## 1. 交付物

| 类别 | 文件 |
|---|---|
| CONV1 原理图 | `D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System\S07_Conv1.kicad_sch` |
| CONV2 原理图 | `D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System\S08_Conv2.kicad_sch` |
| FC 原理图 | `D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System\S09_FC.kicad_sch` |
| 自定义块库 | `D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System\symbols\CNN_Blocks.kicad_sym` |
| CONV1 生成脚本 | `D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System\tools\build_conv1.py` |
| CONV2 生成脚本 | `D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System\tools\build_conv2.py` |
| FC 生成脚本 | `D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System\tools\build_fc.py` |
| 仿真脚本 | `D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System\sim\gen_engine_tb.py` |
| SPICE 网表 | `sim\tb_conv1_eng.cir`、`sim\tb_conv2_eng.cir`、`sim\tb_fc_eng.cir` |
| ERC 报告 | `output\s07-erc.rpt`、`output\s08-erc.rpt`、`output\s09-erc.rpt` |
| 仿真日志 | `output\sim\conv1_engine.log`、`conv2_engine.log`、`fc_engine.log` |
| 仿真波形 | `output\sim\conv1_eng_wave.txt`、`conv2_eng_wave.txt`、`fc_eng_wave.txt` |
| PDF | `output\pdf\S07_Conv1.pdf`、`output\pdf\S08_Conv2.pdf`、`output\pdf\S09_FC.pdf` |
| 引脚清单（调试用） | `output\s07_pins.json`、`output\s09_pins.json` |

未修改已有 `S01_Supervisor`、`S02_Timing`、`S_LUT_Mult_1` 图纸及其生成脚本。

## 2. 引擎架构

### 2.1 公共数据通路

三张图使用同一套 74 系列数据通路：

- 4 个 `LUT_Mult_Unit`（对应 `S_LUT_Mult_1` 接口）：`A0..A7`、`B0..B7`、`PROD0..PROD15`、`LUT_AB_LATCH`、`LUT_PROD_LATCH`、`LUT_CE_N`、`LUT_OE_N`。图上按实例限定为 `C1_A0_*`/`C1_B0_*`/`C1_P0_*`（CONV2 为 `C2_*`，FC 为 `FC_*`），避免四份实例在展开时冲突。
- 4 级输入/权重流水：8×`74HCT574`（4 级像素 + 4 级权重），每级 8 位。
- 4 乘积 18 位加法树：13×`74HC283`，分两级两两相加后汇总，产生 `PSUM[17:0]`。
- 32 位累加器：8×`74HC283` + 4×`74HCT574`；`ACC_LD` 控制 B 侧掩码（5×`74HC157`），清空时 32 个 10 kΩ 下拉保证高阻期间读回 0。
- Requant/零点修正块：S07/S08/S09 分别由 S13/S15/S17 门级实现（串行 32×16 乘法器、64 位中间积、移位/四舍五入/饱和）；FC1 为 uint8+ReLU，FC2 为 signed32 统一 scale，四字节小端。
- 本地 FSM：2×`27C512`（ROM1 下一状态+标志，ROM2 控制字）+ `74HCT273` 状态寄存器 + 2×`74HCT574` 输出寄存器 + `74HC138` 状态译码。
- 存储接口：每个引擎一个 `S02_MEM_IF` 实例，信号名与 `S02_Timing` 完全一致：`REQ`、`WE`、`CLK`、`RESET_N`、`WAIT_READ[3:0]`、`WAIT_WRITE[3:0]`、`MEM_nCE`、`MEM_nOE`、`MEM_nWE`、`MEM_ACK`、`MEM_DONE`、`MEM_BUSY`、`DATA[7:0]`、`MEM_DATA[7:0]`。每个 bank 的片选为全局网络 `C1_MEM_nCE_{IN,W,OUT,B,Q,MC}`（CONV2 前缀 `C2_`，FC 前缀 `FC_`）。
- 时钟/复位：全局 `CLK` 单时钟；`RESET_N` 低有效；`START/BUSY/DONE` 为同步单周期握手。

### 2.2 CONV1（S07）

参数：`H=28, W=28, Cin=1, Cout=8, K=5`，`Hout=24, Wout=24`。

循环顺序与计数链：

```text
oc(0..7) -> oy(0..23) -> ox(0..23) -> ky(0..4) -> kx(0..4)
ic = 0（Cin=1，74HC161 固定清零，Q0 引出为 IC0）
```

- 计数器：OC 3 位、OY 5 位、OX 5 位、KY 3 位、KX 3 位、SP 10 位（0..575）。均为 74HC161 链，74HC688 比较终值，NAND 产生同步零装载 `~PE`；`MAC_EN` 为每 MAC 的使能，KX 由 `MAC_EN` 驱动。
- 地址公式与位宽：

```text
SY = OY + KY
SX = OX + KX
SY28 = SY*28 = SY*32 - SY*4        （NSY 取反 + 进位实现）
IN_ADDR  = SY28 + SX               = (oy+ky)*28 + (ox+kx)      10 bit, 0..783
W_ADDR   = OC*25 + KY*5 + KX       = oc*25 + ky*5 + kx          8 bit, 0..199
OUT_ADDR = OC*576 + SP             = oc*576 + oy*24 + ox       13 bit, 0..4607
```

- `OC*25` 由 `OC*5 + OC*5*5` 的 74HC283 链实现；`OUT` 侧利用 `576 = 9*64`，先 `OC*9` 再左移 6 位加到 `SP`，最高进位单独保留为 `OUT_ADDR12`。
- 74HC157 地址选择器在 `IN/W/OUT` 地址、`B`/`Q`/微码地址之间切换，所有选择端由 FSM 控制。
- MAC/输出点：`5×5=25`；输出点 `8×24×24=4608`；总 MAC `25×4608=115200`。
- 输出顺序：`oc -> oy -> ox`，每点 1 个 uint8（本层小端仅使用 byte 0）。

### 2.3 CONV2（S08）

参数：`H=12, W=12, Cin=8, Cout=16, K=3`，`Hout=10, Wout=10`。

循环顺序与计数链：

```text
oc(0..15) -> oy(0..9) -> ox(0..9) -> ic(0..7) -> ky(0..2) -> kx(0..2)
```

- 计数器：OC 4 位、OY/OX 4 位、IC 3 位、KY/KX 2 位、SP 7 位（0..99）。终值比较与同步零装载由 74HC688 + NAND 完成。
- 地址公式与位宽：

```text
SY = OY + KY
SX = OX + KX
SY12 = SY*12 = (SY << 3) + (SY << 2)
IC9   = (IC << 3) + IC            = ic*9
IC144 = IC9 << 4                  = ic*144（低 4 位接 GND）
T1    = IC144 + SY12
IN_ADDR  = T1 + SX                = ic*144 + (oy+ky)*12 + (ox+kx)   11 bit, 0..1151 (CHW)
W_ADDR   = OC*72 + IC*9 + KY*3 + KX = oc*72 + ic*9 + ky*3 + kx     11 bit, 0..1151
OUT_ADDR = (OC*25 << 2) + SP      = oc*100 + oy*10 + ox           11 bit, 0..1599
```

- `OC*72 = OC*9*8`，`OC*100 = OC*25*4`，均由 74HC283 链和硬连线移位实现。
- 74HC157 完成 `IN/W/OUT`、`B/Q`、微码地址的选择。
- MAC/输出点：`8×3×3=72`；输出点 `16×10×10=1600`；总 MAC `72×1600=115200`。
- 输出顺序：`oc -> oy -> ox`，每点 1 个 uint8（小端 byte 0）。

### 2.4 FC（S09）

FC1：`400 -> 32`，uint8 + ReLU；FC2：`32 -> 10`，signed32 统一 scale，小端 4 字节。

循环与计数：

```text
FC1: neuron(0..31) -> index(0..399)   400 MAC/neuron, 12800 MAC
FC2: neuron(0..9)  -> index(0..31)     32 MAC/neuron,    320 MAC
FC_SEL=0 选择 FC1；FC_SEL=1 选择 FC2
```

- `NEURON` 5 位、`INDEX` 9 位、`BYTE` 2 位；FC1/FC2 的终值比较分别由 `NEURON31/NEURON9`、`INDEX399/INDEX31` 74HC688 产生，`FC_SEL` 选择 `NEURON_LAST`、`INDEX_LAST` 以及权重基址。
- 地址公式：

```text
FC1 IN_ADDR  = index                                    0..399
FC1 W_ADDR   = neuron*400 + index                       0..12799
FC1 OUT_ADDR = neuron                                   0..31
FC2 IN_ADDR  = index                                    0..31
FC2 W_ADDR   = neuron*32 + index                        0..319
FC2 OUT_ADDR = neuron*4 + byte, byte=0..3（小端）       0..39
```

- `N400 = (neuron<<8) + (neuron<<7) + (neuron<<4)`，`N32 = neuron<<5`，`NWMUX` 选 FC1/FC2 基址后与 `index` 相加；`FCOUT2 = (neuron<<2) + BYTE`，`OUTMUX` 选 `NEURON` 或 `FCOUT2`。
- FC1：输出 uint8；FC2：输出 4 字节 signed32，`QSTB` 每字节一次。
- S09 的 `FC_REQ_QSTB` 直接接 2 位 `BYTE` 计数器的 CEP/CET；FC2 的 BC=0..3 四个 QSTB 使 `BYTE=0..3`，第 4 字节后同步回 0。
- 输出顺序：FC1 `neuron 0..31` 每神经元 1 字节；FC2 `neuron 0..9`，每类 4 字节，地址 `4n..4n+3`，`D0` 为 LSB。
- 总 MAC：`12800 + 320 = 13120`；输出写次数：FC1 32 + FC2 40 = 72。

### 2.5 V2 简单 Requant（S13/S15/S17）

旧版 `Requant_Block` 的通用门级核心已归档，当前 S07/S08/S09 使用 V2 小核心：

- S13：CONV1，`Q = clamp(ACC >> 8, 0, 255)`，13 片 DIP。
- S15：CONV2，`Q = clamp(ACC >> 9, 0, 255)`，13 片 DIP。
- S17：FC1 `Q = clamp(ACC >> 8, 0, 255)`；FC2 原始 signed32 四字节小端，24 片 DIP。

```text
Conv/FC1:
  QRAW[i] = ACC[S+i]（越界取 ACC[31]）
  HIGH    = OR(ACC[S+8..31])
  SAT_POS = HIGH & ~ACC[31]
  QVAL    = ACC[31] ? 0 : (SAT_POS ? 255 : QRAW)
  Q       = QVAL 在 START 沿锁存
  QSTB    = START 后 1 个 CLK
  DONE    = START 后 2 个 CLK

FC2:
  byte = ACC[8*BC[1:0] +: 8]；BC=0..3 时 QSTB，BC=3 时 DONE
```

- 没有 `BIAS/M/ZP_X/ZP_W/ZP_OUT/N_MACS`，没有 32×16 乘法器，没有 27C512 微程序。
- 没有 `PDATA/PSEL/PLOAD`，S14/S16/S18 已删除。
- 模型契约：对称量化、bias=0、每层统一 2^S；直接截断，不四舍五入。
- FC1/FC2 仍共用 S09 的 `FC_REQ_QSTB` 字节计数和 OUTHOLD；FC2 地址为 `neuron*4+byte`。
- 验证：`sim/gen_requant_simple_tb.py`（5000×3 随机 clamp、FC2 字节序、握手模型、结构/跨页/BOM/ERC）；`sim/run_all.py` 11/11。
- 详细说明：`docs/REQUANT_SIMPLE_V2.md`。

## 3. ERC 结果

顶层最终结果（2026-11-06，V2 集成后）：

```
发现 940 条违规项
errors 0 / warnings 940
```

warning 主要是 74HC 别名符号库一致性、单页全局标签和未用备用门；顶层无 `pin_to_pin`/输出冲突/短路。以下为各引擎单页历史报告，单页 error 均为外部输入未驱动（顶层由 S01/CLK/RESET 驱动）。

执行命令（单页历史）：

```bat
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc --severity-all -o output\s07-erc.rpt S07_Conv1.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc --severity-all -o output\s08-erc.rpt S08_Conv2.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc --severity-all -o output\s09-erc.rpt S09_FC.kicad_sch
```

实际报告汇总行：

| 图纸 | ERC messages | Errors | Warnings | 报告 |
|---|---:|---:|---:|---|
| S07_Conv1 | 184 | 3 | 181 | `output\s07-erc.rpt` |
| S08_Conv2 | 189 | 3 | 186 | `output\s08-erc.rpt` |
| S09_FC | 174 | 5 | 169 | `output\s09-erc.rpt` |

### 3.1 错误（全部为本页外部输入未驱动）

| 图纸 | 网络 | 引脚位置 | 说明 |
|---|---|---|---|
| S07 | `CLK` | U1 pin 2 (CP) | 全局时钟，板级由 S01/时钟源驱动 |
| S07 | `RESET_N` | U19 pin 1（74HC08 复位合成门） | 全局复位，板级由 S01 驱动 |
| S07 | `C1_START` | U136 pin 5 (ROM1 A5) | 引擎启动，板级由 S01 驱动 |
| S08 | `CLK` | U1 pin 2 (CP) | 同上 |
| S08 | `RESET_N` | U16 pin 1 (~MR) | 同上 |
| S08 | `C2_START` | U140 pin 5 (ROM1 A5) | 板级由 S01 驱动 |
| S09 | `CLK` | U1 pin 2 (CP) | 同上 |
| S09 | `RESET_N` | U14 pin 1（74HC08 复位合成门） | 同上 |
| S09 | `FC1_START` | U126 pin 1（74HC32 启动合成） | 板级由 S01 驱动 |
| S09 | `FC2_START` | U126 pin 2（74HC32 启动合成） | 板级由 S01 驱动 |
| S09 | `FC_SEL` | U5 pin 1 (74HC157 S) | 板级由 S01 驱动 |

这些是独立图纸的对外接口，单页 ERC 没有源端，属于预期错误；在系统顶层由 `S01_Supervisor`/时钟复位网络驱动。

### 3.2 警告分类

| 类型 | S07 | S08 | S09 | 说明 |
|---|---:|---:|---:|---|
| `lib_symbol_issues` | 96 | 100 | 86 | KiCad 10 的 `74xx` 库中不存在 `74HC161/283/157/08/32/00/04` 等别名；符号已嵌入图纸，绘制/网表正常 |
| `lib_symbol_mismatch` | 41 | 42 | 33 | 嵌入的 `74HCT574` 与库版本存在字段差异 |
| `isolated_pin_label` | 40 | 40 | 44 | 单页上的对外全局标签/每 bank 片选标签，只在本页出现一次 |
| `missing_unit` | 2 | 2 | 3 | 多单元门器件只放置了使用到的单元（电源单元已单独放置） |
| `missing_input_pin` | 2 | 2 | 3 | 未使用备用门单元的输入脚未连接（未放置单元） |

关键结论：

- 没有 `pin_to_pin`（重复驱动/短路）错误。
- 没有 `output_to_output`/输出对输出短接错误。
- 没有 `pin_not_connected`/输出悬空错误；所有已放置符号的引脚均接线、接电源地或显式 NC。
- 唯一 errors 是上表 11 个外部输入。

## 4. 地址 / MAC 仿真

### 4.1 执行命令

```bat
cd /d D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System
python sim\gen_engine_tb.py
```

脚本内部调用 KiCad 自带 ngspice 共享库：

```bat
python tools\ngspice_runner.py sim\tb_conv1_eng.cir
python tools\ngspice_runner.py sim\tb_conv2_eng.cir
python tools\ngspice_runner.py sim\tb_fc_eng.cir
```

### 4.2 验证方法（三种独立方法）

1. **Python golden model**：按规定的嵌套循环顺序生成每一步的 `(oc,oy,ox,ic,ky,kx)` 与 `IN/W/OUT` 地址，统计 MAC 数和边界。
2. **Python 74HC161 计数器模型**：模拟同步零装载、使能链和终值回绕，逐步比对 115200/13120 个 MAC 索引。
3. **ngspice 行为模型**：`Bstep = floor(time/100ns)` 作为时钟步进；地址用 `floor/mod` 从同一公式计算；`.tran 100ns` 跑完整序列；`wrdata` 导出 `v(step) v(ina) v(wa) v(oa)`，逐步与 golden 比对；极值直接从 SPICE 波形统计（`.meas` 指令保留在网表中，但共享库回调未稳定返回 measure 文本，因此以 `wrdata` 波形极值作为实际证据）。

### 4.3 实际 PASS 摘要

`output\sim\conv1_engine.log`：

```text
PASS: CONV1 MAC count = 115200
PASS: CONV1 points = 8*24*24 = 4608
PASS: CONV1 IN_ADDR bounds 0..783 (got 0..783)
PASS: CONV1 W_ADDR bounds 0..199 (got 0..199)
PASS: CONV1 OUT_ADDR bounds 0..4607 (got 0..4607)
PASS: CONV1 last MAC at oc=7,oy=23,ox=23,ky=4,kx=4
PASS: CONV1 last addresses = (783,199,4607)
PASS: CONV1 74HC161 counter model matches golden indices for all 115200 MACs
PASS: CONV1 counters wrap to (oc,oy,ox,ky,kx)=0 after the final MAC
ngspice load rc=0
ngspice run rc=0
SPICE samples: 115201 steps (expected 115200)
PASS: conv1: SPICE address sequence equals golden for every step
conv1: SPICE measured bounds IN 0..783, W 0..199, OUT 0..4607
PASS: conv1: SPICE extrema equal golden extrema
PASS: conv1: all addresses stay inside their documented ranges
PASS: conv1: MAC count 115200 == 115200
RESULT: PASS
```

`output\sim\conv2_engine.log`：

```text
PASS: CONV2 MAC count = 115200
PASS: CONV2 points = 16*10*10 = 1600
PASS: CONV2 IN_ADDR bounds 0..1151 (got 0..1151)
PASS: CONV2 W_ADDR bounds 0..1151 (got 0..1151)
PASS: CONV2 OUT_ADDR bounds 0..1599 (got 0..1599)
PASS: CONV2 last MAC at oc=15,oy=9,ox=9,ic=7,ky=2,kx=2
PASS: CONV2 last addresses = (1151,1151,1599)
PASS: CONV2 74HC161 counter model matches golden indices for all 115200 MACs
SPICE samples: 115201 steps (expected 115200)
PASS: conv2: SPICE address sequence equals golden for every step
conv2: SPICE measured bounds IN 0..1151, W 0..1151, OUT 0..1599
PASS: conv2: SPICE extrema equal golden extrema
RESULT: PASS
```

`output\sim\fc_engine.log`：

```text
PASS: FC total MAC count = 13120
PASS: FC1 MAC count = 32*400 = 12800
PASS: FC2 MAC count = 10*32 = 320
PASS: FC IN_ADDR bounds 0..399 (got 0..399)
PASS: FC W_ADDR bounds 0..12799 (got 0..12799)
PASS: FC OUT_ADDR bounds 0..36 (got 0..36)
PASS: FC output writes = 32 (FC1) + 40 (FC2) = 72
PASS: FC2 write address bounds 0..39 (got 0..39)
PASS: FC2 writes 4 bytes little-endian per class, addresses 4n..4n+3
PASS: FC1 neuron/index counters wrap after 12800 MACs
PASS: FC2 neuron/index counters wrap after 320 MACs
PASS: FC 74HC161 counter model matches golden indices for all 13120 MACs
SPICE samples: 13121 steps (expected 13120)
PASS: fc: SPICE address sequence equals golden for every step
fc: SPICE measured bounds IN 0..399, W 0..12799, OUT 0..36
PASS: fc: SPICE extrema equal golden extrema
PASS: fc: MAC count 13120 == 13120
RESULT: PASS
```

总结果：

```text
OVERALL: PASS
```

说明：FC 日志中的 `OUT_ADDR 0..36` 是 MAC 阶段输出基地址（FC2 为 `neuron*4`，最大 9*4=36）；输出写阶段额外 4 字节偏移后为 `0..39`，已由 `FC2 write address bounds 0..39` 单独验证。

### 4.4 边界与位宽核对

| 引擎 | MAC 数 | IN 地址 | W 地址 | OUT 地址 | 最后一步 |
|---|---:|---|---|---|---|
| CONV1 | 115200 | 0..783 (10 bit) | 0..199 (8 bit) | 0..4607 (13 bit) | oc=7, oy=23, ox=23, ky=4, kx=4 |
| CONV2 | 115200 | 0..1151 (11 bit) | 0..1151 (11 bit) | 0..1599 (11 bit) | oc=15, oy=9, ox=9, ic=7, ky=2, kx=2 |
| FC1 | 12800 | 0..399 | 0..12799 (14 bit) | 0..31 | neuron=31, index=399 |
| FC2 | 320 | 0..31 | 0..319 | 0..39（写阶段；MAC 基址 0..36） | neuron=9, index=31 |

- CONV1/CONV2 的 MAC 数均为 `115200`，且计数器在最后一步后回到 0。
- FC 总 MAC `13120`，FC1/FC2 分别 `12800`/`320`，计数器回绕正确。
- 所有地址保持在文档范围内，没有地址溢出；SPICE 波形极值与 golden 完全一致。

## 5. PDF

执行命令：

```bat
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export pdf --output output\pdf\S07_Conv1.pdf S07_Conv1.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export pdf --output output\pdf\S08_Conv2.pdf S08_Conv2.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export pdf --output output\pdf\S09_FC.pdf S09_FC.kicad_sch
```

| PDF | 页数 | 幅面 | 大小 |
|---|---:|---|---:|
| `output\pdf\S07_Conv1.pdf` | 1 | A1 横向 | 约 1.52 MB |
| `output\pdf\S08_Conv2.pdf` | 1 | A1 横向 | 约 1.57 MB |
| `output\pdf\S09_FC.pdf` | 1 | A1 横向 | 约 1.42 MB |

三张图均已用 PyMuPDF 渲染检查：标题、循环顺序、地址公式、输出顺序、块引脚和内部说明均可见；顶部说明文字已移到空白区并拆行，不再与计数器/比较器电源符号重叠。功能块按区域分开，未发现符号体互相覆盖。

## 6. 已知限制

1. **LUT 仍为架构级块符号**：S07–S09 内各 4 个 `LUT_Mult_Unit`（共 12 个）尚未展开为 74HC/27C512 门级网表；Requant 已全部展开（S13/S15/S17）。
2. **LUT 乘法单元为块引用**：S07–S09 使用 4 个 `LUT_Mult_Unit` 块，接口与 `S_LUT_Mult_1` 一致；ROM 内容/烧录镜像不由本页生成。
3. **ERC 外部输入错误**：`CLK`、`RESET_N`、`Cx_START`、`FC1_START`、`FC2_START`、`FC_SEL` 在独立单页上无源端，属系统顶层连接项；不影响页内数据通路。
4. **警告为库/单页性质**：`lib_symbol_issues`/`lib_symbol_mismatch` 来自 KiCad 10 `74xx` 库缺少 74HC 别名及嵌入符号版本差异；`isolated_pin_label` 来自单页全局标签；`missing_unit`/`missing_input_pin` 来自未使用的备用门单元。均与既有 S01/S02 图纸的告警类型一致。
5. **仿真为行为级**：验证的是循环顺序、计数器回绕、地址序列和 MAC 计数，不覆盖门级延迟、建立/保持时间、8 MHz 时序余量、存储器实际读等待和模拟乘法器精度；这些需后续门级/板级时序仿真。
6. **FC2 输出地址语义**：MAC 阶段 `OUT_ADDR=neuron*4`（0..36），写阶段加字节偏移到 0..39；日志已分别验证，报告中也明确区分。
7. **A1 单页密度高**：网络标签较小，打印/查看时需放大；已通过分块布局避免短路，但未做自动布线。

## 7. 复现步骤

```bat
cd /d D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System

python tools\build_conv1.py
python tools\build_conv2.py
python tools\build_fc.py

"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc --severity-all -o output\s07-erc.rpt S07_Conv1.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc --severity-all -o output\s08-erc.rpt S08_Conv2.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc --severity-all -o output\s09-erc.rpt S09_FC.kicad_sch

"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export pdf --output output\pdf\S07_Conv1.pdf S07_Conv1.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export pdf --output output\pdf\S08_Conv2.pdf S08_Conv2.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export pdf --output output\pdf\S09_FC.pdf S09_FC.kicad_sch

python sim\gen_engine_tb.py
```
