# S11 总线适配层修复报告（M-02/M-03/M-06/M-07 总线部分，隔离副本验证）

日期：2026-11-05  
隔离副本：`D:/Document/tempPrj/74Series-CNN/Cache/_repair_bus/work`  
主工程：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System`（只读；本报告与 patch 写在主工程 `output/model_reviews/repair_bus/`）  
设计依据：`docs/BUS_FABRIC_REPAIR_PLAN.md` 第 3–7 节

## 0. 结论

| 项目 | 结果 |
|---|---|
| S11_BusFabric | 已生成：4×74HC148、27C512 map ROM、2×74HC157、2×74HCT541、74HC32+74HC08，共 11 片 + 11 去耦 + 3 TP |
| 引擎 S07/S08/S09 | 已删除 3 个 `S02_MEM_IF` 占位块；`MEM_*`/`Cx_MEM_REQ/WE` 全局化；地址 541 OE 改为 `Cx_BUSY_N`；增加共享握手监测 541 + 6 TP |
| S02 | 删除 U10（MEM_DATA 74HC245），U1..U12 中只保留 11 片；REQ/WE 由 S11 驱动；MEM_ACK/DONE/BUSY 保持全局 |
| S01 | 用微码 spare 位 13/14 产生 `POOL_SEL`/`FC_SEL`（U1005 Q5/Q6），未改状态序列 |
| S04 | 增加 6×74HCT541 引擎地址二级缓冲（U4044..U4049），把 C1/C2/FC_ADDR 汇入共享 ADDR[15:0]；U40/U41 仍是 MADDR 唯一驱动 |
| 顶层审计 | 单节点模块网 90 → **4**；未展开总线 27 → 21；`done_multidriver=false` |
| 仿真 | `sim/run_all.py` **9/9 PASS** |
| Harness A | 59 PASS / 2 FAIL，与基线完全相同（2 个微码模型期望差异，非本次改动） |
| Harness B | 29 PASS / 6 FAIL，基线为 26 PASS / 9 FAIL；剩余 5 个是“MEM_SEL 只能由主机驱动”的过期检查，1 个是基线已有的 S02 未用 138 输出 |
| 布局 harness | **PASS（0 failures）** |
| 顶层 ERC | 42 error → **40 error**（全部仍在 S05/S06 `pin_not_driven`），无新增 error 类型；warning 895 → 829 |
| 主工程修改 | 无。除本报告目录外未写入主工程 |

## 1. 修改文件

工具：

| 文件 | 修改 |
|---|---|
| `tools/gen_bus_map.py` | 新增。生成 27C512 映射镜像 `model/busmap/bus_map.bin/.hex/.csv`，含 24 个映射地址与抽查断言 |
| `tools/build_bus.py` | 新增。生成 `S11_BusFabric.kicad_sch` |
| `tools/build_conv1.py` | 删除 `S02_MEM_IF` 实例；`C1_MEM_*`/REQ/WE/BUSY_N 全局化；区域 138 改由共享 `MEM_nCE` 使能；地址 541 OE 改 `C1_BUSY_N`；加状态监测 541；ROMA A7 改全局 `MEM_ACK` |
| `tools/build_conv2.py` | 同上（C2） |
| `tools/build_fc.py` | 同上（FC）；`FC_BUSY` 直接全局化 |
| `tools/build_timing.py` | 删除 U10 74HC245；去耦 12→11；删除 `MEM_DATA/DATA` 的 S02 全局标签；更新说明 |
| `tools/build_supervisor.py` | GLOBAL 增加 `POOL_SEL/FC_SEL`；U5 Q5/Q6 接出；说明更新 |
| `tools/gen_supervisor_microcode.py` | 微码 bit13=POOL_SEL（P2 状态 9/10），bit14=FC_SEL（FC2 状态 13/14）；不改变状态迁移 |
| `tools/build_memories.py` | 增加 6×74HCT541 引擎地址汇入缓冲 U4044..U4049（OE=Cx_BUSY_N）；去耦 42→48；说明更新 |
| `tools/build_top.py` | 增加 S11 sheet（page 11）、模块表、net_hints、审查备注；根图备注/表格位置调整 |
| `tools/strip_pwr_flags.py` | 加入 S11 |
| `tools/renumber_refs.py` | S11 位号块 12000 |

生成物（均在副本内重新生成）：

`S01_Supervisor.kicad_sch`、`S02_Timing.kicad_sch`、`S04_Memories.kicad_sch`、`S07_Conv1.kicad_sch`、`S08_Conv2.kicad_sch`、`S09_FC.kicad_sch`、`S11_BusFabric.kicad_sch`、`CNN_74xx_System.kicad_sch`、`model/microcode/*`、`model/busmap/*`、`docs/CONNECTION_MATRIX.md`、`output/connection_matrix.csv`。

## 2. S11 结构与端口

### 2.1 器件

| 位号 | 器件 | 功能 |
|---|---|---|
| U12001 | 74HC148 | master 编码（C1>C2>FC） |
| U12002/3/4 | 74HC148 | C1/C2/FC 区域编码 |
| U12005 | 27C512 | `{FC_SEL,MASTER,REGION,0} -> MEM_SEL[4:0]` |
| U12006 | 74HC157 | 区域 mux 第 1 级（C1 vs C2） |
| U12007 | 74HC157 | 区域 mux 第 2 级（conv vs FC） |
| U12008 | 74HCT541 | `ADDR[23:16]={000,MEM_SEL}` 标签缓冲 |
| U12009 | 74HCT541 | `MEM_SEL[4:0]` 缓冲 |
| U12010 | 74HC32 | REQ 2 级 OR + WE 两项 OR（4 门全用） |
| U12011 | 74HC08 | 3 个 REQ&WE 项 + `ANY_CONV_N=C1_BUSY_N&C2_BUSY_N`（4 门全用） |
| TP12001..3 | TestPoint | `MEM_ACK/MEM_DONE/MEM_BUSY` 可见性 |
| C12001..11 | 100n | 每片一顆去耦 |

说明：KiCad 10 的 74xx 库没有 74HC148 符号，本图使用引脚兼容的 `74xx:74LS148` 符号、Value/Footprint 标为 74HC148、DIP-16。**实际 BOM 必须采购 74HC148（CMOS），不要装 74LS148**：74LS148 的 VOH≈2.7 V，低于 74HC/27C512 的 VIH≈3.15 V，存在电平兼容风险。

### 2.2 端口（全局标签）

输入：`C1_BUSY_N, C2_BUSY_N, FC_BUSY_N`；`C1/C2/FC_MEM_nCE_IN/W/OUT/B/Q/MC`（18）；`C1/C2/FC_MEM_REQ/WE`（6）；`FC_SEL`；`LOAD_EN`。  
输出：`REQ, WE`；`MEM_SEL0..4`；`ADDR16..23`。  
直通/广播：`MEM_ACK, MEM_DONE, MEM_BUSY`（S11 只放测试点，真正消费者在 S07/S08/S09）。  
无时钟/复位。

### 2.3 优先级与使能

- master：`C1_BUSY_N` 接 U1 I6，`C2_BUSY_N` 接 I5，`FC_BUSY_N` 接 I4；148 输出为反码，取 S1/S0 得 MASTER 1/2/3。优先级 C1>C2>FC。
- 区域 mux：U6 `S=C1_BUSY_N`，I0=C1、I1=C2；U7 `S=ANY_CONV_N=C1_BUSY_N&C2_BUSY_N`，I0=conv、I1=FC。与 master 同优先级。
- 区域编码输入直接接引擎 74HC138 的低有效一热输出：IN→I7、W→I6、OUT→I5、B→I4、Q→I3、MC→I2；无区域时输出 111（REGION=7）。
- S11 输出缓冲 OE = **LOAD_EN**（低有效）。S10 U96/U95 的 OE = `NOT_LOAD_EN = ~LOAD_EN`，因此主机加载（LOAD_EN=1）与引擎推理（LOAD_EN=0）严格互斥。此极性在独立复核后从 `NOT_LOAD_EN` 修正为 `LOAD_EN`。
- REQ/WE 为纯组合：
  `REQ = C1_REQ | C2_REQ | FC_REQ`
  `WE = (C1_REQ&C1_WE) | (C2_REQ&C2_WE) | (FC_REQ&FC_WE)`
  没有仲裁/锁存，依赖 S01 串行化。

### 2.4 映射表（`model/busmap/bus_map.csv` 同内容）

| MASTER | FC_SEL | 区域 | MEM_SEL | 窗口 |
|---|---|---:|---:|---|
| C1 | 0 | IN/W/OUT/B/Q/MC | 0/8/1/12/16/20 | INPUT_SRAM / W_CONV1 / CONV1_OUT / B_CONV1 / Q_CONV1 / LUT0 |
| C2 | 0 | IN/W/OUT/B/Q/MC | 2/9/3/13/17/22 | POOL1_OUT / W_CONV2 / CONV2_OUT / B_CONV2 / Q_CONV2 / LUT1 |
| FC (FC1) | 0 | IN/W/OUT/B/Q/MC | 4/10/5/14/18/24 | POOL2_OUT / W_FC1 / FC1_OUT / B_FC1 / Q_FC1 / LUT2 |
| FC (FC2) | 1 | IN/W/OUT/B/Q/MC | 5/11/6/15/19/26 | FC1_OUT / W_FC2 / FC2_LOGITS / B_FC2 / Q_FC2 / LUT3 |

ROM 地址：`A[6:0]={FC_SEL,MASTER[1:0],REGION[2:0],0}`，即 `addr=(FC_SEL<<6)|(MASTER<<4)|(REGION<<1)`；未用地址写 `0x1F`。A0 及 A7..A15 接地，D5..D7 NC。

## 3. 引擎 / S02 / S01 / S04 接口修改

### 3.1 S07/S08/S09

- 删除 `CNN_Blocks:S02_MEM_IF` 实例（三处占位块）。`S02_MEM_IF` 符号定义仍在 `symbols/CNN_Blocks.kicad_sym`，但不再实例化。
- `C1/C2/FC_MEM_nCE_IN..MC` 保持全局标签，作为 S11 区域编码输入；74HC138 使能改为显式 `E0=MEM_nCE, E1=GND, E2=+5V`。复核：原接法 `E1=MEM_nCE, E2=+5V` 的极性本来就是正确的（E1 低有效），本次只是把共享 `MEM_nCE` 移到 E0 并变成显式接法，功能等价，不是修复反相 bug。
- `Cx_MEM_REQ/WE` 改为全局；`MEM_ACK/DONE/BUSY`、`MEM_nCE/nOE/nWE` 改为全局。FSM ROM 的 A7 接全局 `MEM_ACK`。
- 地址 74HCT541（U7147/48、U8149/50、U9136/37）的 `G1/G2 = Cx_BUSY_N`；`Cx_BUSY` 由 flags 574 直接全局化，反相器输出 `Cx_BUSY_N` 也全局化。`promote_engine_status.py` 复核：`C1_BUSY/C2_BUSY` 已是 global，输出“already global”；只有 `C1_DONE_I/C2_DONE_I` 被提升为 `C1_DONE/C2_DONE`，不会重复提升 BUSY。
- 每引擎增加 1×74HCT541 握手监测（输入 `MEM_nCE/nOE/nWE/ACK/DONE/BUSY`，输出 6 个页内 `Cx_MEM_STAT_*`，各接 1 个 TP）。这样 `MEM_DONE/MEM_BUSY` 有真实的引擎输入消费者，且输出不会悬空。状态缓冲放在 x=1010 的空白区，避免与引擎加法器/累加器重叠（早期放在 590,310 时与 `C_SUM*` 网络发生物理重叠，已修正）。

### 3.2 S02

- 删除 U10（74HC245）。S04 U36 是唯一的 `MEM_D <-> DATA` 缓冲；S02 不再重复数据方向控制。
- `REQ/WE` 输入仍由 U9 74HC74 同步，现在驱动源为 S11 U12010。
- `MEM_ACK/DONE/BUSY` 仍由 U5 74HCT541 驱动并保持全局。
- 去耦电容 12→11；网表中不再有 `MEM_DATA[7:0]`。

### 3.3 S01

- 微码 word bit13=POOL_SEL，bit14=FC_SEL；状态 9/10（P2_START/P2_WAIT）POOL_SEL=1，状态 13/14（FC2_START/FC2_WAIT）FC_SEL=1，其余 0。状态序列未改。
- U5（74HCT574）Q5/Q6 原为 NC，现接 `POOL_SEL/FC_SEL` 全局。网表驱动：`U1005.14 -> POOL_SEL`，`U1005.13 -> FC_SEL`。
- 选择 spare 微码位而不是 74HC238+门电路，因为 S01 本身有 3 个 spare 数据位（13/14/15）和 U5 的 3 个 spare 输出。

### 3.4 S04

- 增加 6×74HCT541（U4044..U4049），输入 `C1/C2/FC_ADDR[15:0]`，输出共享 `ADDR[15:0]`，OE=`Cx_BUSY_N`。U40/U41（`ADDR -> MADDR`）仍是 MADDR 的唯一驱动，因此 S02/S04 harness 的“MADDR 只由主机加载缓冲驱动”检查保持 PASS。
- 这是“两级地址缓冲”：引擎侧 541 先把内部 MX2 送到 `Cx_ADDR`，S04 侧 541 再把活动引擎的 `Cx_ADDR` 送到 `ADDR`。多用了 6 片，但保留了 `C1/C2/FC_ADDR` 网络名并让它们真正有 S04 节点，满足事务 harness 的地址路径检查；同时避免把三个引擎输出直接短接成单一 ADDR 网（多个全局标签会被 KiCad 合并成一个网名，无法表达三条独立总线）。
- 去耦 42→48。

## 4. 网表前后差异

| 指标 | 修改前（主工程 `output/top.net`） | 修改后（副本 `output/top.net`） |
|---|---:|---:|
| 网络数 | 2773 | 2815 |
| 元件数 | 863 | 917 |
| 单节点模块网（audit） | 90 | **4** |
| 未展开总线（audit） | 27 | 21 |
| `done_74hct541_outputs` | 1 | 1 |
| `done_multidriver` | false | false |

修改后仅剩 4 个单节点模块网，全部是总线修复范围外：

- `/S09_FC/FC_MODE_SPARE`（Requant 模式 spare）
- `ARGMAX_BUSY`
- `ARGMAX_RESULT_VALID`
- `POOL_BUSY`

未展开总线从 27 降到 21：三个引擎的 `Cx_WAIT_READ/WRITE[3:0]` 随 `S02_MEM_IF` 一起消失；剩余 21 个是每个引擎的 7 条 `B_DATA/M/N_MACS/SHIFT/ZP_*` 宏总线（属 S12/Requant 范围）。

关键网络节点（修改后）：

| 网络 | 节点 |
|---|---|
| `REQ` | `U12010.6`（S11 74HC32 输出）+ `U2009.2`（S02 同步器）+ TP2002 |
| `WE` | `U12010.11` + `U2009.12` + TP2003 |
| `MEM_ACK` | `U2005.15`（S02 输出）+ 9 个引擎输入（S07/S08/S09 ROM A7 + 状态 541） |
| `MEM_DONE` | `U2005.14` + U7149.6 / U8151.6 / U9138.6 |
| `MEM_BUSY` | `U2005.13` + U7149.7 / U8151.7 / U9138.7 |
| `MEM_SEL0..4` | `U10096.18..14`（S10，OE=NOT_LOAD_EN）+ `U12009.18..14`（S11，OE=LOAD_EN）+ `U4043`（S04） |
| `ADDR16..23` | `U10095`（S10）+ `U12008`（S11 tag）+ `U4042`（S04） |
| `C1_ADDR0` | `U7147.18`（引擎 541）+ `U4044.2`（S04 541） |
| `ADDR0` | `U10093.18`（S10）+ `U4044.18`（S04 C1 缓冲）+ `U4046.18`（S04 C2）+ `U4048.18`（S04 FC）+ `U4040.2`（S04 地址输入缓冲） |
| `C1_BUSY_N` | `U7146.2`（引擎反相器）+ 引擎/S04/S11 共 11 个负载 |

## 5. 验证结果

### 5.1 顶层网表与审计

```text
kicad-cli sch export netlist --format kicadsexpr -o output/top.net CNN_74xx_System.kicad_sch
python tools/audit_top_connectivity.py output/top.net
```

结果：`single_node_module_nets=4`，`unexpanded_bus_nets=21`，`done_541_output_count=1`，`done_multidriver=false`。证据：`top.audit.json`。

### 5.2 仿真

`python sim/run_all.py` → **9/9 PASS**（日志 `sim_run_all.log`）。

### 5.3 Muse harness

Harness A（`harness_s01_handshake.py output/top.net model/microcode`）：59 PASS / 2 FAIL，与修改前日志逐条相同。2 个失败是既有模型期望差异：

1. `IDLE+START -> G_C1_START`：微码在 state 2（IDLE）的当前字只给出 next=3，stage/tclr 在 state 3 的字里；harness 期望同一字带 stage=1/tclr=1。
2. `AM_WAIT done -> FINISH`：模型在 FINISH（17）的字里就给出 next=18，harness 调用后检查 state==17，得到 18。

这两项不是本次总线改动引入，也没有通过改状态序列去“修 harness”；保留原微码语义。

Harness B（`harness_s02_s04_transaction.py output/top.net`）：29 PASS / 6 FAIL（基线 26 PASS / 9 FAIL）。新增通过：REQ/WE 有驱动、MEM_ACK/DONE/BUSY 有引擎消费者、MADDR 单驱动、C1/C2/FC_ADDR 各 16 网全部到达 S04。剩余 6 个失败：

- 5 个 `MEM_SEL0..4: drivers=[U10096(S10), U12009(S11)] ... (host only)`：该检查写于修复前，要求 MEM_SEL 只能由主机驱动；本次修复的设计目标正是推理时由 S11 驱动，且两者 OE（NOT_LOAD_EN vs LOAD_EN）互斥。这是**过期检查**，不是电路错误。
- 1 个 `S02 74HC138 outputs with no load`（CAPTURE_N/DONE_ST_N/HOLD_N/RELEASE_N/WAIT_N）：基线已存在，属 S02 未用译码输出，与总线修复无关。

Harness C（`harness_datapath_layout.py`）：**PASS，0 failures**（日志 `harness_layout.log`）。

### 5.4 顶层 ERC

```text
kicad-cli sch erc --severity-all -o output/top-erc-after-bus.rpt CNN_74xx_System.kicad_sch
```

| 指标 | 修改前 | 修改后 |
|---|---:|---:|
| violations | 937 | 869 |
| error | 42 | **40** |
| warning | 895 | 829 |

40 个 error 全部是 S05/S06 的 `pin_not_driven`（S05 8 个、S06 32 个，属 Pool/Argmax 输入总线缺口）；S11、S07/S08/S09、S02、S04、S01 无 error。error 类型只有 `pin_not_driven`，无新增类型；减少的 2 个 error 是 S05 的 `POOL_SEL`（U5005.P2）和 S09 的 `FC_SEL`（U9005.S）原先无驱动，S01 补上两个选择信号后消失。warning 类型仍是原有类别，无新增 `pin_to_pin`/`multiple_net_names`（状态缓冲移到空白区后这两个临时 warning 已消失）。

## 6. 剩余风险

1. **MEM_SEL 到达时间 vs S02 wait state**：引擎区域 138 由 `MEM_nCE` 选通，MEM_SEL 还要经过 74HC148→74HC157→27C512→74HCT541，典型 ~100–150 ns（27C512 tAA 70–120 ns）。S02 默认 READ wait=3、WRITE wait=2（@8 MHz：375/250 ns）。写事务的 nCS 有效窗口可能被压缩到 ~100 ns，建议把 WRITE wait 改为 3 或对 6264/28C256 的 tWP 做时序复核；这是本方案最需要实测的一项。
2. **Q/MC 区域仍不可达**：三个引擎的 74HC138 只有 ADD_SEL0/1，A2 接地，只能选 IN/W/OUT/B；S11 已按 6 区域预留 Q/MC，但引擎 FSM 需要第 3 位 ADD_SEL2 后才能访问 Q_CONV*/Q_FC*/LUT*。当前 bias 通过 B 可达，qparam/LUT 不可达。
3. **LOAD_EN 与引擎 BUSY 无硬件互锁**：逻辑上主机加载与推理互斥，但若主机在引擎 BUSY 时置 LOAD_EN=1，S10 与 S11/S04 会同时驱动 ADDR/MEM_SEL。建议在 S10 或 S01 增加 `LOAD_EN & BUSY` 保护。
4. **两级地址缓冲延迟**：引擎 541 + S04 541 约增加 10–20 ns；相对 125 ns 时钟可接受，但地址建立时间需计入 S04 的 wait。
5. **空闲时 ADDR[15:0] 浮空**：LOAD_EN=0 且无引擎 BUSY 时，S10 与 S04 缓冲均关闭，ADDR 浮空；S04 U40/U41 的输入浮空。基线已有此问题，建议加 10k 下拉（未在本任务内改动）。
6. **74HC148 符号替代**：见 2.1；实际物料必须 74HC148 或电平兼容的 CMOS 148，不能装 74LS148。
7. **MAP ROM 内容不在原理图内**：27C512 需要按 `model/busmap/bus_map.bin` 烧录；BOM/生产流程要包含这一步。
8. **状态监测 541 + TP**：每引擎增加 1 片 541 和 6 个 TP，增加了 BOM/面积；若不需要调试观测，可删掉 541 和 TP，仅保留 ROM A7 对 MEM_ACK 的消费，但 MEM_DONE/MEM_BUSY 将失去引擎消费者。

## 7. 未完成 / 超出范围

- M-07 的状态回送：`POOL_BUSY`、`ARGMAX_BUSY`、`ARGMAX_RESULT_VALID` 仍是单节点，需要 S05/S06 -> S01 的状态路径。
- S12：`SCORE_DATA[31:0]` 拼装、S05/S06 的 `IN_*/OUT_*/SCORE_*` 存储器接口。
- Requant 门级展开（M-05/M-09）、LUT 物理 lane 映射（M-08）、等待/超时重算（M-10）、BOM 封装/去耦补齐（M-11）。
- S11 的 `MODE_SPARE` 等引擎内 spare 未处理。

## 8. 复现命令（在 `_repair_bus/work` 根目录）

```bash
python tools/gen_bus_map.py
python tools/build_bus.py
python tools/build_supervisor.py
python tools/gen_supervisor_microcode.py
python tools/build_timing.py
python tools/build_conv1.py
python tools/build_conv2.py
python tools/build_fc.py
python tools/build_memories.py
python tools/strip_pwr_flags.py
python tools/renumber_refs.py
python tools/promote_engine_status.py
python tools/build_top.py
"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist \
  --format kicadsexpr -o output/top.net CNN_74xx_System.kicad_sch
python tools/audit_top_connectivity.py output/top.net
python sim/run_all.py
python output/model_reviews/muse-slot-session-model/harness_s01_handshake.py output/top.net model/microcode
python output/model_reviews/muse-slot-session-model/harness_s02_s04_transaction.py output/top.net
python output/model_reviews/muse-slot-session-model/harness_datapath_layout.py
"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch erc --severity-all \
  -o output/top-erc-after-bus.rpt CNN_74xx_System.kicad_sch
```

## 9. patch

`bus.patch`（本目录）相对 `_repair_bus/work` 根目录，包含 26 个文本文件：工具、8 张重生成原理图（含 S11）、根图、supervisor 微码 `.hex/.csv`、bus map `.hex/.csv`、连接矩阵。未包含 `.bin` 二进制镜像；按第 8 节先运行 `gen_bus_map.py` / `gen_supervisor_microcode.py` 重新生成。已在主工程文件的临时副本上执行 `git apply --check`，可干净应用。
