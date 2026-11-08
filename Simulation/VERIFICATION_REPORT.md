# 74 系列 CNN 12 板卡：结构/连线仿真验证报告

日期：2026-11-08
对象：`Cache/CNN_74xx_System/output/top.net`（方案 A，12 板卡，1329 件 BOM）
仿真器：ModelSim ASE 10.5b（`C:\intelFPGA\18.0\modelsim_ase`）
工作目录：`Simulation/rtl`

---

## 1. 结论摘要

**结构本身（板间网络、背板连接、装载通路、存储握手）基本可用，但存在 4 个确定性缺陷和 1 个需复核的微码/接线语义不一致，都会阻止整机正确工作。**

已经跑通的链路：

- 上电复位、8 MHz 时钟、JP1 1-2 短接片；
- 主机经 `H_A/H_D/LOAD_*` 写 SRAM 并读回（8/8 字节正确）；
- 主机经同一通路写 28C256 并读回（4/4 字节正确）；
- `IMAGE_DONE_N` / `MODEL_DONE_N` → `IMAGE_READY` / `MODEL_READY`；
- `START` 同步、S01 状态机启动、C1→P1→C2→P2→FC1 的阶段推进；
- P1/P2 在真实存储总线上完成了数毫秒的读写（整机 `MEM_nCE` 7776 个脉冲@20 ms，其中 P1/P2 约 7760 次，与理论值吻合）。

**没有跑通的部分及原因：**

| 现象 | 直接原因 | 性质 |
|---|---|---|
| 主机无法选中除 SRAM0 外的任何存储器 | 装载排针没有引出 `H_A16..H_A23`，而 S04 的 74HC688 要求 `ADDR[23:16] = {000,MEM_SEL}` | 连线缺陷（阻塞在线编程） |
| C1 的 MAC 循环只走 4 次就 DONE；C2/FC1 同样几微秒结束 | 74HC688 的 `P=R` 是低有效，引擎侧 `*_LAST` 却按高有效使用 | 逻辑缺陷（极性） |
| 即使修好极性，C1 的 SP、FC1 的 INDEX 终值仍不对 | 8 位比较器被用于 10 位/9 位计数器，常数被截断（575→63，399→143） | 逻辑缺陷（位宽） |
| FC2 永远不 DONE，S01 停在 FC2_WAIT | FC 状态 8 保持 `REQ_START=1` 等 DONE；requant 的字节计数器又被 `START_N=0` 按住，BC 到不了 3，DONE 永远不来 | 逻辑缺陷（握手死锁） |
| C1 每个输出点只累加 4 个 tap | `POINT_LAST` 实际接的是 `PAD_LAST`（每 4 个 MAC 一次），微码在状态 7 见到它就转输出 | 设计/微码不匹配，需复核 |

> 这不是“CNN 数值不对”，而是**当前网表按真实 0/1 行为无法完成一次正确的推理**。下面每一条都给出了网表证据和仿真证据。

---

## 2. 验证方法

### 2.1 FPGA 实机路径的状态（2026-11-08 复检）

初检时 Quartus 因 license 报 `Error (292026)`、USB-Blaster 为 Code 28，实机不可用。
复检结果：

- **Quartus 18.0 全流程已可用**：对 EP4CE10F17C8 跑通
  `quartus_map / quartus_fit / quartus_asm / quartus_sta`，均 0 errors；
  最小工程 `Simulation/quartus_probe2/` 生成的 `.sof` 已通过 JTAG 成功下载。
- **USB-Blaster 已可用**：用 Quartus 自带 `drivers/usb-blaster/usbblstr.inf`
  （v2.12.0.0，NTamd64）安装后，设备状态 Code 28 → OK；
  `jtagconfig` 显示 `USB-Blaster [USB-0]`，IDCODE `0x020F10DD`，
  与实际器件 EP4CE10F17 一致。
- **容量限制不变**：EP4CE10 只有 10,320 LE / 414 Kbit 片内 RAM，
  而字面结构需要 898 个封装、30,144 Kbit 存储（52×27C512 + 12×28C256 + 7×HY6264），
  约为片内 RAM 的 **72.8 倍**，单是一片的 27C512（512 Kbit）就超过 414 Kbit。
  因此整机门级复刻仍然不可行，FPGA 只能做协议子集或后续背板测试器。

所以本轮的“连线是否正确”仍由 **ModelSim ASE 对 PC 上的结构网表做时序仿真**回答；
FPGA 实机现在只证明了工具链、JTAG 与器件型号可用，不改变下面的结构结论。

> 注：系统内未找到 `license.dat`，Quartus 的授权合规状态未在本轮核实；
> 本报告只记录“编译/下载功能可用”这一事实。

### 2.2 结构 Verilog 的生成方式

`gen_rtl.py` 直接读取 `output/top.net`：

- 每个 74xx/存储器封装 → 一个行为模型实例，端口名就是 **KiCad 符号引脚号**（`.p1`、`.p2`…），
  连接关系逐引脚来自网表，不做任何“按功能重连”；
- 每条网络 → 一根 `wire`；`+5V/+3V3/GND` → `1'b1/1'b0`；
- 10k/100k 上拉/下拉 → `pullup`/`pulldown`；
- 33 Ω 时钟电阻、470 Ω LED 电阻 → `assign`（按驱动方向确定源/宿）；
- 3 个 8 联电阻网络 → 每个引脚一条下拉；
- 连接器/电容/LED/测试点/按键不参与逻辑；**JP1 按“1-2 已插短接片”建模**
  （`assign CLK_SEL = OSC_OUT`），这是网表本身无法表达、必须显式声明的唯一板级假设；
- 未连接的输出/输入保留悬空（ModelSim 会给出 895 条 “missing connection” 警告，
  逐条核对后均为未用门/未用输出，不影响逻辑）。

背板层不单独建模：`output/top.net` 中同名全局网络已经合并，等价于底板按
`output/boards/backplane_nets.csv` 把每个网络接到对应板卡。32 排针 / 1280 脚 /
282 个跨板网络的逐脚核对已由 `sim/check_backplane.py` 13/13 通过，因此扁平网表
与“12 板 + 无源底板”的电气连接等价。

规模：

| 项目 | 数值 |
|---|---|
| 网表元件 | 1329 |
| 参与逻辑的封装 | 897（其余 432 个：356 个电容/测试点/LED/按键、40 个连接器，以及 32 个电阻 + 3 个电阻网络 + JP1，按下拉/串联/短接处理） |
| 使用网络 | 3866 |
| Verilog wire | 3809 |
| 模型类型 | 23 个模块 |
| 实例 + 上拉/下拉/串联记录 | 954 |

器件分布与 BOM 完全一致：74HC157×200、74HC283×184、74HCT574×75、74HC161×61、
27C512×52、74HCT541×52、74HC08×49、74HC32×40、74HC688×36、74HCT273×32、
28C256×12、74HC85×12、74HC00×9、6264×7、74HC245×6、74LS148×4、74HC238×2、
74HC02×2、74HCT245×1、晶振×1。

### 2.3 存储器初值

- 52 片 27C512 中 51 片使用工程 `model/` 下的 `.hex` 镜像（supervisor/LUT/conv/FC/busmap）；
- **U2001（S02 时序控制器）没有原始镜像**，本轮按 S02 图纸的
  `IDLE→SETUP→WAIT(n)→CAPTURE/HOLD→RELEASE→DONE` 重建了 64 字节微码
  （`gen_timing_rom.py`，报告中明确标注“重建，非提取”）；
- 12 片 28C256、7 片 6264 初值为 0（运行时由主机装载，正好用于验证装载通路）。

### 2.4 4 态仿真的两个约定

1. **74HCT574 上电清 0**：该器件无异步清零，真实上电状态未知；若从 X 开始，
   S01 的 ROM 地址会被 X 污染并锁死。模型初值为 0，仅用于让复位后的 0/1 行为可观察。
2. **ROM/SRAM 地址的 X 位按 0 解释**：真实硬件每位都有确定电平；这样避免
   “任一 DONE 位为 X → 整个 ROM 输出 X → 又反馈回 DONE”的 4 态 X 锁。
   对确定位不做任何改变。

这两条只影响仿真收敛，不改变下面任何一条 0/1 结论。

---

## 3. 已通过的检查

| # | 检查 | 结果 |
|---|---|---|
| 1 | `RESET_RAW` 低→高后 `RESET_N` 跟随 | PASS |
| 2 | 时钟经 X1→JP1→U70→33 Ω 到达全局 `CLK` | PASS |
| 3 | 复位后 `BUSY/DONE/ERROR` 为 0 | PASS |
| 4 | SRAM0（`MEM_SEL=0`）写 8 字节、读回 | 8/8 PASS |
| 5 | 28C256 W_FC1（`MEM_SEL=10`）写 4 字节、读回 | 4/4 PASS |
| 6 | `IMAGE_DONE_N`/`MODEL_DONE_N` 置起 `IMAGE_READY`/`MODEL_READY` | PASS |
| 7 | `START_RAW` 经两级同步启动 S01 | PASS |
| 8 | S01 阶段链 C1→P1→C2→P2→FC1 | PASS（时序见下） |
| 9 | P1/P2 在共享 `MEM_*` 总线上完成真实读写 | PASS（整机 `MEM_nCE` 7776 次@20 ms，P1/P2 约 7760） |

阶段时间线（8 MHz）：

```text
C1_DONE     50.875 µs   （仅 11 个 MEM_nCE 脉冲）
P1_DONE      6.3855 ms
C2_DONE      6.389875 ms（P1 后 4.375 µs）
P2_DONE      8.5885 ms
FC1_DONE     8.59275 ms （P2 后 4.25 µs）
FC2_WAIT     8.593 ms → 37.5 ms 仍不结束（TB 超时）
```

P1/P2 的毫秒级运行说明：背板网络、S11 总线仲裁、S02 时序、S04 存储阵列这条主通路
是通的；C1/C2/FC1 的“4 µs 级完成”不是快，而是提前退出（见 V2）。

**P1/P2 事务数交叉核对：**

- P1：12×12×8 = 1152 个输出点，2×2 窗口 → 4608 次读 + 1152 次写；
- P2：5×5×16 = 400 个输出点，2×2 窗口 → 1600 次读 + 400 次写；
- 合计 6208 读 + 1552 写 = 7760 次事务；
- 实测 20 ms 时 `MEM_nCE` 低脉冲 = **7776**（含少数控制/测试事务），误差 <0.2%。

这基本证明池化引擎的计数链、地址/数据缓冲、S11 请求合并、S02 时序和 S04 译码
在真实网表上都是按预期工作的；问题集中在卷积/FC 的终值比较与 requant 握手上。

---

## 4. 发现的问题

### V1（阻塞）主机装载口没有引出地址 tag 位 `H_A16..H_A23`

**证据（网表/排针）：**

- S10 的装载排针只引出：
  - J10005（2×16）：`H_A0..H_A12`（13 位）+ `H_D0..7` + `H_LOAD_nOE/nWE`；
  - J10006（2×20）：`H_A0..H_A14`（15 位）+ `H_D0..7` + `H_MEM_SEL0..4` + 控制。
- `H_A15..H_A23` 只出现在 `RN10002/RN10003` 下拉和 U10005/U10006 缓冲器输入上，
  **没有任何排针引脚**。
- S04 的 U4032（74HC688）比较 `ADDR[23:16]` 与 `{000, MEM_SEL[4:0]}`，
  输出 `ADDR_TAG_OK_N`，再经 U4033 反相得到 `ADDR_TAG_OK`；
  `DEC_EN = ADDR_TAG_OK & MEM_CE_OK` 才允许 74HC138 译码。

**仿真证据：**

- 主机只驱动 `H_A[23:0]=0x000000` 写 `MEM_SEL=10` 的 28C256：
  读回 `zz`（无驱动），`ADDR_TAG_OK=0`、`nCS_W_FC1=1`；
- 在 TB 中补驱 `H_A[23:16]={3'b000, MEM_SEL}` 后，同一写/读 4/4 字节正确。

**影响：** 按实物排针，只有 `MEM_SEL=0`（SRAM0，tag=0）能被选中；
12 片 28C256、全部 27C512 都无法通过装载口在线编程。

**可选修法（需用户定）：**

1. 装载排针增加 8 根 tag（`H_A16..H_A23`），或把 `H_MEM_SEL` 直接接到比较器 P 端
   （改协议，不再要求地址高字节带 tag）；
2. 保留 tag 协议，但用板上跳线/拨码在装载时产生 tag；
3. 28C256 改为离线编程（与 27C512 一样），放弃在线写 EEPROM。

> 附带观察：`H_A15` 也未引出。28C256 只需 A0..A14，6264 只需 A0..A12，
> 所以在线编程不受影响；27C512 是 UV EPROM，本就应离线编程。此项本身不是缺陷，
> 但说明“24 位地址缓冲器只用了 15 位”是有意为之，建议在文档中写明。

### V2（严重）74HC688 的 `P=R` 低有效输出被当成高有效 `*_LAST`

**证据（器件+网表）：**

- `analysis/pins.json` 中 74HC688 的 19 脚 `P=R` 的 `graphic = inverted`，
  即 **相等时输出 0**；
- 引擎侧共有 23 个比较器输出使用不带 `_N` 的 `*_LAST` 命名：
  - C1：`C1_OC_LAST`、`C1_OY_LAST`、`C1_OX_LAST`、`C1_KY_LAST`、`C1_KX_LAST`、`C1_SP_LAST`（6）
  - C2：`C2_OC_LAST`、`C2_OY_LAST`、`C2_OX_LAST`、`C2_IC_LAST`、`C2_KY_LAST`、`C2_KX_LAST`、`C2_SP_LAST`（7）
  - FC1：`FC_NEURON31`、`FC_NEURON9`、`FC_INDEX399`、`FC_INDEX31`、`FC_BYTE_LAST`（5）
  - FC2：同上 5 个（5）
- 其中**已确认直接/经 157 进入 ROM“最后”判定的 4 条**，路径上没有反相器：
  - `C1_SP_LAST` → U7132/U7133 的 A10；
  - `C2_SP_LAST` → U8132/U8133 的 A10；
  - `FC1_INDEX399` → U9011（S=GND）→ `FC_INDEX_LAST` → POINT_LAST/ROM；
  - `FC2_INDEX31` → U9211（S=+5V）→ `FC_INDEX_LAST` → POINT_LAST/ROM。
- 其余 `*_LAST` 主要参与计数器同步装载/循环门控，低有效可能是有意的；
  但同一套符号里混用“低有效但不带 _N”的命名，本身是高风险，建议逐条复核。
- 对照：`WAIT_MATCH_N`、`ADDR_TAG_OK_N`、`IDLE_N`、池化的 `*_EQ_N`、Argmax 的 `EQ9_N`
  都带 `_N` 并在下游反相/按低有效使用；S01 的 `MATCH0..2` 经 U1015 或门 + U1016 反相，
  也是正确的。

**仿真证据（C1）：**

- SP=0 时 `C1_SP_LAST=1`（应为 0，表示“未到最后一个点”）；
- C1 微码在状态 11：`SP_LAST=1 → next=12(DONE)`，`SP_LAST=0 → next=2(下一点)`；
- 实测 C1 状态序列：`2→3→4→5→6→7` 重复 4 次，然后 `8→9→10→11→12→1`，
  `C1_DONE` 在 50.875 µs，`MEM_nCE` 仅 11 个脉冲（4 次 MAC 循环 + 3 次写）。
- C2/FC1 同样在 P1/P2 结束后约 4 µs 就 DONE，与“看到最后一个点”立即退出吻合。

**影响：** 卷积/全连接引擎在第一个点（甚至第一个 pad）后就结束；整机无法完成一次推理。

**修法：** 对这 4 条（以及复核后确认的其它 `*_LAST`）在 688 输出后加一级反相
（74HC04 空闲门），或统一改名为 `*_LAST_N` 并让微码按低有效解释；不能只改名字。
建议一次性把 23 处的约定统一，避免同类问题在 C2/FC 复制板上重复。

### V3（严重）8 位比较器被用于 >8 位计数器，终值被截断

**证据（网表）：**

- C1 `SP` 是 10 位（0..575）。U7016 的 P 端接
  `+5,+5,+5,+5,+5,+5,GND,GND = 0x3F = 63`，R 端只接 `SP0..SP7`；
  `SP8/SP9` 只进 U7048 加法器，没有进比较器。
- FC1 `INDEX` 是 9 位（0..399）。U9009 的 P 端 =
  `+5,+5,+5,+5,GND,GND,GND,+5 = 0x8F = 143`，R 端只接 `INDEX0..INDEX7`；
  `INDEX8` 未参与比较。
- 根因在生成器 `tools/build_conv1.py` / `build_fc.py` 的 `comparator()`：
  它只生成一片 74HC688、只循环 8 位，`const` 超过 255 时被截断。
  （575 & 0xFF = 63，399 & 0xFF = 143，与实测 P 值完全一致。）

**影响：** 即使修好 V2 的极性，C1 的“最后一点”会在 SP=63 而不是 575 时成立，
FC1 的“最后一个 index”会在 143 而不是 399 时成立；C1 只覆盖约 1/9 的输出点，
FC1 只累加前 144 个权重。其他计数器（C2 的 7 位 SP、FC 的 5 位 neuron 等）≤8 位，不受影响。

**修法：** 对 9/10 位比较使用两片 688 级联（低 8 位 + 高位与 0 比较，两个 `P=R` 相与），
或改用“计数器 TC 链 + 与门”实现；同时修正生成器，遇到 >8 位直接报错而不是截断。

### V4（严重）FC2 的 requant 握手死锁

**证据（20 ms 时的实测电平）：**

```text
S09_FC2 状态 = 8 (E_REQ)      FC2_REQ_START = 1
S17_FC2 FC_RQ_START_N = 0     FC_RQ_RUN = 1
FC_RQ_BC[2:0] = 000           FC2_REQ_QSTB = 1
FC2_REQ_DONE = 0              MEM_BUSY = 0, MEM_nCE = 1（总线空闲）
```

**机理：**

- FC 微码状态 8 的 ROM 输出固定 `REQ_START=1`，并等待 `REQ_DONE=1` 才转状态 9；
- requant 的字节计数器 74HC161：`~PE = START_N = NOT(REQ_START)`。
  `START=1` 时 `~PE=0`，计数器每个时钟同步装载 0，永远停在 BC=0；
- FC2 的 `REQ_DONE = RUN & (BC0 & BC1 & ~BC2)`，只有 BC=3 才为 1；
- 于是：FC 等 DONE → DONE 等 BC=3 → BC 等 START 变低 → START 等 DONE。死锁。

FC1 不死锁，因为 FC1 的 `DONE` 取的是 `QSTB1`（BC=0 时的组合），不依赖 BC=3；
这也是为什么 FC1 能“完成”（虽然因 V2 提前退出）。

**修法（任选）：**

1. 让状态 8 只保持 `REQ_START` 一个时钟（增加状态 8a，或把 `REQ_START` 改为
   “状态 8 且未请求过”的脉冲）；
2. 字节计数器改为由 `QSTB` 计数，而不是用 `START_N` 做同步装载；
3. FC2 的 DONE 改由 requant 内部两拍序列器产生（与 FC1 一致），BC 只用于字节选择。

### V5（需复核）C1 的 `POINT_LAST` 实际是 `PAD_LAST`

**证据（网表）：**

- U7144（74HC74）D 端 = `C1_PAD_LAST`，Q 端 = `C1_POINT_LAST`；
- `PAD_LAST = PAD0 & PAD1`，PAD 是 2 位计数器，每 4 个 MAC 到 3；
- C1 微码状态 7：`POINT_LAST=1 → 状态 8（requant/输出）`，`=0 → 状态 2（下一个 MAC）`；
- 实测正好 4 次 MAC 循环后进入状态 8。

若设计意图是“25 个 tap 累加完再输出”，这里应在最后一个 pad 且
`KX_LAST & KY_LAST & OX_LAST & OY_LAST & OC_LAST` 时才置 `POINT_LAST`；
当前接法在第一个 4-MAC 组后就转输出，远少于 25 个 tap。请对照 S07 图纸说明确认：
`build_conv1.py` 第 1158 行注释称 PAD 是“4-MAC 累加组”，
但微码把 `POINT_LAST` 当作“整点结束”使用，两者语义不一致。

### V6（观察项，非缺陷）装载口位宽与器件编程方式

- J10005（图像口）只到 A12，正好覆盖 28×28=784 字节的 MNIST 图像（8 KB 空间）；
- J10006（参数口）只到 A14，正好覆盖 28C256 的 32 KB；
- 27C512 是 64 KB UV EPROM，A15 未引出，不能在线装载——但它们本应离线编程。
  如果将来希望在线重写 27C512，需要同时补 A15 和 tag 位。

---

## 5. 对“用 EP4CE10 验证连线”的回答

- **字面复刻不可行**：898 个封装、需 30,144 Kbit 存储（52×27C512、12×28C256、
  7×HY6264，其中仅 ROM 就 27 Mbit），远超 EP4CE10 的 10,320 LE / 414 Kbit；
  即使外挂 32 MB SDRAM，也需要额外的 SDRAM 控制器，
  且时序/引脚数会改变原结构。
- **协议子集可行**：可以把 S01/S02/S10/S11 的握手和地址译码放进 FPGA，
  用 SDRAM 存 ROM 镜像，验证“启动—请求—ACK—DONE”时序；但这不再是逐引脚结构验证。
- **实机路径已打通（2026-11-08）**：Quartus 全流程 0 errors，USB-Blaster v2.12 驱动已装，
  `jtagconfig` 识别到 IDCODE `0x020F10DD`，最小工程已成功配置到 EP4CE10F17。
  但容量限制仍是硬约束，整机复刻无法下载。
- **本轮结论**：PC 上的逐引脚结构仿真已经完成了“连线是否正确”的验证，
  并直接定位到 4 个实机也会发生的确定性缺陷（另有 1 个微码/接线语义问题需复核）。

---

## 6. 复现

```bat
cd /d D:\Document\tempPrj\74Series-CNN\Simulation\rtl
python gen_models.py
python gen_timing_rom.py
python gen_rtl.py
set PATH=C:\intelFPGA\18.0\modelsim_ase\win32aloem;%PATH%
vlib work
vlog -sv models.v cnn74_top.v tb_cnn74.v
vsim -c -voptargs=+acc tb_cnn74 -do "run -all; quit -f"
```

文件：

| 文件 | 作用 |
|---|---|
| `rtl/gen_models.py` | 由 `analysis/pins.json` 生成 23 个按引脚号的行为模型 |
| `rtl/models.v` | 生成的模型（74xx/ROM/SRAM/晶振） |
| `rtl/gen_rtl.py` | 由 `output/top.net` 生成扁平结构顶层 |
| `rtl/cnn74_top.v` | 897 个实例、3809 根 wire 的结构网表 |
| `rtl/gen_timing_rom.py` | 重建 U2001 时序微码（明确标注“重建”） |
| `rtl/tb_cnn74.v` | 复位/装载/读回/READY/START/阶段链测试 |
| `rtl/audit_structure.py` | 三条静态结论的独立复核（688 极性、位宽、装载口位） |
| `rtl/init/*.hex` | 从工程 `model/` 复制的 ROM 镜像 + `timing.hex` |
| `rtl/instance_map.csv` | 每个实例/上拉/串联的 ref、模型、图页 |

---

## 7. 建议的修复顺序

1. **V2 极性**（先修 4 条已确认路径，再统一 23 处命名约定）——不改则所有引擎只跑一个点；
2. **V3 位宽**（C1 SP、FC1 INDEX）——不改则引擎只覆盖部分数据；
3. **V4 FC2 死锁**——不改则整机永远停在 FC2_WAIT；
4. **V1 装载口 tag**——不改则 28C256 无法在线编程（可先用离线编程绕过）；
5. **V5 C1 POINT_LAST 语义**——与微码作者确认 25 tap 的结束条件；
6. 以上修完后重跑本仿真，预期 `C1_DONE` 的 `MEM_nCE` 脉冲数应从 11 增至
   约 23 万级（115200 MAC × 2 次读 + 4608 次写），FC2 应能 DONE，
   整机在 S01 超时（2 s）内完成。

> 本报告只做验证，没有改动 KiCad 主工程或 `output/top.net`。

---

## 8. 静态审计脚本（可重复）

`rtl/audit_structure.py` 对上述三条网表结论做独立检查，不依赖仿真。2026-11-08 输出：

```text
=== 74HC688 outputs feeding a ROM/mux 'last' input ===
  U7016  B04_S07_Conv1          C1_SP_LAST           direct 27C512 address
  U8015  B06_S08_Conv2          C2_SP_LAST           direct 27C512 address
  U9009  B08_S09_FC1            FC_INDEX399          U9011.4->FC_INDEX_LAST
  U9010  B08_S09_FC1            FC_INDEX31           U9011.4->FC_INDEX_LAST
  U9209  B09_S09_FC2            FC_INDEX399          U9211.4->FC_INDEX_LAST
  U9210  B09_S09_FC2            FC_INDEX31           U9211.4->FC_INDEX_LAST

=== 74HC688 width: counter Q bits above bit 7 ignored ===
  U7016  B04_S07_Conv1          C1_SP_LAST     P=0x3F(63)  compares C1_SP0..7, counter has C1_SP9
  U9009  B08_S09_FC1            FC_INDEX399    P=0x8F(143) compares FC_INDEX0..7, counter has FC_INDEX8
  U9209  B09_S09_FC2            FC_INDEX399    P=0x8F(143) compares FC_INDEX0..7, counter has FC_INDEX8

=== H_A bits on connectors ===
  J10005: H_A0..H_A12 (13 bits)
  J10006: H_A0..H_A14 (15 bits)
  missing on every header: [15, 16, 17, 18, 19, 20, 21, 22, 23]
```

说明：

- FC 的 mux 有两个输入（`INDEX399` / `INDEX31`），`FC_SEL` 只选一个：
  FC1 选 399，FC2 选 31；两条输入都在审计里列出，实际生效的是被选中的那条。
- `MATCH0..2` 是 24 位超时计数器的三字节比较（每片 688 比 8 位，三片相与），
  不是截断，审计脚本已把 `MATCH*` 排除。
- `FC_INDEX31`/`FC_NEURON31`/`FC_NEURON9` 的常数 ≤255，8 位比较足够；
  它们不在位宽问题清单里，但仍在 V2 的极性命名清单里。

运行：

```bat
cd /d D:\Document\tempPrj\74Series-CNN\Simulation\rtl
python audit_structure.py
```

---

## 9. 修正后的回归结果（2026-11-08）

第 4 节列出的问题已在 KiCad 工程中修正（V1–V4、V7–V11；V5 复检为误报，
V6 评估后不改），并重新导出网表、重新生成 ROM 映像。整链仿真结果：

| 事件 | 时间 | 写事务 |
|------|------|--------|
| C1_DONE（CONV1，575 点） | 40.51 ms | 577 |
| P1_DONE（POOL1，1152 字节） | 46.85 ms | 1152 |
| C2_DONE（CONV2，1600 点） | 66.80 ms | 1600 |
| P2_DONE（POOL2，400 字节） | 68.99 ms | 400 |
| FC1_DONE（32 神经元） | 104.24 ms | 32 |
| FC2_DONE（10 神经元 × 4 字节） | 105.17 ms | 40 |
| ARGMAX_DONE / DONE | 105.23 ms | — |

```
PASS: RESET_N follows RESET_RAW
PASS: clock reaches CLK_SEL
PASS: status idle after reset
PASS: SRAM0[0..7] 8/8, EEPROM[0..3] 4/4
PASS: IMAGE_READY / MODEL_READY
PASS: DONE pulsed at end of chain
PASS: no error reported
PASS: RESULT_VALID latched
PASS: ARGMAX returns class 0
TB RESULT: PASS
```

修正项与逐引脚差异见 `Cache/CNN_74xx_System/CHANGES_V1_V11_FOR_EASYEDA.md`
与 `Cache/CNN_74xx_System/review/net_diff_v1_v11.txt`。

新增的三个仿真问题（V8/V9/V10）与一个位宽/门控问题（V11）都是**原设计就存在**
的逻辑缺陷，不是本次改造引入的：

- V8 状态译码 Y0 在 state 8 也有效 → 每个输出点清零全部循环计数器；
- V9 写请求保持到 MEM_DONE → 控制器回到 IDLE 时 REQ 仍为高，写执行两遍；
- V10 C2 外层循环使能错位一级 → IC 永不计数；
- V11 FC 神经元计数器重载未受 MAC_EN 门控 → IMAGE_LAST 永不置位。

写入事务数与输出点数一一对应，可作为 V9 的回归判据；FC2 的 40 次写
（10×4）可作为 V4 的回归判据。
