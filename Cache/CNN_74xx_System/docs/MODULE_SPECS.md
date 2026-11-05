# 模块绘制与仿真任务规格（子代理用）

所有模块位于 `Cache/CNN_74xx_System`。先读 `docs/HW_ARCH_CONTRACT.md`。
必须复用 `tools/kicad_gen.py`、`tools/symbol_lib.py`，参考 `tools/build_supervisor.py` 与 `tools/build_timing.py` 的写法。
不允许修改已有的 `S01_Supervisor.kicad_sch`、`S02_Timing.kicad_sch`、`S_LUT_Mult_1.kicad_sch`、`tools/*`（可新增脚本）。
每张图使用 A1/A2 纸张、真实 74 系列/存储器符号、短线+网络标签连接；每个引脚必须接线、接地/电源或显式 NC。
输出 PDF 到 `output/pdf/`，ERC 报告到 `output/`，SPICE testbench 到 `sim/`，结果日志到 `output/sim/`。

## 通用约定

- 单时钟 `CLK`，低有效复位 `RESET_N`；start/busy/done 同步单拍。
- 所有内部网络使用局部标签；跨模块接口使用全局标签。
- 74HC/HCT 5V；存储器：6264、28C256、27C512。
- SPICE 使用 `tools/ngspice_runner.py`（KiCad 自带 ngspice.dll）。
- XSPICE `d_dff` 可用：`.model ddff d_dff()`，A 器件端口顺序 `d clk set reset q qbar`。
- B 源条件表达式用 C 三元 `cond ? a : b`，不要用 `if()`。
- 采样用 `wrdata` 后按 `(time,value)` 成对解析；在时钟沿后 20–30ns 采样，避免状态位偏斜毛刺。
- 外部输入未驱动的 ERC error 可以记录为“单页仿真/待顶层连接”，但不得有重复驱动、短路、悬空输出。

## 1. POOL 引擎（S05_Pool）

- 文件：`S05_Pool.kicad_sch`；同时覆盖 POOL1/POOL2，用参数/注释区分。
- 功能：2×2 窗口、stride 2、VALID、CHW、unsigned max、单端口 SRAM 四次读。
- POOL1：C=8,H=24,W=24 → 12×12×8；POOL2：C=16,H=10,W=10 → 5×5×16。
- 接口（全局标签）：CLK, RESET_N, START, POOL_SEL（0=POOL1,1=POOL2）, IN_DATA[7:0], IN_ADDR[12:0], OUT_DATA[7:0], OUT_ADDR[11:0], OUT_WE, BUSY, DONE。
- 建议器件：74HC161（c/oy/ox 计数器）、74HC283（地址相加）、74HC157（地址/数据选择）、74HC85（unsigned max 比较）、74HCT574（max 寄存器/输出寄存器）、74HC138/74HC32（控制译码）、27C512 或 74HC174 实现局部 FSM。
- 图面必须标注四值读取顺序：v0=(2oy,2ox), v1=(2oy,2ox+1), v2=(2oy+1,2ox), v3=(2oy+1,2ox+1)。
- SPICE：`sim/gen_pool_tb.py` + `sim/tb_pool.cir`；验证 4 个窗口值（含相等、最大值在 4 个位置轮换、0/255 边界），PASS 日志。
- PDF：`output/pdf/S05_Pool.pdf`。

## 2. ARGMAX（S06_Argmax）

- 文件：`S06_Argmax.kicad_sch`。
- 功能：读 10 个 signed32 little-endian 分数；先 class0 初始化 max；class1..9 有符号比较；严格大于才更新（并列取小编号）；输出 4 位类别。
- 接口：CLK, RESET_N, START, SCORE_DATA[31:0]（或 SCORE_BYTE[7:0]+BYTE_SEL）, SCORE_ADDR[5:0], SCORE_RD, RESULT[3:0], RESULT_VALID, BUSY, DONE。
- 建议器件：74HC161（class/byte 计数器）、74HCT574（32 位 score/max/index 寄存器）、74HC85 级联（signed 比较；最高位取反实现有符号）、74HC688（相等检测）、74HC157/74HC138（字节选择/控制）、局部 FSM。
- 图面注明：signed 比较不能按 uint32；tie 不更新。
- SPICE：`sim/gen_argmax_tb.py` + `sim/tb_argmax.cir`；覆盖正负分数、最大值在首/尾、并列最大、-2^31/2^31-1 边界，PASS 日志。
- PDF：`output/pdf/S06_Argmax.pdf`。

## 3. 存储器阵列（S04_Memories）

- 文件：`S04_Memories.kicad_sch`。
- 内容：
  - 7×6264（8K×8）：INPUT、CONV1_OUT、POOL1_OUT、CONV2_OUT、POOL2_OUT、FC1_OUT、FC2_LOGITS。
  - 4×28C256 权重：CONV1 200B、CONV2 1152B、FC1 12800B、FC2 320B。
  - 4×28C256 偏置：8/16/32/10 ×int32。
  - 4×28C256 qparam：8/16/32/10 ×16B。
  - 4×27C512 LUT 对（8 片）+ 可选监督微码 ROM 位置（注释）。
  - 74HC138/74HC688 地址译码、74HC245 数据缓冲、加载/编程接口（连接器）、READY 标志。
- 接口：CLK, RESET_N, ADDR[23:0], DATA[7:0], nCE/nOE/nWE 分组, MEM_SEL[4:0], LOAD_EN, IMAGE_READY, MODEL_READY。
- 图面必须体现每片独立片选、独立地址空间，不做地址复用。
- 可只做“阵列级 + 片选译码”接线，不必把每个地址位都画到每条总线；但每片 IC 的电源、片选、OE/WE、数据/地址端口必须有明确网络标签。
- 简单 SPICE 或 Python 地址译码测试：验证 7 个 feature SRAM 与 4+4+4 参数存储器的片选唯一性，PASS 日志。
- PDF：`output/pdf/S04_Memories.pdf`；BOM 片段 `output/S04_BOM.csv`。

## 4. 顶层 I/O（S10_Top_IO）

- 文件：`S10_Top_IO.kicad_sch`。
- 内容：CLK 振荡器/输入、RESET_N 复位监督、START/IMAGE_READY/MODEL_READY 输入、BUSY/DONE/RESULT_VALID/ERROR/RESULT[3:0] 输出、ERROR_CODE[3:0]、图像加载接口、权重/参数编程接口、测试点、电源入口与去耦。
- 建议器件：74HC04/74HC74（复位/同步）、74HCT541/74HCT245（缓冲）、连接器、晶振/时钟模块（可用 8MHz 有源振荡器符号或外部 CLK 连接器）、LED+电阻。
- 接口与顶层 S00 一致；不得改变已有模块的全局网络名。
- PDF：`output/pdf/S10_Top_IO.pdf`。

## 5. CONV1 / CONV2 / FC 引擎（S07/S08/S09）

- 文件：`S07_Conv1.kicad_sch`、`S08_Conv2.kicad_sch`、`S09_FC.kicad_sch`。
- 采用“功能块 + 真实 74 系列接口”层次：
  - 地址生成：74HC161 计数器链 + 74HC283 加法器 + 74HC157 选择。
  - MAC：4× LUT 乘法单元（引用 S_LUT_Mult_1 的接口与网络名）+ 32 位累加器（74HC283×8 + 74HCT574×4）。
  - V2 requant：S13/S15/S17 固定移位钳位；Conv1 `>>8`、Conv2 `>>9`、FC1 `>>8`，FC2 原始 signed32 四字节 LE；无 bias/零点/乘法器/参数口。
  - 局部 FSM：27C512 微码 + 74HCT273/74HCT574 状态/输出寄存器。
  - 存储器接口：ADDR/DATA/nCE/nOE/nWE/ACK，引用 S02 时序控制器的信号名。
- CONV1 参数：H=28,W=28,Cin=1,Cout=8,K=5,Hout=24,Wout=24；25 MAC/点。
- CONV2：H=12,W=12,Cin=8,Cout=16,K=3,Hout=10,Wout=10；72 MAC/点。
- FC1：400→32，uint8 + ReLU；FC2：32→10，原始 signed32，little-endian 4 字节（S17）。
- 接口统一：CLK, RESET_N, START, IN_DATA[7:0], W_DATA[7:0], B_DATA[31:0], Q_DATA[127:0], OUT_DATA[7:0], OUT_ADDR[..], OUT_WE, BUSY, DONE。
- 图面必须标注循环顺序、地址公式、输出顺序；不得只放符号不接线。
- SPICE/Python：每个引擎生成地址序列测试（`sim/gen_conv1_tb.py` 等），验证 oc/oy/ox/ky/kx/ic 循环与 MAC 计数（CONV1 115200、CONV2 115200、FC1 12800、FC2 320），PASS 日志。
- PDF：`output/pdf/S07_Conv1.pdf`、`S08_Conv2.pdf`、`S09_FC.pdf`、`S13_Requant_C1.pdf`、`S15_Requant_C2.pdf`、`S17_Requant_FC.pdf`。

## 交付报告

每个代理写 `docs/REPORT_<module>.md`：完成内容、ERC 摘要、仿真 PASS/FAIL、已知限制、复现命令。
不得声称“全部通过”而没有日志/PDF 证据。
