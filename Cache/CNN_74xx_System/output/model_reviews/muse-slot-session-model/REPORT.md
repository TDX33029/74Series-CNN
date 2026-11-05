# 独立模型联合审查报告（Muse 位置替代）

> **模型声明：muse-spark-1.3-contributor 不可用，替代为会话模型 DeepSeek V4.1 Flash。**
> 本报告由第 5 位独立审查员按 `docs/MODEL_REVIEW_BRIEF.md` 执行，不代表原 Muse 模型结论。

- 日期：2026-11-05
- 工程：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System`（主工程只读）
- 规划书：`D:/Document/tempPrj/74Series-CNN/CNN_74xx_MNIST_28x28_v1.txt`
- 隔离副本：`D:/Document/tempPrj/74Series-CNN/Cache/_review_deepseek/work`
- 报告目录：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/output/model_reviews/muse-slot-session-model`
- 环境：Windows 10 x64 / Git Bash / Python 3.10.9 / KiCad 10.0.4 `kicad-cli` / KiCad 自带 `ngspice.dll`（XSPICE d_dff）

---

## 1. 结论摘要

**当前工程不具备制板条件。** 各模块单页的局部逻辑大体成立，但系统级"引擎↔存储器"总线组织整体缺失，且存在三处文档明确否认、但网表可复现的结构性错误：

1. **推理地址/片选通路完全不存在**：`C1_ADDR[15:0]`、`C2_ADDR[15:0]`、`FC_ADDR[15:0]` 全部是单节点全局标签；S04 的 27 片存储器地址 `MADDR[15:0]` 只由主机加载缓冲 U4040/U4041 驱动，`MEM_SEL[4:0]` 只由 S10 主机口驱动。
2. **监督 FSM 的三个启动脉冲没有到达对端**：`P1_START`、`P2_START`、`ARGMAX_START` 只有 S01 内部一个负载；S05/S06 反而直接使用主机 `START`，会在 CONV1 启动的同一拍启动。
3. **`DONE` 被两个 74HCT541 同时推挽驱动**（S01 U1009.17 与 S05 U5039.17），两片的 `G1/G2` 都接地，属于确定的输出冲突。

另外确认：`run_all.py` 9/9 PASS 的测试全部是**自建行为模型**（Python/SPICE 重写状态表和地址公式），没有一条从原理图网表提取逻辑；引擎与 S02 的微码 ROM 镜像根本不存在。因此"9/9 PASS"不能作为图纸正确性的证据。

---

## 2. 我的拓扑理解（用自己的话）

- 一张 A1 根图 S00 只放 9 个层次块符号和连接总表，没有实际连线；所有模块间连接靠**全局标签同名合并**。
- S01 是一个 20 状态的微码 FSM：`2×27C512`（U1001/U1002）出 16 位微码字，低 5 位进 `74HCT273`（U1003）做状态寄存器，`74HCT574`（U1004/U1005）寄存 BUSY/DONE/ERROR/STAGE/TIMEOUT_CLR；`74HC238`（U1006）把 STAGE 译成 STG1..7，再由 `74HCT541`（U1008）缓冲成 C1/P1/C2/P2/FC1/FC2/ARGMAX_START。24 位看门狗由 6 片 `74HC161` 组成。
- S02 是共享的存储器时序控制器：`27C512`（U2001）微码 + `74HCT273`（U2002）状态 + `74HCT574`（U2003）寄存 nCE/nOE/nWE/ACK/DONE；`74HC138`（U2004）做状态译码；`74HC161`（U2006）+ `74HC688`（U2008）做等待计数比较；`74HC157`（U2007）选择读/写等待值；`74HC74`（U2009）把外部 REQ/WE 同步成 REQ_S/WE_S。
- S04 是 27 片存储器的共享阵列：7×6264 特征 SRAM、12×28C256 权重/偏置/qparam、8×27C512 LUT；24 位地址经 4×`74HCT541`（U4040–U4043）从主机口进入，`74HC688`（U4032）比较 `ADDR[23:16]` 与 `MEM_SEL[4:0]`，4×`74HC138`（U4028–U4031）产生 27 个低有效片选；`74HC245`（U4036/U4037）做主机/推理两侧的数据总线隔离。
- S05/S06/S07/S08/S09 是五个"自包含"引擎：局部计数器和比较器生成地址，局部微码 ROM 生成控制，输出经 574/245 上总线。它们的地址总线全部使用模块内名字（`C1_*`、`C2_*`、`FC_*`、`IN_*`、`OUT_*`、`SCORE_*`）。
- S10 提供 8 MHz 晶振/外部时钟选择、复位整形、主机加载口和状态 LED。

**关键理解**：这套图纸把"每个模块能独立评审"做到了，但把"模块之间怎么接"留成了 TODO。S04 实际被接成一块**只能由主机预加载的存储器**，而不是推理引擎的共享存储器。

---

## 3. 测试执行与结果

所有测试在副本中执行；主工程未改动（只读了文档与网表，报告写在主工程 `output/model_reviews/`）。

### 3.1 全量回归

| 命令 | 退出码 | 耗时 | 结果 | 日志 |
|---|---:|---:|---|---|
| `python sim/run_all.py` | 0 | 7 s | **9/9 PASS** | `work/sim/*.log` |

### 3.2 单项测试

| 命令 | 退出码 | 耗时 | 结果 |
|---|---:|---:|---|
| `python tools/gen_lut.py` | 0 | 205 ms | PASS：65536 项穷举 |
| `python sim/gen_lut_tb.py` | 0 | 241 ms | PASS：8 组代表操作数 |
| `python sim/gen_glue_tb.py` | 0 | 219 ms | PASS：11/11 |
| `python sim/gen_supervisor_tb.py` | 0 | 234 ms | PASS：状态序列 |
| `python sim/gen_timing_tb.py` | 0 | 229 ms | PASS：读/写协议 |
| `python sim/gen_mem_decode_tb.py` | 0 | 287 ms | PASS：324 项断言 |
| `python sim/gen_pool_tb.py` | 0 | 840 ms | PASS：10 窗口/40 地址 |
| `python sim/gen_argmax_tb.py` | 0 | 3.8 s | PASS：5 向量 |
| `python sim/gen_engine_tb.py` | 0 | 3.4 s | PASS：CONV1/2 115200 MAC，FC 13120 MAC |
| `python tools/gen_supervisor_microcode.py` | 0 | 275 ms | PASS；重新生成的 bin 与主工程 SHA-256 完全一致 |

**重要限定**：这些测试的"PASS"只证明测试里写的那套公式/状态表自洽。

- `gen_supervisor_tb.py` 在 Python 里重新写了一遍 next-state 表，再用 XSPICE `d_dff` 搭出来，**没有读取 U1001/U1002 的微码镜像，也没有使用原理图网表**。
- `gen_timing_tb.py` 同样是自己写状态表；而且它把读/写等待值写反了（见 M5）。
- `gen_engine_tb.py` 的"SPICE 验证"只是把同一套地址公式用 `floor()` 写成 B 源，再和 Python 黄金模型比对——两边是同一套公式，属于同义反复。
- `gen_pool_tb.py`/`gen_argmax_tb.py` 是寄存器级行为模型，不是从 S05/S06 网表提取的。

### 3.3 ERC / 网表导出

| 命令 | 退出码 | 耗时 | 结果 |
|---|---:|---:|---|
| `kicad-cli sch erc --severity-all`（顶层） | 0 | 10 s | 940 项：**42 error / 898 warning** |
| `kicad-cli sch export netlist --format kicadsexpr` | 0 | 2 s | 2,556,384 字节，2775 网，861 元件 |
| 逐页 ERC（9 张） | 0 | 2.5–3.1 s/页 | 与 `FINAL_STATUS.md` 表格逐项一致 |

顶层 42 个 error 的构成（与文档一致）：`SCORE_DATA[31:0]` 32 网、`IN_DATA[7:0]` 8 网、`POOL_SEL`、`FC_SEL`。**但 ERC 没有报告 `DONE` 双驱动**——因为两片都是三态 541，KiCad ERC 不做三态冲突分析。所以"没有重复驱动/输出冲突"的结论不能由 ERC 得出。

---

## 4. 联合逻辑验证

按要求做了三种（超过"至少两种"）。

### 4.1 A：S01 微码 → 启动选通 → 引擎（`harness_s01_handshake.py`）

方法：直接执行 `model/microcode/supervisor_lo.bin` + `supervisor_hi.bin` 作为 U1001/U1002 的 64K×16 内容，地址按原理图 `A[4:0]=ST, A5=START, A6=IMG, A7=MDL, A8..A14=DONE, A15=TIMEOUT` 组装；得到的状态字再经"STAGE→74HC238→74HCT541→全局网名"映射，用导出的网表统计每个启动网的真实负载。

结果：

- **PASS**：状态序列 `0→1→2→3→4→5…→16→17→18→2`；每个 WAIT 只认自己的 done；超时进 19；ERROR 粘滞；未就绪启动进 19；`START` 长高时停在 18；`G_FINISH` 同时置 DONE 和 RESULT_VALID。
- **FAIL**：`P1_START`、`P2_START`、`ARGMAX_START` 各只有 1 个负载（U1008 自己的输出脚），没有到达 S05/S06。
- **FAIL**：`DONE` 有 2 个推挽驱动：`U1009.17`（S01 74HCT541）与 `U5039.17`（S05 74HCT541），两片 G1/G2 均接地。

### 4.2 B：S02 ↔ S04 存储事务（`harness_s02_s04_transaction.py`）

方法：从网表提取每个 245 的 OE/DIR 源、每个 138 的使能、688 的 P/R 连接、MADDR/MEM_SEL 的驱动者，再按 74xx 真值表枚举。

结果：

- **FAIL**：`REQ`、`WE` 只有测试点 + U2009 的 D 脚，**没有驱动**。时序控制器永远不会收到请求。
- **FAIL**：`MEM_ACK`、`MEM_DONE`、`MEM_BUSY` 只到 TP2007/TP2008/TP2009，**没有输入消费者**。
- **FAIL**：`C1_ADDR*`、`C2_ADDR*`、`FC_ADDR*` 各 16 网，**0 个到达 S04**。
- **PASS**：`MADDR0..15` 只由 U4040/U4041 驱动（主机加载 541）；`MEM_SEL0..4` 只由 U10096（S10）驱动。
- **PASS**：32 个 `MEM_SEL` 一一选中对应器件；地址标签不符不选中；64 KB 窗口内片选稳定。
- **PASS**：硬件等待值确实为 read=3、write=2（U2007 I0=`0011`、I1=`0010`）。
- **FAIL**：S02 的 `74HC138`（U2004）输出 `CAPTURE_N`、`WAIT_N`、`HOLD_N`、`RELEASE_N`、`DONE_ST_N` **全部无负载**；只有 `IDLE_N`、`SETUP_N` 被使用。
- **FAIL**：`DONE` 双驱动（同上）。

### 4.3 C：级间地址布局一致性（`harness_datapath_layout.py`）

方法：按 S05/S07/S08/S09 图纸注释里的地址公式，逐元素枚举每条边界。

| 边界 | 结果 |
|---|---|
| CONV1_OUT → POOL1 | PASS 4608/4608 |
| **POOL1_OUT → CONV2** | **FAIL：7200 次读中 7198 次地址错；1152 字节只有 2 字节按原地址读回** |
| CONV2_OUT → POOL2 | PASS 1600/1600 |
| POOL2_OUT → FC1 | PASS 400/400（CHW 展平） |
| FC2 logits → ARGMAX | PASS（40 字节，4n+b，little-endian） |

POOL1 按 CHW 写：`c*144 + y*12 + x`；CONV2 按 HWC 读：`(oy+ky)*96 + (ox+kx)*8 + ic`。两者不是同一个布局。这是独立于"总线没接"的第二个功能错误。

---

## 5. 发现的问题（按严重度）

### BLOCKER

**B1. 推理地址/片选通路整体缺失**
`C1_ADDR[15:0]`（U7147/U7148）、`C2_ADDR[15:0]`（U8150/U8151）、`FC_ADDR[15:0]`（U9137/U9138）都是单节点网；S04 的 27 片存储器地址只来自 U4040/U4041（主机 `ADDR[23:0]`），片选只来自 `MEM_SEL[4:0]`（S10 主机口）。推理时没有任何信号能改变存储器地址或片选。**系统无法执行一次推理。**

**B2. P1/P2/ARGMAX 启动脉冲未接，S05/S06 由主机 START 直接启动**
U1008 的 `P1_START`(Y1)、`P2_START`(Y3)、`ARGMAX_START`(Y6) 各只有 1 个节点；S05 的启动输入是 U5036.1/U5037.5 上的 `START`，S06 是 U6036.4/U6037.5 上的 `START`。主机一按 START，POOL1/POOL2/ARGMAX 与 CONV1 同拍启动。

**B3. `DONE` 双推挽驱动**
`U1009.17`（S01 74HCT541，`G1=G2=GND` 常使能）与 `U5039.17`（S05 74HCT541，`G1=G2=GND` 常使能）同时驱动全局 `DONE`。S05 的 `DONE` 还被本页 U5041.1/U5041.4 读回。上电后两片必然对拉，可能损坏芯片或造成 DONE 随机跳变。

**B4. S02 时序控制器没有请求输入，握手输出没有消费者**
`REQ`/`WE` 悬空；`MEM_ACK/MEM_DONE/MEM_BUSY` 只到测试点；`MEM_DATA[7:0]`（U2010 A 侧）是单节点浮空网。三个 `S02_MEM_IF` 块符号（U7145/U8148/U9135）没有内部电路、封装为空，其 `WAIT_READ/WAIT_WRITE` 引脚也是单节点。**存储器事务在原理图上无法发起、无法确认。**

**B5. 推理读方向反了，且写期间有总线竞争**
S04 `U4036`（245）：`OE=LOAD_EN_I`，`DIR=READ_DIR=NOT(DIR_SEL)`；推理模式 `LOAD_EN=0` → `DIR_SEL=1` → `READ_DIR=0` → B→A，即 **DATA 驱入 MEM_D**（写方向）。读操作时存储器驱动 MEM_D，与 U4036 对拉。
同时 `U2010`（S02 245）`OE=MEM_nCE`，任何事务期间都使能，而其 A 侧 `MEM_DATA[7:0]` 浮空 → 会向 `DATA` 输出不确定电平，与引擎的 245（U7127/U8131/U9117）对拉。

**B6. POOL1→CONV2 布局不一致**
见 4.3：7198/7200 次读地址错，1152 字节只有 2 字节正确。违反规划书 §2.1 的 CHW 契约。

### CRITICAL

**C1. Pool/Argmax 的输入输出总线全部悬空**
`IN_DATA[7:0]`（8 网，接 U5012/U5013 的 74HC85 A 侧）、`IN_ADDR[12:0]`、`OUT_ADDR[11:0]`、`OUT_DATA[7:0]`、`OUT_WE`、`SCORE_DATA[31:0]`、`SCORE_ADDR[5:0]`、`SCORE_RD` 都是单节点或仅页内。S05/S06 是"只算不存"的空转电路。

**C2. 引擎/时序微码 ROM 没有镜像**
`model/microcode/` 只有 supervisor 的 `lo/hi.bin`；`model/lut/` 只有 LUT。S07/S08/S09 的 `U7136/U7137`、`U8130/U8131`?（实际为各引擎 2×27C512）和 S02 的 `U2001` 没有任何生成器或 bin。ROM 为空（0xFF）时引擎状态机行为未定义。**"115200 MAC + 全地址序列 SPICE PASS"只是行为模型，不是这些 ROM 的验证。**

**C3. 时钟/复位扇出超标**
`CLK` 网 136 节点：132 个 input，由单个 `74HC04` 门经 33 Ω 串阻驱动（`U10070.10 → R10005 → CLK`），无时钟缓冲/树。`RESET_N` 45 节点：42 个 input，单个 74HC04 输出驱动。按 8 MHz、5 V、约 3.5 pF/输入估算，CLK 负载约 460 pF，动态电流远超 74HC04 的 ±5.2 mA 能力；边沿和 skew 不可控。

**C4. 18 个块符号未展开，BOM 490 片不完整**
`LUT_Mult_Unit×12`、`Requant_Block×3`、`S02_MEM_IF×3` 封装为空。Requant 被描述为"32×16 串行乘法器 + 64 位积 + 移位/舍入/饱和"，若用 74 系列实现，每块至少几十片；LUT 块若按 S_LUT_Mult_1 展开，每块 2×27C512 + 4×574。**实际可制造芯片数远大于 490。**

### MAJOR

**M1. 去耦严重不足**：BOM 171 个电容 / 490 片 IC = 0.35 个/片；文档称"每个 IC 一个 100 nF"。按 0.1 µF/IC 至少需要约 490 个。

**M2. 没有同步复位释放**：`RESET_N` 直接进所有异步清零脚（74HCT273/574/161/74HC74），没有两级同步器。复位释放相对 CLK 是异步的，不同触发器可能在不同时钟沿退出复位。

**M3. `POOL_SEL`、`FC_SEL` 没有源**：`POOL_SEL` 7 个输入 0 驱动；`FC_SEL` 13 个输入 0 驱动。S05 无法选择 POOL1/POOL2，S09 无法选择 FC1/FC2。

**M4. 等待值固定、不可按器件配置**：U2007 硬接 read=3/write=2，规划书 §7.1 要求按 6264/28C256/27C512 分别配置。8 MHz 下 3 拍 = 375 ns，对 6264(70 ns)/28C256(150 ns)/27C512(90 ns) 足够；但没有逐器件时序预算文件，也没有把等待值做成可配置。

**M5. `gen_timing_tb.py` 的等待值与硬件相反**：TB 用 `waitr=2, waitw=3`；U2007 实际 read=3、write=2。TB 的 PASS 不覆盖真实配置。

**M6. 文档声称"无重复驱动/输出冲突"与实际不符**：`FINAL_STATUS.md`、`HW_MANUAL.md` §10、`INTEGRATION_NOTES.md` §4 都写了"没有短路、重复驱动或输出冲突"。网表证明 `DONE` 有两个常使能推挽驱动，`DATA[7:0]` 每根有 5 个 245 驱动源（U2010/U4036/U7127/U8131/U9117，方向/OE 组合存在竞争）。

**M7. 图纸文字与实际不符**：S00 根图/连接矩阵把 S05 描述为 "Pool1 2x2 stride-2 (12x12x8 -> 6x6x8)"，实际应为 24×24×8 → 12×12×8（S05 页内注释是正确的）。

### MINOR

- **m1**：`INTEGRATION_NOTES.md`/`HW_MANUAL.md` 写"BOM 262 个唯一位号"，实际网表 861 个唯一位号（59 行分组，合计 861 件）。
- **m2**：`CONNECTION_MATRIX.md` 的"`+5V/GND` 只出现在 S07–S09"是全局标签统计方法的产物，实际所有页都用电源符号。
- **m3**：8 KB SRAM 在 64 KB 窗口内 8 倍别名、32 KB EEPROM 2 倍别名（未译码 A13..A15），文档已声明为已知限制。
- **m4**：74HC238 的 Y0、74HCT541 的 Y7 未用；无影响。
- **m5**：24 位看门狗 2²⁴ 拍在 8 MHz 是 2.097 s；若改用 10–100 Hz 外部时钟，超时变成 46.6 h–19.4 天，失去"卡死保护"意义。图纸没有 10–100 Hz 分频器，只有 8 MHz 晶振或外部时钟输入。

### INFO（确认正确的部分）

- 微码状态序列、超时分支、WAIT_START_LOW、未就绪拒绝：正确。
- 74HC688 `P=R` 低有效输出后都做了反相（U4032→U4033、U2008→U2012、S01 的 IDLE/TIMEOUT 同理）：极性正确。
- 74HC138 低有效输出直接驱动 `nCS_*`：正确。
- 74HC245 的 `OE` 低有效：用法正确（问题在使能条件/方向，不在极性）。
- S06 有符号 Argmax：`SCORE31`/`MAX31` 经 U6003 反相后接 U6021 的 A3/B3，级联来自 U6020，LSB 级联常数 `Ia=b=1, Ia<b=0, Ia>b=0`：offset-binary 比较正确。
- S05 的 74HC85 无符号比较：级联常数正确，`GT` 用于严格大于（等值不更新）：符合"并列取小号"。
- LUT 内容：65536 项穷举通过；8 片 27C512 的 LO/HI 划分与规划书一致。
- 861 个位号无重复；封装字段除 18 个块符号外均有值。

---

## 6. 与现有文档/结论的冲突

| 现有结论 | 本次证据 | 判定 |
|---|---|---|
| `run_all.py` 9/9 PASS 证明功能正确 | 9 个 TB 都是自建行为模型，未读原理图/微码镜像 | **PASS 只覆盖 TB 自己的断言** |
| 顶层 42 error 全部是外部输入，无重复驱动/短路 | `DONE` 两个常使能推挽驱动；`DATA[7:0]` 每根 5 个 245 源 | **错误** |
| P1/P2/ARGMAX done 链已接通（`INTEGRATION_NOTES` §2） | 三个 START 脉冲无负载；S05/S06 由主机 START 启动 | **只接通了 done，没接通 start** |
| 各引擎 `*_BUSY/RESULT_VALID` 已改为唯一名字，不再竞争 | `C1_BUSY`/`C2_BUSY`/`ARGMAX_BUSY`/`ARGMAX_RESULT_VALID` 都是单节点，根本没送到 S01 | **未接通** |
| 74HC245 的 CE 改为 MEM_nCE 消除空闲竞争 | 事务期间 U2010 反而以浮空 MEM_DATA 驱动 DATA；推理读方向反 | **引入了新的竞争** |
| BOM 262 唯一位号、约 861 件 | 网表 861 个唯一位号 | **数字口径错误** |
| 每个 IC 一个 100 nF 去耦 | 171 个电容 / 490 片 IC | **不成立** |
| S05 "12x12x8 -> 6x6x8" | 实际 24x24x8 -> 12x12x8 | **文字错误** |
| 总线适配层是"后续工作" | 与本次结论一致；但这是 BLOCKER，不是普通 TODO | **承认缺口但低估严重度** |

---

## 7. 制板前必须修的事项（按顺序）

1. **补齐系统总线组织**：为 S04 增加地址/片选多路选择（主机加载 vs 引擎推理），把 `C1_ADDR/C2_ADDR/FC_ADDR`、`C1_MEM_nCE_*` 等真正接到 `MADDR/MEM_SEL/nCS_*`；给 S05/S06 增加 `IN_DATA/OUT_*/SCORE_*` 的存储器接口。否则整板无法推理。
2. **重做启动/完成握手**：`P1_START/P2_START/ARGMAX_START` 接到 S05/S06；S05/S06 删除对主机 `START` 的直接连接；S05 的本地 done 改用独立网名（如 `POOL_DONE_I`），不要驱动全局 `DONE`；`DONE` 只保留 S01 一个驱动。
3. **修正数据总线方向/使能**：推理读时 `U4036 DIR` 必须为 A→B；`U2010` 要么删除，要么把 A 侧接到真正的捕获寄存器并只在读事务使能；所有 245 的 OE 做严格互斥（任一时刻最多一个源）。
4. **补齐 S02 请求/应答**：`REQ/WE` 由引擎产生；`MEM_ACK/MEM_DONE/MEM_BUSY` 回送引擎；展开 `S02_MEM_IF` 或删除这些占位块；给出 `U2001` 的微码镜像。
5. **修正 POOL1→CONV2 布局**：二选一——CONV2 改 CHW（`ic*144 + (oy+ky)*12 + (ox+kx)`），或 POOL1 改 HWC；并同步修改 `gen_engine_tb.py` 的黄金模型。
6. **给出所有引擎微码 ROM 镜像**（CONV1/CONV2/FC），并用镜像驱动仿真；否则 FSM 未定义。
7. **展开 18 个块符号**（尤其 Requant 32×16 串行乘法器），重新出 BOM；按实际芯片数补去耦（≥1 个 100 nF/IC）和电源预算。
8. **时钟/复位分配**：加时钟缓冲树（例如 74HCT244/541 分组），把 CLK 每路扇出降到 ≤10；RESET_N 加两级同步释放。
9. **补 `POOL_SEL`/`FC_SEL` 来源**（阶段译码或配置锁存），并确认上电默认值。
10. **补时序预算**：按 8 MHz 给出每个器件的 tAA/tCE/tOE/tWP/tDH 与等待拍数，替换 `gen_timing_tb.py` 中与硬件相反的等待值。

---

## 8. 不确定 / 未能验证的事项

1. **S02 微码内容**：`U2001` 无镜像，无法判断 `nCE/nOE/nWE/ACK/DONE` 的实际时序。现有 TB 的时序结论**不适用于硬件**。
2. **引擎微码内容**：S07/S08/S09 的 27C512 无镜像，无法验证 11 状态序列、`MEM_REQ/MEM_WE/OUT_STB/ADD_SEL` 的真实时序。
3. **Requant_Block 内部**：无子图、无行为模型；32×16 串行乘法、64 位积、舍入/饱和/零点修正均未验证。规划书 §2.5 的位精确要求无法确认。
4. **10–100 Hz 时钟**：图纸只有 8 MHz 晶振或外部时钟，没有 10–100 Hz 分频器。若外部注入 10–100 Hz，等待拍数在功能上仍成立（更慢），但看门狗失去意义；未做实际波形验证。
5. **模拟/电气特性**：未做 IBIS/负载/传输线/电源完整性分析；CLK/RESET 扇出结论是基于 74HC 典型输入电容的估算，未实测。
6. **28×28 模型**：仓库仍缺 28×28 权重/qparam（`HW_MANUAL` §10.1 已承认），端到端逐位一致无法验证；本次只验证了地址布局与握手，不涉及数值正确性。
7. **`DONE` 对拉的实际后果**：未做上电/短路电流实测；结论基于两片 541 的 G1/G2 均接地这一网表事实。
8. **S06 的 `SCORE_DATA` 4 字节拼装**：S06 注释说由 S04/S10 的存储接口拼装，但该接口不存在；无法验证小端序拼装与 32 位符号扩展。

---

## 9. 可复现产物

- `REPORT.md`（本文件）
- `findings.json`：机器可读发现列表
- `commands.log`：命令、退出码、耗时
- `harness_s01_handshake.py` + `harness_s01.log`
- `harness_s02_s04_transaction.py` + `harness_s02.log`
- `harness_datapath_layout.py` + `harness_layout.log`
- `net_audit.py`、`nl_query.py`、`net_audit.json`、`net_audit_stdout.txt`
- `evidence/top.net`（导出网表）、`evidence/top-erc.rpt`、`evidence/sheets/*.rpt`（逐页 ERC）

复现命令（在副本中）：

```bash
cd D:/Document/tempPrj/74Series-CNN/Cache/_review_deepseek/work
python sim/run_all.py
"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc --severity-all -o review_out/erc/top-erc.rpt CNN_74xx_System.kicad_sch
"/c/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist --format kicadsexpr -o review_out/net/top.net CNN_74xx_System.kicad_sch
cd D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/output/model_reviews/muse-slot-session-model
python harness_s01_handshake.py evidence/top.net ../../../../_review_deepseek/work/model/microcode
python harness_s02_s04_transaction.py evidence/top.net
python harness_datapath_layout.py
```
