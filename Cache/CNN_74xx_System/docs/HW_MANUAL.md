# CNN 74 系列硬件说明手册（V2，简洁 Requant）

本手册解释 CNN 74 系列推理系统的时钟、复位、握手、监督状态机、存储器时序控制器，以及各计算模块的工作方式。配套文件：

- `docs/HW_ARCH_CONTRACT.md`：接口/状态/微码契约
- `docs/MODULE_SPECS.md`：各模块绘制与仿真规格
- `S01_Supervisor.kicad_sch`：监督 FSM 原理图
- `S02_Timing.kicad_sch`：存储器时序控制器
- `S13_Requant_C1.kicad_sch`：CONV1 简单 Requant（`ACC >> 8`）
- `S15_Requant_C2.kicad_sch`：CONV2 简单 Requant（`ACC >> 9`）
- `S05_Pool1/2.kicad_sch`：固定 POOL1/POOL2 变体
- `S09_FC1/2.kicad_sch`：固定 FC1/FC2 变体
- `S17_FC1/2.kicad_sch`：FC1 `ACC>>8` uint8 / FC2 原始 signed32 四字节
- `S11A_EngineMerge.kicad_sch`：FC1/FC2、POOL1/POOL2 二选一接回 S11
- `S12A_PoolLatch1/2.kicad_sch`、`S12B_ScoreLatch.kicad_sch`：拆分后的数据拼装
- `docs/BOARD_PARTITION.md`、`output/boards/BOARD_MANIFEST.csv`：12 板卡清单
- `S_LUT_Mult_1.kicad_sch`：8×8 LUT 乘法单元
- `sim/tb_supervisor.cir`、`sim/tb_timing.cir`、`sim/tb_lut.cir`：SPICE 功能仿真

---

## 1. 系统总览

系统只有一个推理入口 `START`，没有 MCU 参与调度。上电/复位后，外部把 28×28 图像写入 INPUT_SRAM，并把权重、偏置、qparam 准备好，置 `IMAGE_READY` 和 `MODEL_READY`。随后 `START` 启动一次推理：

```
CONV1 → POOL1 → CONV2 → POOL2 → FC1 → FC2 → ARGMAX → RESULT
```

每个阶段拥有独立的存储器、LUT 乘法 ROM、累加器和局部 FSM。顶层监督 FSM 只负责“启动—等待 done—启动下一阶段”，不产生像素地址或乘法控制。

### 1.1 全局信号

| 信号 | 方向 | 说明 |
|---|---|---|
| `CLK` | 输入 | 唯一系统时钟，8 MHz |
| `RESET_N` | 输入 | 低有效复位；外部异步断言，内部同步释放 |
| `START` | 输入 | 启动一次推理；建议脉冲或电平，FSM 在 IDLE 采样 |
| `IMAGE_READY` | 输入 | 输入图像已加载 |
| `MODEL_READY` | 输入 | 权重/偏置/qparam/LUT 已就绪 |
| `BUSY` | 输出 | 推理进行中 |
| `DONE` | 输出 | 推理完成，单周期脉冲 |
| `RESULT[3:0]` | 输出 | 类别 0–9 |
| `RESULT_VALID` | 输出 | 结果保持有效，直到下一次 START 或复位 |
| `ERROR` | 输出 | 未就绪启动、超时或协议错误 |
| `ERROR_CODE[3:0]` | 输出 | 错误编码：0001=未就绪，0010=超时 |

### 1.2 阶段握手

每个计算模块使用统一接口：

```
clk, rst, start, busy, done, error
```

- `start` 是单周期脉冲；模块只在 `IDLE` 接受。
- `busy` 在整个事务期间为 1，包括最后一次存储器写和保持周期。
- `done` 是单周期脉冲；必须在最后一次写操作完成之后产生。
- 顶层只在看到某模块 `done` 后，才在下一个时钟沿进入下一阶段的 `START` 状态。
- 推理过程中忽略新的 `START`；完成后进入 `G_WAIT_START_LOW`，等 `START` 撤销后回 `G_IDLE`，防止长高电平重复启动。

### 1.3 12 板卡与背板连接器（2x20P）

系统由 12 张具体板卡组成，每张板只做固定功能，层与层之间不再复用同一引擎：

| 板卡 | 名称 | 图页 | 对外网络 | 排针 |
|---|---|---|---|---|
| B01 | SUPERVISOR | S01 | 37 | 2 |
| B02 | TIMING | S02 | 10 | 1 |
| B03 | MEMORY | S04 | 204 | 8 |
| B04 | CONV1 | S07 + S13 | 43 | 2 |
| B05 | POOL1 | S05_Pool1 + S12A_PoolLatch1 | 53 | 3 |
| B06 | CONV2 | S08 + S15 | 43 | 2 |
| B07 | POOL2 | S05_Pool2 + S12A_PoolLatch2 | 53 | 3 |
| B08 | FC1 | S09_FC1 + S17_FC1 | 43 | 2 |
| B09 | FC2 | S09_FC2 + S17_FC2 | 44 | 2 |
| B10 | ARGMAX | S06 + S12B_ScoreLatch | 26 | 1 |
| B11 | BUSFAB | S11 + S11A_EngineMerge | 72 | 3 |
| B12 | HOSTIO | S10 | 59 | 3 |

- 共 **32 片 2x20P**、1280 脚、687 个信号端点；插到底板实现板卡互联。
- 每片排针的电源脚固定：
  `1–4 = +5V`、`5–8 = +3.3V`（预留）、`9–14 = GND`、`15–40 = 信号`。
- 每片只有 26 个信号脚；超过 26 个对外网络的板放多片。
- 信号按功能连续分配；同一网络在不同板上的引脚号可能不同。
  权威引脚表：`output/backplane/backplane_pinout.csv`；逐网视图：
  `output/boards/backplane_nets.csv`；板卡清单：
  `output/boards/BOARD_MANIFEST.csv`。
- 生成器：`tools/build_boards.py`（按网络共现自动生成外部网表）、
  `tools/backplane.py`、`tools/gen_backplane_csv.py`。
- 板内网络（各引擎 ACC/REQ 对、`IN_DATA1/2`、`SCORE_DATA`）不上底板。
- 底板设计者按 CSV 逐槽布线；当前不是“同一网络同一引脚”的总线式背板。

---

## 2. 监督状态机（S01）

### 2.1 状态编码

| 编码 | 状态 | 行为 |
|---:|---|---|
| 0 | `G_RESET` | 清状态/输出，转 `G_WAIT_READY` |
| 1 | `G_WAIT_READY` | 等 `IMAGE_READY & MODEL_READY`；若 START 在未就绪时出现，转 ERROR |
| 2 | `G_IDLE` | 等 START；ready 时接受，未 ready 时启动则 ERROR |
| 3 | `G_C1_START` | 发 CONV1 start，`BUSY=1` |
| 4 | `G_C1_WAIT` | 等 `C1_DONE`；超时→ERROR |
| 5/6 | `G_P1_START/WAIT` | POOL1 |
| 7/8 | `G_C2_START/WAIT` | CONV2 |
| 9/10 | `G_P2_START/WAIT` | POOL2 |
| 11/12 | `G_FC1_START/WAIT` | FC1 |
| 13/14 | `G_FC2_START/WAIT` | FC2 |
| 15/16 | `G_ARGMAX_START/WAIT` | ARGMAX |
| 17 | `G_FINISH` | 锁存 RESULT，`DONE` 一拍，`BUSY=0` |
| 18 | `G_WAIT_START_LOW` | 等 START 撤销 |
| 19 | `G_ERROR` | 锁存 ERROR，停止下游，保持到复位 |

### 2.2 状态转移（文字版）

```
RESET ──► WAIT_READY ──(ready)──► IDLE
                 │                  │
                 └─(start & !ready)─┴──► ERROR

IDLE ──(start & ready)──► C1_START ──► C1_WAIT ──(done)──► P1_START
  ▲                                                        │
  │                                                        ▼
  └──────────────── WAIT_START_LOW ◄── FINISH ◄── ... ◄── ARGMAX_WAIT
```

每个 `*_START` 只停留一拍，产生对应模块的单周期 `start`；下一拍进入 `*_WAIT`。每个 `*_WAIT` 在对应 `done` 到来后进入下一 `*_START`；若 24 位超时计数器到 `0xFFFFFF`，进入 `G_ERROR`。

### 2.3 微码地址

监督 FSM 用 2×27C512 组成 16 位微码。地址线：

```
A[4:0]  = state[4:0]
A5      = START_S            (两级同步)
A6      = IMAGE_READY_S      (两级同步)
A7      = MODEL_READY_S      (两级同步)
A8..A14 = C1/P1/C2/P2/FC1/FC2/ARGMAX done
A15     = TIMEOUT
```

### 2.4 微码数据

| 位 | 名称 | 含义 |
|---:|---|---|
| 4:0 | NEXT_STATE | 下一状态 |
| 5 | BUSY | 忙标志 |
| 6 | DONE | 完成脉冲（仅 FINISH） |
| 7 | RESULT_VALID_SET | 置位 RESULT_VALID DFF |
| 8 | ERROR | 错误标志 |
| 11:9 | STAGE_CODE | 1=C1, 2=P1, 3=C2, 4=P2, 5=FC1, 6=FC2, 7=ARGMAX |
| 12 | TIMEOUT_CLR | 清 24 位超时计数器 |
| 13 | POOL_SEL | POOL2 阶段选择（状态 9/10） |
| 14 | FC_SEL | FC2 阶段选择（状态 13/14） |
| 15 | SPARE | 预留 |

`STAGE_CODE` 经 74HC238 译码成 7 路 `*_START`。`TIMEOUT_CLR` 在每个 `*_START` 有效，使超时按阶段重新计时。`POOL_SEL`/`FC_SEL` 由 74HCT574（U5）的 Q5/Q6 直接输出，供 S05 Pool 和 S11 总线映射使用；它们不改变状态序列。

### 2.5 关键时序

```
CLK        _/‾\_/‾\_/‾\_/‾\_/‾\_/‾\_
state      IDLE  C1_START C1_WAIT ... 
C1_START   ____/‾‾\__________________   (one cycle)
BUSY       ____/‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\__
C1_DONE    ________________/‾‾\______   (from CONV1)
DONE       ________________________/‾\  (at FINISH)
RESULT_VALID ______________________/‾‾‾  (held)
```

要点：

1. `BUSY` 从接受 START 的下一拍开始，到 `G_FINISH` 清零；包含所有阶段和最后一次写完成等待。
2. `DONE` 只在 `G_FINISH` 出现一拍；此前必须已经看到 ARGMAX 的 `done`。
3. `RESULT_VALID` 由独立 74HC74 置位并保持；新的有效 START 或复位清除。
4. `G_WAIT_START_LOW` 防止 START 长高造成重复推理；只有 START 回到 0 才回 IDLE。
5. 未就绪启动：`G_IDLE` 检测到 `START & !ready` 时不进入任何计算阶段，直接 `G_ERROR`，`ERROR_CODE=0001`。
6. 超时：24 位计数器在 `BUSY` 期间计数；比较器到 `0xFFFFFF` 时 `TIMEOUT=1`，当前 WAIT 状态转 `G_ERROR`，`ERROR_CODE=0010`。8 MHz 下约 2.1 s，覆盖一次完整推理。

### 2.6 SPICE 验证结果

`sim/gen_supervisor_tb.py` 用 5 个 XSPICE `d_dff` 保存状态，用 B 源实现同一张状态表。采样时钟沿后 30 ns，得到：

```
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16
  → 17 → 18 → 2
```

`sequence_ok=True, busy_ok=True, done_ok=True, error_ok=True`，输出 `PASS: supervisor state sequence`。

随后发现 74HC688 的 `P=R` 是低有效输出，而微码 A15/A5 的 `TIMEOUT/IDLE` 语义是高有效。当前 S01 用 U16E/U16F 两个反相器把 `TIMEOUT_N/IDLE_N` 转成 `TIMEOUT_I/IDLE_MATCH`；`sim/gen_glue_tb.py` 专门验证了这两个极性、`RESULT_VALID` 的保持/清除以及时序片的 `WAIT_MATCH` 反相。该测试 11/11 检查通过，输出 `PASS: active-low glue and result-valid hold`。

`RESULT_VALID` 的 74HC74 采用 D=Q 反馈，而不是 D=+5V：置位后一直保持，只有“接受新的 START”或复位才清除。D=+5V 会在下一个时钟自动重新置位，导致推理期间一直为高，这是本轮仿真发现并修复的问题之一。

---

## 3. 存储器时序控制器（S02）

### 3.1 状态

| 编码 | 状态 | 说明 |
|---:|---|---|
| 0 | `T_IDLE` | 等 `REQ` |
| 1 | `T_SETUP` | 建立地址/数据，拉低 nCE；读拉低 nOE，写拉低 nWE |
| 2 | `T_WAIT` | 等待计数器达到 `WAIT_READ`/`WAIT_WRITE` |
| 3 | `T_CAPTURE` | 读：数据有效，发 ACK |
| 4 | `T_HOLD` | 读：撤 nOE；写：撤 nWE 并发 ACK |
| 5 | `T_RELEASE` | 撤 nCE |
| 6 | `T_DONE` | 发 DONE，下一拍回 IDLE |

### 3.2 读时序

```
CLK        _/‾\_/‾\_/‾\_/‾\_/‾\_/‾\_/‾\_
state      IDLE  SETUP WAIT  WAIT  CAPT  HOLD  REL   DONE  IDLE
nCE        ‾‾‾\_________________________________/‾‾‾‾‾‾‾‾‾‾‾
nOE        ‾‾‾\___________________________/‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
DATA       ======X=========== valid =========X============
ACK        ________________________________/‾‾\__________
DONE       ______________________________________________/‾\_
```

- `nCE/nOE` 在 `T_SETUP` 拉低，地址在整个 `T_WAIT` 保持稳定。
- `T_CAPTURE` 的时钟沿锁存数据；同时 `ACK` 告诉引擎“数据已可用”。
- `T_HOLD` 撤 `nOE`，满足输出保持/总线释放。
- `T_RELEASE` 撤 `nCE`；`T_DONE` 才发 `DONE`。

### 3.3 写时序

```
CLK        _/‾\_/‾\_/‾\_/‾\_/‾\_/‾\_
state      IDLE  SETUP WAIT  WAIT  WAIT  HOLD  REL   DONE
nCE        ‾‾‾\_________________________________/‾‾‾‾‾
nWE        ‾‾‾\_________________________/‾‾‾‾‾‾‾‾‾‾‾‾
DATA       ======X=========== valid =========X========
ACK        ________________________________/‾‾\________
DONE       __________________________________________/‾\_
```

- 写期间 `nOE` 始终保持高，避免读驱动器与写数据冲突。
- `nWE` 在 `T_HOLD` 撤销后才发 `ACK`；`DONE` 更晚，保证最后一次写和保持时间完成。
- 引擎必须在看到 `ACK/DONE` 后才释放 `REQ` 或改变地址/数据。

### 3.4 等待周期

```
WAIT_READ  = ceil((max(tAA,tCE,tOE) + margin) / Tclk)
WAIT_WRITE = ceil((tWP + tDH + margin) / Tclk)
```

示例（8 MHz，Tclk=125 ns）：6264 读/写 = 2/2；28C256 读 = 3；27C512 读 = 2。S02 当前把 `WAIT_READ/WRITE` 默认接为 3/2（覆盖最慢的 28C256 读和 6264 写），U7 的四个输入直接接 +5V/GND；如要按器件类型动态配置，可把这四个连接改为 S10 的 DIP 开关或配置锁存器。原独立的 `WAIT_READ[3:0]`/`WAIT_WRITE[3:0]` 全局网络在系统集成时被这组默认值取代。

### 3.5 总线规则

- 每片 SRAM/ROM 独立片选；地址/数据/控制总线由 S11 在“主机加载”和“推理引擎”之间切换。
- 同一片存储器任一时刻只有一个控制器：S10 缓冲 OE=`NOT_LOAD_EN`，S11/S04 引擎缓冲 OE=`LOAD_EN`，硬件上互斥（但尚无 `LOAD_EN & BUSY` 联锁）。
- 写期间 nOE 高；读期间 nWE 高；未访问时 nCE 高。
- 任何 `done` 都不得早于最后一次写脉冲和保持周期。

### 3.6 SPICE 验证结果

`sim/gen_timing_tb.py` 用 3 个 `d_dff` 保存时序状态、2 个 `d_dff` 保存等待计数器，验证：

- 读事务：`IDLE→SETUP→WAIT→CAPTURE→HOLD→RELEASE→DONE→IDLE`，ACK 在 CAPTURE。
- 写事务：`IDLE→SETUP→WAIT→HOLD→RELEASE→DONE→IDLE`，ACK 在 HOLD，nWE 已抬高。
- `nOE` 与 `nWE` 从未同时有效；`nCE` 在 IDLE/RELEASE/DONE 为高；DONE 只在 T_DONE。
- 输出 `PASS: timing controller read/write protocol`。

图纸复核时另外发现并修复了三处接线问题：

1. 74HC138（U4）的符号输出名为 `~{Y0}..~{Y7}`、使能名为 `~{E0}/~{E1}/E2`；原映射使用 `Y0..Y7/E3`，导致译码器输出全部 NC。现在按引脚号映射，Y0..Y6 分别驱动 `IDLE_N..DONE_ST_N`。
2. 74HC688（U8）的 `P=R` 低有效；`WAIT_MATCH_N` 经 U12B 反相为高有效的 `WAIT_MATCH` 后才进微码 A4。
3. 74HC245（U10）已删除：S02 不再重复做数据方向控制，S04 U36 是 `MEM_D <-> DATA` 的唯一缓冲；网表中不再有 `MEM_DATA[7:0]`。

`sim/gen_glue_tb.py` 覆盖 `WAIT_MATCH` 极性、`IDLE_MATCH` 极性、`TIMEOUT_I` 极性和 74HC245 使能门控，全部通过。

### 3.7 共享总线适配层（S11）

S11 把三个引擎的“区域请求”翻译成 S04 的 `MEM_SEL[4:0]`，并在主机加载与推理之间切换共享总线：

- 4×74HC148：1 片 master 编码（C1>C2>FC>ARGMAX>POOL），3 片区域编码（IN/W/OUT/B/Q/MC，接引擎 74HC138 的低有效一热输出）。
- 2×74HC157：区域 mux；第 1 级在 C1/C2 间选择，第 2 级在 conv/FC 间选择，选择端与 master 同优先级。
- 27C512 映射 ROM：地址 `{FC_SEL, MASTER[1:0], REGION[2:0], 0}`，输出 `MEM_SEL[4:0]`；镜像在 `model/busmap/bus_map.bin`。
- 2×74HCT541：`ADDR[23:16]={000,MEM_SEL}` 标签缓冲和 `MEM_SEL[4:0]` 缓冲，OE=`LOAD_EN`。
- 74HC32 + 74HC08：`REQ = C1_REQ|C2_REQ|FC_REQ`，`WE` 只取“请求且该引擎写”的项。
- S04 另有 8×74HCT541，把活动引擎的 `C1/C2/FC1/FC2_ADDR[15:0]` 汇入共享
  `ADDR[15:0]`，OE=`Cx_BUSY_N`；POOL1/POOL2 各有 5 片（地址低/高、写地址、
  写数据）和 1 片 74HC32，构成两组三方态缓冲。
- **S11A_EngineMerge（B11 板上）**：FC1/FC2、POOL1/POOL2 是独立板卡，但 S11
  只保留一个 FC 槽和一个 POOL 槽；S11A 用 5 片 74HC157，以 `FC2_BUSY` /
  `POOL2_BUSY` 为选择端，把两套 region/REQ/WE/BUSY 二选一接回 S11。
  用 mux 而不是 OR/AND：引擎 138 只由 `MEM_nCE` 限定，空闲引擎仍会输出
  区域码，直接合并会把别的引擎的访问映射到错误窗口。S11 本体未改。

`LOAD_EN=1` 时主机通过 S10 驱动地址/MEM_SEL；`LOAD_EN=0` 时由 S11 驱动。两者 OE 互补，但软件/硬件必须保证主机不在引擎 BUSY 时加载。S11 增加约 100–150 ns 的 MEM_SEL 延迟（27C512 tAA 为主），10–100 Hz 外部时钟下余量充足；8 MHz 内部时钟的写等待建议从 2 改为 3。

### 3.8 数据拼装层（S12A/S12B）

拆分后每块板只带自己需要的部分：

- **Pool（S12A_PoolLatch1/2）**：各 1 片 74HCT541，把共享 `DATA[7:0]`
  缓冲为板内 `IN_DATA1[7:0]` / `IN_DATA2[7:0]`，OE 固定使能。
- **Argmax（S12B_ScoreLatch）**：U1–U4 四片 74HCT574 按字节锁存 score，
  Q 输出组成 `SCORE_DATA[31:0]`（小端）；U5 74HC238 用 `SCORE_ADDR[1:0]`
  和 `MEM_ACK` 产生四个字节锁存时钟。
- S12A/S12B 消除了 40 个数据 `pin_not_driven`；V2 删除参数装载器后，
  顶层最终 **0 errors**。

**Argmax 四字节事务**：S06 的 U39 是 2 位字节计数器，U38 输出 `SCORE_ADDR={CLASS,BYTE}=class*4+byte`。每个字节执行 `SCORE_RD` → S02 REQ/ACK → S12 在 `MEM_ACK` 锁存 → S06 等 `MEM_DONE` 后字节 +1。S04 U50/U51 在 `ARGMAX_BUSY_N` 期间把地址零扩展到 `ADDR[15:0]`；S11 把 Argmax 作为 master 4，27C512 A7=`MASTER2`，映射全部 region 到 `MEM_SEL=6`（FC2_LOGITS），`REQ` 合并 `SCORE_RD`。

### 3.9 V2 简单 Requant（S13/S15/S17）

旧版通用门级核心和 S14/S16/S18 参数装载器已归档删除。当前只有三块小核心：

- **S13 CONV1**：13 片 DIP，`Q = clamp(ACC >> 8, 0, 255)`。
- **S15 CONV2**：13 片 DIP，`Q = clamp(ACC >> 9, 0, 255)`。
- **S17 FC1/FC2**：24 片 DIP；FC1 `Q = clamp(ACC >> 8, 0, 255)`，FC2 原始 signed32 四字节小端。

共同数据通路：

```text
QRAW[i] = ACC[S+i]（越界取 ACC[31] 符号扩展）
HIGH    = OR(ACC[S+8 .. 31])
SAT_POS = HIGH & ~ACC[31]
QVAL    = ACC[31] ? 0 : (SAT_POS ? 255 : QRAW)
Q       = QVAL 在 START 上升沿锁存
```

- 4×74HC157 做两级 8 位 2:1 钳位，1×74HCT574 输出，1×74HC74 产生 QSTB/DONE。
- S17 用 13×74HC157：FC1 钳位 4 片、FC2 字节 mux 6 片、输出 mux 2 片、QSTB/DONE 选择 1 片；1×74HC161 做 3 位字节计数，1×74HC74 做 RUN。
- Conv：START→QSTB 1 CLK，DONE 2 CLK。FC1：BC=0 时 QSTB/DONE。FC2：BC=0..3 时 QSTB，BC=3 时 DONE。
- `FC_REQ_QSTB` 直接驱动 S09 的 OUTHOLD 和字节计数器；FC2 地址为 `neuron*4+byte`。
- 没有 `BIAS/M/ZP_X/ZP_W/ZP_OUT/N_MACS`，没有 32×16 乘法器、64 位乘积、27C512 微程序，也没有 `PDATA/PSEL/PLOAD`。
- 模型契约：对称量化、**bias=0**、每层统一 2^S、直接截断不四舍五入。详细说明见 `docs/REQUANT_SIMPLE_V2.md`。

**规模**：S13 13 + S15 13 + S17_FC1 24 + S17_FC2 24 = **74 片 DIP**
（旧版 1368 片；方案 A 后 FC/S17 各复制一份）。

**验证**：`sim/gen_requant_simple_tb.py` 对每层 5000 组随机 ACC 做 golden clamp，检查 FC2 四字节小端、Conv/FC 握手、结构、跨页网表、BOM 和 ERC；`sim/run_all.py` 13/13。

## 4. 8×8 LUT 乘法单元

- 两片 27C512 共享地址 `{A[7:0],B[7:0]}`；低字节 ROM 输出 `(A*B)[7:0]`，高字节 ROM 输出 `(A*B)[15:8]`。
- 操作数由 74HCT574 锁存；乘积由两片 74HCT574 锁存。
- ROM 文件由 `tools/gen_lut.py` 生成；对全部 65536 个地址逐项校验，`errors=0`。
- SPICE 抽样验证 8 组操作数（含 255×255、0×255、128×127），全部匹配。
- 四个计算引擎各有一对独立 ROM；物理芯片独立，不共享地址总线。

---

## 5. 计算引擎接口与循环

### 5.1 CONV1

- 输入 28×28×1，权重 8×1×5×5，输出 24×24×8。
- 循环：`oc → oy → ox → ic → ky → kx`；每个输出点 25 个乘积。
- 地址：`IN = ic*H*W + (oy+ky)*W + (ox+kx)`；`W = (((oc*Cin+ic)*K+ky)*K+kx)`；`OUT = oc*Hout*Wout + oy*Wout + ox`。
- 每个输出点重新清 `RAW_SUM/SUM_X/SUM_W`，单独装载该 oc 的 bias/qparam。
- 输出写完才推进下一个输出点；阶段 done 晚于最后一次写。

### 5.2 CONV2

- 输入 12×12×8，权重 16×8×3×3，输出 10×10×16。
- 每个输出点 72 个乘积；其余与 CONV1 相同。

### 5.3 POOL1/POOL2

- 2×2、stride 2、VALID、CHW；每个通道独立，不跨通道比较。
- 单端口 SRAM 顺序读 4 个值，unsigned max，写回。
- POOL1：24×24×8 → 12×12×8；POOL2：10×10×16 → 5×5×16。
- S05 实现：4 个 74HC161 循环计数器、74HC283×8 地址增量、74HC85×2 比较、74HCT273 保存 MAX/WB、74HCT574 输出寄存器、74HC161×3 输出地址计数器、one-hot 局部 FSM。
- SPICE 覆盖 10 个连续窗口（最大值位置轮换）、相等值、0/255 边界和 40 次读地址检查，输出 `PASS: POOL 2x2 max, 4-value order, 0/255 and equal-value coverage`。

### 5.4 FC1/FC2

- FC1：400→32，uint8 输出 + ReLU；每个 neuron 400 MAC；S17 在 BC=0 发一次 QSTB。
- FC2：32→10，原始 signed32 输出，不做 uint8 饱和；10 类统一到同一分数尺度，little-endian 写 4 字节；S17 在 BC=0..3 各发一次 QSTB，BC=3 同时 DONE。
- S09 的 `FC_REQ_QSTB` 直接作为 2 位字节计数器的时钟使能；因此 QSTB 每来一次，地址 `neuron*4+byte` 就前进一字节，第 4 字节后计数器回到 0。
- V2 没有 bias/qparam 装载；FC2 写完 4 字节后才处理下一类。S09 本地 FSM 的 4 个写请求 (`MEM_REQ/WE`) 必须与这 4 个 QSTB 对齐；本工程尚未导出 S09 FSM 微码镜像，需按 3.9/S09 图纸说明实现。

### 5.5 ARGMAX

- 先读 class0 初始化 max，再读 class1..9。
- 有符号 32 位比较；`score > max` 才更新，并列取小编号。
- 扫描完 10 类锁存 4 位结果并发出 done。
- S06 实现：class 计数器、2 位字节计数器、32 位 SCORE/MAX 寄存器、8×74HC85 级联（最高位取反做 signed）、32 位 MAX 更新 mux、多状态 one-hot FSM。每类先按 `class*4+byte` 读 4 个字节，S12 在 `MEM_ACK` 锁存后组成 32 位 score。
- SPICE 覆盖 5 组向量（最大值在首/尾、并列、-2^31/2^31-1），输出 `PASS: ARGMAX signed32, ties, first/last and -2^31/2^31-1 boundaries`。

### 5.6 模块接口与顶层适配

各子图按“可独立评审的功能块”绘制，接口使用模块内总线名；S04 使用全局 `ADDR[23:0]`/`DATA[7:0]`/`MEM_SEL[4:0]`。S11 负责把引擎的 `Cx_ADDR`/`Cx_MEM_*` 映射到共享总线（见 3.7）。S05 Pool 和 S06 Argmax 的 `IN_DATA1/2[7:0]`/`SCORE_DATA[31:0]` 由 S12A/S12B 接到 S04 数据总线；S13/S15/S17_FC1/S17_FC2 分别接 S07/S08/S09_FC1/S09_FC2 的板内 Requant 接口。当前顶层 ERC 为 0 error / 1407 warnings；`POOL_BUSY` 已接入 S11，剩余单节点状态网为 `ARGMAX_RESULT_VALID`（测试点）和 `OUT_WE`（预留），0 个未展开总线。

| 模块 | 地址/数据接口 | 控制/握手 | 目标存储窗口 |
|---|---|---|---|
| S05 Pool | `IN_ADDR[12:0]`, `IN_DATA[7:0]`, `OUT_ADDR[11:0]`, `OUT_DATA[7:0]` | `P1_START`, `P2_START`, `POOL_BUSY`, `P1_DONE`, `P2_DONE`, `OUT_WE`, `POOL_SEL` | POOL1_OUT / POOL2_OUT |
| S06 Argmax | `SCORE_ADDR[5:0]`, `SCORE_DATA[31:0]` | `ARGMAX_START`, `SCORE_RD`, `RESULT_IN[3:0]`, `ARGMAX_RESULT_VALID`, `ARGMAX_BUSY`, `ARGMAX_DONE` | FC2_LOGITS |
| S07 Conv1 | `C1_ADDR[15:0]`, `DATA[7:0]`, `C1_ACC[31:0]` | `C1_START`, `C1_DONE`, `C1_BUSY`, `C1_MEM_*` | INPUT / CONV1_OUT / W_CONV1 / B_CONV1 / Q_CONV1 / LUT0 |
| S08 Conv2 | `C2_ADDR[15:0]`, `DATA[7:0]` | `C2_START`, `C2_DONE`, `C2_BUSY`, `C2_MEM_*` | CONV1_OUT / CONV2_OUT / W_CONV2 / … |
| S09 FC | `FC_ADDR[15:0]`, `FC_OUT_D[7:0]`, `FC_OUT_ADDR[?]` | `FC1_START`, `FC2_START`, `FC1_DONE`, `FC2_DONE`, `FC_SEL` | POOL2_OUT / FC1_OUT / FC2_LOGITS |
| S04 Memories | 全局 `ADDR[23:0]`, `DATA[7:0]`；引擎侧 `C1/C2/FC_ADDR[15:0]` | `MEM_SEL[4:0]`, `MEM_nCE/nOE/nWE` | 27 片独立窗口 |
| S11 BusFabric | `C1/C2/FC_MEM_nCE_*`、`Cx_MEM_REQ/WE` | `FC_SEL`、`LOAD_EN` → `REQ/WE`、`MEM_SEL[4:0]`、`ADDR[23:16]` | 映射 ROM 24 项 |

---

## 6. 数值契约

```
real_x = scale_x * (q_x - zp_x)
real_w = scale_w * (q_w - zp_w)
ACC = SUM((q_x-zp_x)*(q_w-zp_w)) + bias_int32
    = RAW_SUM - zp_w*SUM_X - zp_x*SUM_W + N*zp_x*zp_w + bias_int32
q_out = SATURATE_UINT8(ROUND(ACC * M / 2^S) + zp_out)
```

- `RAW_SUM/SUM_X/SUM_W` 均为 32 位；中间不截断到 8/16 位。
- requant 用串行 32×16 乘法器和 64 位中间积；按模型规定的舍入和算术移位执行。
- ReLU 下限是 `zp_out`（实数 0），不是固定数字 0。
- FC2 不做 uint8 饱和；10 类必须统一尺度后才能 Argmax。
- 模型审计必须给出 input scale/zp、每层 input zp、每输出通道 weight zp、output zp、bias 格式、M/S、舍入/饱和规则。

---

## 7. 存储器与地址

| 存储 | 容量 | 建议器件 | 地址 |
|---|---:|---|---|
| INPUT_SRAM | 784 B | 6264 | `y*28+x` |
| CONV1_OUT | 4608 B | 6264 | `oc*576+y*24+x` |
| POOL1_OUT | 1152 B | 6264 | `c*144+y*12+x` |
| CONV2_OUT | 1600 B | 6264 | `oc*100+y*10+x` |
| POOL2_OUT | 400 B | 6264 | `c*25+y*5+x` |
| FC1_OUT | 32 B | 6264 | `n` |
| FC2_LOGITS | 40 B | 6264 | `n*4+byte` |
| CONV1 权重 | 200 B | 28C256 | `oc*25+ky*5+kx` |
| CONV2 权重 | 1152 B | 28C256 | `(((oc*8+ic)*3+ky)*3+kx)` |
| FC1 权重 | 12800 B | 28C256 | `neuron*400+i` |
| FC2 权重 | 320 B | 28C256 | `class*32+i` |
| 偏置 | 8/16/32/10×4 B | 28C256 | `neuron*4+byte` |
| qparam | 8/16/32/10×16 B | 28C256 | `channel*16+byte` |
| LUT | 64K×8 ×8 | 27C512 | `{A,B}` |

每片独立片选；未用地址位保留/接地，不做地址复用。

S04 的实际 24 位窗口划分（`ADDR[23:21]=000`，`ADDR[20:16]=MEM_SEL`，`ADDR[15:0]` 为片内偏移）：

| MEM_SEL | 器件 | 用途 | 有效容量 |
|---:|---|---|---:|
| 0..6 | 6264 ×7 | INPUT、CONV1_OUT、POOL1_OUT、CONV2_OUT、POOL2_OUT、FC1_OUT、FC2_LOGITS | 8 KB 窗口 |
| 7 | — | 未用 | — |
| 8..11 | 28C256 ×4 | CONV1/CONV2/FC1/FC2 权重 | 32 KB |
| 12..15 | 28C256 ×4 | 四层偏置 | 32 KB |
| 16..19 | 28C256 ×4 | 四层 qparam | 32 KB |
| 20..27 | 27C512 ×8 | 4 对 LUT 的 LO/HI | 64 KB |
| 28..31 | — | 未用 | — |

片选由 4×74HC138（按 `MEM_SEL[4:3]` 分组）+ 74HC688 地址标签比较产生；每路 `nCS_*` 只连一片存储器。6264 在 8 KB 窗口内镜像（只译 A0–A12），28C256 在 32 KB 窗口内镜像（只译 A0–A14），软件必须使用表中的基址。27C512 使用完整的 16 位地址。

S10 提供 8.000 MHz 有源振荡器（可切外部时钟）、约 70 ms 上电复位、两级 START 同步、图像/参数加载连接器和状态 LED/测试点。复位路径使用 74HC04 非施密特输入；慢沿环境建议改为 74HC14。

---

## 8. 仿真方法与复现

### 8.1 引擎

使用 KiCad 10 自带的 `ngspice.dll`（shared-library API），由 `tools/ngspice_runner.py` 调用；XSPICE 代码模型从 `models/ngspice/*.cm` 加载。这不是外部 ngspice，而是 KiCad 模拟器同一引擎。

### 8.2 命令

```bash
cd Cache/CNN_74xx_System
python sim/run_all.py            # 运行全部功能测试并写 sim/*.log
python tools/gen_lut.py          # 65536 项 LUT 逐项校验
python sim/gen_glue_tb.py        # 低有效比较器/保持逻辑专项测试
```

### 8.3 已通过

| 测试 | 结果 |
|---|---|
| 8×8 LUT 全 65536 地址逐项校验 | PASS, errors=0 |
| LUT SPICE 代表操作数 | PASS |
| 监督 FSM 状态序列 | PASS |
| 时序控制器读/写协议 | PASS |
| 低有效比较器/粘滞 RESULT_VALID 专项 | PASS, 11/11 checks |
| 存储器片选唯一性 | PASS, 323 checks / 20000 random vectors, max active CS=1 |
| POOL 2×2/stride-2/四值顺序/0/255/相等 | PASS, 10 窗口 + 40 地址检查 |
| ARGMAX signed32/并列/边界 | PASS, 5 向量 |
| CONV1 地址序列 + MAC=115200 | PASS, Python golden + 74HC161 模型 + SPICE 全序列 |
| CONV2 地址序列 + MAC=115200 | PASS, Python golden + 74HC161 模型 + SPICE 全序列 |
| FC1/FC2 地址序列 + MAC=13120 | PASS, 含 FC2 little-endian 4 字节写 |
| V2 Requant clamp/FC2 字节序/握手 | PASS, 5000×3 随机 + 定向、FC2 四字节 LE、结构/跨页/BOM/ERC |

### 8.4 仿真建模边界

- 数字逻辑采用状态位/行为级模型，不模拟 74HC 晶体管级电气特性。
- 存储器为行为级模型；读写时序由状态机和等待计数器验证。
- 逻辑综合/门级时序、扇出、传输线、电源完整性不在本次 SPICE 范围，需在 PCB/实物阶段验证。

### 8.5 最终构建顺序

```bash
python tools/build_all.py              # 模块/模板 + 变体 + 连接器 + 位号 + S00
python tools/export_review.py          # 每图 ERC/PDF + BOM
python sim/run_all.py                  # 13 组功能测试
python tools/md_to_pdf.py docs/HW_MANUAL.md -o output/pdf/HW_MANUAL.pdf
python tools/build_review_pdf.py       # 合并评审包
```

`build_all.py` 固定顺序：模块图（S05/S09/S17 写入 `templates/`）→
`make_variants.py`（6 份固定变体）→ `strip_pwr_flags.py` →
`build_boards.py`（12 张连接器图 + 清单）→ `renumber_refs.py` →
`build_top.py`。`docs/INTEGRATION_NOTES.md` 记录了顶层 ERC 的 0 error
和复现顺序。

---

## 9. 复位、上电与测试点

1. 上电：`RESET_N` 低至少 100 ns；释放后两级同步。
2. 加载图像：写 INPUT_SRAM，置 `IMAGE_READY`。
3. 加载模型：确认权重/偏置/qparam/LUT 内容，置 `MODEL_READY`。
4. 给 `START` 至少一个 CLK 宽的脉冲；观察 `BUSY` 上升。
5. 等待 `DONE`；读 `RESULT[3:0]`，确认 `RESULT_VALID=1`。
6. 若 `ERROR=1`，读 `ERROR_CODE`：0001=未就绪启动，0010=超时。

建议测试点：`CLK`、`RESET_N`、`START`、`BUSY`、`DONE`、`RESULT_VALID`、`ERROR`、各阶段 `*_START/*_DONE`、`MEM_nCE/nOE/nWE/ACK`、超时计数器最高位。

---

## 10. 已知限制与待办

1. **28×28 模型缺失**：仓库现有训练脚本是 16×16、3→8 通道、FC1 128→36，与规划书的 28×28、8→16、400→32 不符；必须重新训练/导出 28×28 模型并生成 qparam/bias/LUT 文件，才能做端到端逐位验证。
2. 当前 SPICE 覆盖监督 FSM、时序控制器、LUT 算术、低有效胶合逻辑；Pool/Argmax/Conv/FC 的地址/MAC 功能仿真已完成并 PASS；V2 Requant 另有 golden/结构/跨页检查。`sim/run_all.py` 13/13。
3. 单页 ERC 中外部输入未驱动是预期的；顶层集成后已消除。S11 已把 S07/S08/S09_FC1/S09_FC2 的地址/存储控制接到 S04；`FC_SEL`/`POOL_SEL` 只送 B11 的 map ROM。**当前顶层 ERC：0 errors / 1407 warnings。** S12A/S12B 消除了 Pool/Argmax 的 40 个数据 `pin_not_driven`；S13/S15/S17 的输入由同板引擎 ACC 驱动；S06/S04/S11 已把 Argmax 四字节 REQ/ACK 事务闭环，详见 3.8/3.9。没有短路、重复驱动或输出冲突。阶段 done 链、`RESULT_IN` 结果链和状态命名已接通；各引擎的 `*_BUSY`/`RESULT_VALID` 已改为唯一名字，不再与 S01 的全局状态线竞争。2026-11-05 已修复 Pool/Argmax 阶段 START、`DONE` 双驱动、Conv2 HWC→CHW、S11 总线适配层和 S07/S08/S09 Requant 门级化。
4. 74HC161/283/157/08/32 使用同引脚 74LS 符号派生，KiCad 会报 lib_symbol_mismatch 警告；最终可生成自定义符号库消除。
5. 超时目前是整次推理的 24 位累计超时；若要严格逐阶段超时，可把 `TIMEOUT_CLR` 分成每阶段独立计数。
6. 物理实现（PCB、扇出、电源、存储器编程）不在本次交付范围。
7. **LUT 已物理展开**：`LUT_Mult_Unit` 块符号为 0；S07/S08/S09_FC1/S09_FC2 各 8 片独立 27C512（4 lane × 低/高字节），共 32 片。当前 BOM 总数量 **1329**（**896 片 DIP IC/存储器** + 32 片 2x20P 背板排针 + 连接器/测试点/电容等）。S07 143、S08 144、S09_FC1/2 各 132 片，S13/S15 各 13 片，S17_FC1/2 各 24 片。详见 `docs/REQUANT_SIMPLE_V2.md`、`docs/FINAL_STATUS.md` 3.1 节。
8. **单页 ERC 的电源错误**：层次结构只保留 S00 的 +5V/+3V3/GND 三个 PWR_FLAG，因此单独打开子图时会出现 `power_pin_not_driven`；这是预期的，顶层 ERC 没有该错误。
9. **S09 本地 FSM 微码未导出**：S09 状态机的 27C512 内容仍是状态/控制位说明；四字节写的 `MEM_REQ/WE` 序列尚未逐状态仿真。V2 已删除 S17 的 Requant 微程序。

---

## 11. 评审清单

- [x] 顶层层次图包含 S00、S01/S02、S04–S13/S15/S17，所有子图可解析。
- [x] 每张图 ERC 0 error（或仅外部输入未驱动且有说明）。顶层 0 errors / 1407 warnings；单页剩余 error 均为外部输入未驱动。
- [x] 每个模块有 PDF、接口表、测试点。
- [x] Supervisor/Timing/LUT 仿真日志 PASS。
- [x] Pool/Argmax/Conv/FC 仿真报告 PASS。
- [ ] BOM 位号唯一、封装齐全。
- [ ] 28×28 模型审计与 qparam 契约确认。
- [x] 引擎总线适配层（S11，`C1_*`/`C2_*`/`FC_*` ↔ `ADDR/DATA/MEM_SEL`）。
- [x] `SCORE_DATA` 的 4 字节锁存与 Pool 输入缓冲（S12）；`POOL_SEL`/`FC_SEL` 已由 S01 微码输出。
- [x] Argmax 四字节读事务（S06 字节计数/`{class,byte}` 地址 + S04 缓冲 + S11 master + S02 REQ/ACK）。
- [x] V2 Requant 小核心（S13/S15/S17），固定移位/钳位/FC2 四字节，`sim/run_all.py` 13/13。
- [ ] S09 本地 FSM 微码镜像与逐状态仿真。

---

## 12. 本轮仿真发现并修复的问题

| # | 图纸 | 问题 | 修复 |
|---:|---|---|---|
| 1 | S01 | 74HC688 的 `IDLE` 输出低有效，却直接当高有效 `IDLE_MATCH` 用，导致接受 START 逻辑反相、`RESULT_VALID` 不能在新推理开始时清除 | 改名 `IDLE_N`，用 U16F 反相为 `IDLE_MATCH` |
| 2 | S01 | 三片 74HC688 的 `MATCH` 低有效，OR 后仍低有效，却直接送微码 A15 当高有效 `TIMEOUT` | 改名 `TIMEOUT_N`，用 U16E 反相为 `TIMEOUT_I` |
| 3 | S01 | `RESULT_VALID` DFF 的 D 接 GND，只在置位后保持一拍；接 +5V 又会在下一拍自动重新置位 | D=Q 反馈，形成粘滞 SR 锁存；新 START 或复位清除 |
| 4 | S02 | 74HC138 输出名是 `~{Y0}..~{Y7}`、使能是 `~{E0}/~{E1}/E2`，原映射全部落空，译码器输出 NC | 改为按引脚号映射，并正确接 E0/E1/E2 |
| 5 | S02 | 74HC688 的 `WAIT_MATCH` 低有效，微码 A4 却按高有效解释 | 先命名 `WAIT_MATCH_N`，U12B 反相为 `WAIT_MATCH` |
| 6 | S02 | 74HC245 的 `CE` 接地，空闲时数据总线被未知值驱动 | 删除 U10，由 S04 U36 唯一驱动 `MEM_D <-> DATA` |
| 7 | S07/S08/S09 | `Cx_ADDR`/`Cx_MEM_*` 未接 S04，S02_MEM_IF 悬空 | 新增 S11 映射层 + S04 6×74HCT541 汇入共享 `ADDR[15:0]` |
| 8 | S08 | Conv2 输入按 HWC 取址，与 Pool1/规格的 CHW 不符 | `INA = ic*144 + (oy+ky)*12 + (ox+kx)` |
| 9 | S12 | Pool/Argmax 的 40 个数据输入无驱动 | 1×541 缓冲 Pool，4×574 + 74HC238 拼装 Argmax |
| 10 | S06/S04/S11 | Argmax 只有 32 位锁存，SCORE_ADDR 仍是类别、S04 无 Argmax 地址/REQ | S06 2 位字节计数 + `{class,byte}`，S04 2×541，S11 master 4/ROM A7，S12 `MEM_ACK` 锁存 |
| 11 | S07/S08/S09 | `Requant_Block` 不可读；旧展开 1368 片 | V2：S13/S15/S17 固定移位小核心，共 50 片；S14/S16/S18 删除 |
| 16 | S09 | BYTE 计数器原来依赖未生成的 FSM `OUT_STB`，无法保证与 QSTB 同步 | `FC_REQ_QSTB` 直接接 74HC161 CEP/CET 和清零装载；每字节自动推进 |
| 17 | S09/S13/S15 | ACC 下拉电阻仍打 local label，与跨页 global `*_ACC` 不连通 | 改为全局标签；S09 32 个、S08 32 个 `same_local_global_label` 警告清零 |

对应验证：`sim/gen_glue_tb.py` 的 11 项检查全部通过；`sim/run_all.py` 13/13；V2 Requant 专项 PASS。上述修复都已重新生成图纸与 PDF，并重新跑过 ERC（顶层 0E/1407W）。方案 A 板卡化后 `sim/run_all.py` 13/13（新增 backplane 逐脚核对）。
