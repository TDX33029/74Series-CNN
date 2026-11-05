# S11 总线适配层修复方案（M-02/M-03/M-06/M-07）

日期：2026-11-05  
状态：设计稿，待隔离副本实现与验证  
目标：把 S07/S08/S09 的引擎地址、区域片选、S02 请求/应答接到共享 S04 存储阵列，消除顶层 42 个未驱动输入中的总线部分。

## 1. 为什么需要 S11

当前三张引擎图各自有一个未展开的 `S02_MEM_IF` 宏块，输出 `Cx_MEM_nCE/nOE/nWE/ACK/DONE/BUSY`，但：

- `Cx_MEM_REQ/WE` 没有接到 S02 的全局 `REQ/WE`；
- S02 的 `MEM_ACK/DONE/BUSY` 只到测试点，没有引擎消费者；
- `Cx_ADDR[15:0]` 只到引擎页内，未接 S04 的 `ADDR`；
- `Cx_MEM_nCE_*` 是页内一热区域选择，S04 需要 5 位 `MEM_SEL`；
- S04 的地址标签比较器要求 `ADDR[23:16] == {000, MEM_SEL}`，引擎没有驱动高 8 位。

S01 已经串行化阶段（同一时刻只有一个引擎运行），因此不需要复杂仲裁器；只需要一个“当前 master 选择 + 地址/片选映射”的组合层。

## 2. 总体结构

```text
S10 host ADDR[23:0]/MEM_SEL[4:0] ----(LOAD_EN=1)----+
                                                     |
S07 C1_ADDR[15:0] --74HCT541(OE=C1_BUSY_N)--+        |
S08 C2_ADDR[15:0] --74HCT541(OE=C2_BUSY_N)--+-- ADDR[15:0] shared
S09 FC_ADDR[15:0] --74HCT541(OE=FC_BUSY_N)--+        |
                                                     |
S11: MASTER encoder (74HC148)                        |
     REGION encoder per engine (74HC148 x3)          |
     map ROM 27C512 -> MEM_SEL[4:0]                  |
     tag buffer 74HCT541 -> ADDR[23:16]={000,MEM_SEL}|
     REQ/WE OR gates -> S02 REQ/WE                   |
     MEM_ACK/DONE/BUSY global labels -> engines      |
                                                     |
S02 MEM_nCE/nOE/nWE --------------------------------+--> S04
S04 DATA[7:0] <---------------------------------------> engines (245)
```

关键前提：`LOAD_EN=1` 时主机独占；`LOAD_EN=0` 时 S01 只启动一个引擎。S10 的地址/数据/控制缓冲已经用 `NOT_LOAD_EN` 关闭，因此共享总线不会与主机冲突。

## 3. 引擎侧改动

### 3.1 删除未展开的 S02_MEM_IF 宏块

每个引擎的 `S02_MEM_IF` 块只是占位符，内部没有逻辑。改为被动接口：

- `Cx_MEM_nCE` ← 全局 `MEM_nCE`（S02 输出）
- `Cx_MEM_nOE` ← 全局 `MEM_nOE`
- `Cx_MEM_nWE` ← 全局 `MEM_nWE`
- `Cx_MEM_ACK/DONE/BUSY` ← 全局 `MEM_ACK/DONE/BUSY`
- `Cx_MEM_REQ/WE` → 全局 `Cx_MEM_REQ/WE`（送 S11）
- `Cx_WAIT_READ/WRITE[3:0]`：不再需要；等待值由 S02 内部 U2007 固定，或改为 S11 的可配置寄存器。

这样每个引擎不再有独立的时序控制器，S02 是唯一时序源，符合 brief 的“shared 12-IC controller”。

### 3.1.1 区域译码器使能接法（等价重构）

三个引擎原来的 74HC138 接法是 `~E0=GND, ~E1=MEM_nCE, E2=+5V`。74HC138 的 `~E0/~E1` 都是低有效，所以原接法本来就是正确的。S11 补丁把 `MEM_nCE` 移到 `~E0`、`~E1=GND`，只是让共享时序信号的接法更直观，功能等价，不是修复极性 bug。三种引擎（S07/S08/S09）同步改法即可。

### 3.2 地址缓冲使能

引擎现有的 `e.buf541` 把 OE 接地，三个引擎会同时驱动 `ADDR[15:0]`。改为：

- `C1_ADDR` 缓冲 OE = `C1_BUSY_N`
- `C2_ADDR` 缓冲 OE = `C2_BUSY_N`
- `FC_ADDR` 缓冲 OE = `FC_BUSY_N`

`Cx_BUSY` 在引擎运行期间为高，反相后作为 74HCT541 的低有效 OE。可用每个引擎现有的 74HC04 备用门，或新增 1 片 74HC04（3 个门足够）。

### 3.3 区域选择编码

每个引擎的 74HC138 输出 `Cx_MEM_nCE_IN/W/OUT/B/Q/MC`（低有效一热）。用 74HC148 8-to-3 优先级编码器把 6 个区域编码为 `REGION[2:0]`：

| 区域 | REGION |
|---|---|
| IN | 0 |
| W | 1 |
| OUT | 2 |
| B | 3 |
| Q | 4 |
| MC | 5 |
| 无 | 7（GS=1） |

当前引擎的 74HC138 只用 `ADD_SEL0/1 + GND`，所以 Q/MC 实际不可达；S11 先按 6 区域预留，等引擎 FSM 增加第 3 位 `ADD_SEL2` 后再使用。

## 4. S11 内部逻辑

### 4.1 Master 编码

输入 `C1_BUSY/C2_BUSY/FC_BUSY`（高有效），用 3 个反相器 + 1 片 74HC148 得到 `MASTER[1:0]`：

| MASTER | 引擎 |
|---|---|
| 0 | 无/主机 |
| 1 | C1 |
| 2 | C2 |
| 3 | FC |

### 4.2 区域映射 ROM

一片 27C512，地址 `A[6:0] = {FC_SEL, MASTER[1:0], REGION[2:0], 1'b0}`，数据 `D[4:0] = MEM_SEL`。映射表：

| MASTER | 区域 | MEM_SEL | 窗口 |
|---|---|---|---|
| C1 | IN | 0 | INPUT_SRAM |
| C1 | W | 8 | W_CONV1 |
| C1 | OUT | 1 | CONV1_OUT |
| C1 | B | 12 | B_CONV1 |
| C1 | Q | 16 | Q_CONV1 |
| C1 | MC | 20 | LUT0 pair |
| C2 | IN | 2 | POOL1_OUT |
| C2 | W | 9 | W_CONV2 |
| C2 | OUT | 3 | CONV2_OUT |
| C2 | B | 13 | B_CONV2 |
| C2 | Q | 17 | Q_CONV2 |
| C2 | MC | 22 | LUT1 pair |
| FC (FC_SEL=0) | IN | 4 | POOL2_OUT |
| FC (FC_SEL=0) | W | 10 | W_FC1 |
| FC (FC_SEL=0) | OUT | 5 | FC1_OUT |
| FC (FC_SEL=0) | B | 14 | B_FC1 |
| FC (FC_SEL=0) | Q | 18 | Q_FC1 |
| FC (FC_SEL=0) | MC | 24 | LUT2 pair |
| FC (FC_SEL=1) | IN | 5 | FC1_OUT |
| FC (FC_SEL=1) | W | 11 | W_FC2 |
| FC (FC_SEL=1) | OUT | 6 | FC2_LOGITS |
| FC (FC_SEL=1) | B | 15 | B_FC2 |
| FC (FC_SEL=1) | Q | 19 | Q_FC2 |
| FC (FC_SEL=1) | MC | 26 | LUT3 pair |

未用地址写 `0x1F`（无设备）。ROM 内容由 `tools/gen_bus_map.py` 生成，便于审查。

### 4.3 地址标签

S04 的 U32 要求 `ADDR[23:16] == {000, MEM_SEL[4:0]}`。S11 用一片 74HCT541 驱动 `ADDR[23:16]`：

```text
ADDR23..16 = {3'b000, MEM_SEL[4:0]}
```

OE = `NOT_LOAD_EN`（主机加载时关闭）。这样 S04 的标签比较器在引擎访问时通过，不需要修改 S04 内部。

### 4.4 REQ/WE 合并

```text
REQ = C1_MEM_REQ | C2_MEM_REQ | FC_MEM_REQ
WE  = (C1_MEM_REQ & C1_MEM_WE)
    | (C2_MEM_REQ & C2_MEM_WE)
    | (FC_MEM_REQ & FC_MEM_WE)
```

用 1 片 74HC32（4 个 OR）+ 1 片 74HC08（3 个 AND）实现。因为 S01 串行化，不需要锁存/仲裁。

### 4.5 握手分发

S02 的 `MEM_ACK/MEM_DONE/MEM_BUSY` 直接作为全局标签，接到三个引擎的 `Cx_MEM_ACK/DONE/BUSY` 输入。三个负载很轻，不需要缓冲。注意：非活动引擎也会看到握手，但它们的 FSM 不在等待态，不会误动作；S01 只等待当前阶段的 `*_DONE`。

### 4.6 主机/引擎 MEM_SEL 选择

S10 U96 在 `LOAD_EN=1` 时驱动 `MEM_SEL[4:0]`；S11 的 map ROM 输出经 74HCT541（OE=`NOT_LOAD_EN`）驱动同一总线。两者互斥，无需 mux。

## 5. S01 需要补的两个选择信号

- `POOL_SEL`：S01 在 STAGE=4（P2）时为 1，STAGE=2（P1）时为 0。可用 S01 的 74HC238 输出 `STAGE2_N/STAGE4_N` + 74HC08/32 产生。
- `FC_SEL`：S01 在 STAGE=6（FC2）时为 1，STAGE=5（FC1）时为 0。同理。

这两个信号目前是 S05/S09 的未驱动输入，属于 M-07 的一部分。

## 6. 芯片估算

| 功能 | 器件 | 数量 |
|---|---|---:|
| Master 编码 | 74HC148 | 1 |
| Master 反相 | 74HC04（与现有备用门共享） | 0–1 |
| 区域编码 | 74HC148 | 3 |
| 映射 ROM | 27C512 | 1 |
| 标签缓冲 | 74HCT541 | 1 |
| MEM_SEL 缓冲 | 74HCT541 | 1 |
| REQ/WE 合并 | 74HC32 + 74HC08 | 2 |
| 去耦/上拉 | 100nF/10k | 若干 |
| **合计** | | **约 9–10 片** |

相比给三个引擎各展开一份 12 片 S02（36 片），这个方案更小，也符合“共享 S02”的架构。

## 7. 实施顺序（隔离副本）

1. 复制主工程到 `Cache/_repair_bus/work`。
2. 新建 `tools/build_bus.py`，生成 `S11_BusFabric.kicad_sch`；先只画 master/region 编码、map ROM、标签/MEM_SEL 缓冲、REQ/WE 合并。
3. 修改 `tools/build_conv1.py`/`build_conv2.py`/`build_fc.py`：
   - 删除 `S02_MEM_IF` 实例；
   - 把 `Cx_MEM_nCE/nOE/nWE/ACK/DONE/BUSY` 改成全局标签；
   - 把 `Cx_MEM_REQ/WE` 改成全局标签；
   - 地址缓冲 OE 改为 `Cx_BUSY_N`。
4. 修改 `tools/build_timing.py`：删除 U10（MEM_DATA 245），`REQ/WE` 由 S11 驱动；`MEM_ACK/DONE/BUSY` 保持全局。
5. 修改 `tools/build_top.py`：加入 S11 sheet、模块表、连接矩阵；S00 页增加 S11。
6. 修改 `tools/build_supervisor.py`：增加 `POOL_SEL`/`FC_SEL` 输出。
7. 重新生成所有受影响的 sheet，导出 netlist，运行：
   - `python tools/audit_top_connectivity.py output/top.net`：目标单节点 < 20，`MEM_ACK/DONE/BUSY` 有消费者；
   - `python sim/run_all.py`：9/9；
   - Muse S02/S04 harness：REQ/WE 有驱动、ACK/DONE/BUSY 有消费者、C1/C2/FC_ADDR 到达 S04；
   - 布局 harness：0 failures；
   - 顶层 ERC：42 个 error 中至少 40 个消失（Pool/Argmax 数据输入仍需 S12）。
8. 写 `output/model_reviews/repair_bus/REPAIR_REPORT.md`，记录前后网表差异、ERC、仿真、剩余风险。

## 8. 不在本方案内

- `SCORE_DATA[31:0]` 的 4 字节拼装（建议单独 S12：4×74HCT574 + 地址译码，约 6 片）。
- Requant V2 已完成：S13/S15/S17 固定移位小核心，共 50 片；不再展开通用门级核心。
- LUT 物理 lane 映射（M-08）。
- 10–100 Hz 的等待/超时重算（M-10）。
- BOM 封装/去耦补齐（M-11）。

## 9. 验收标准

- S02 的 `REQ/WE` 不再单节点，且只由 S11 驱动。
- `MEM_ACK/DONE/BUSY` 在顶层至少有一个引擎消费者。
- `C1/C2/FC_ADDR[15:0]` 在顶层到达 S04 的 `ADDR` 路径。
- `MEM_SEL[4:0]` 在引擎模式下由 S11 驱动，且与 `Cx_MEM_nCE_*` 的区域一致。
- 9/9 仿真、布局 harness 0 failures、顶层 ERC 无新增 error。
- 所有修改在隔离副本完成，主工程只在报告审核通过后合并。
