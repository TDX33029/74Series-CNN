# 模块互联方案（Interconnect Plan）

> **2026-11-07 更新：本文件描述的是旧的 14 模块 / 40 排针方案，已停止维护。**
> 当前交付是 12 张具体板卡（方案 A）；板卡划分见 `docs/BOARD_PARTITION.md`，
> 转嘉立创 EDA 的交接说明见 `docs/BOARD_HANDOFF.md`，逐脚定义见
> `output/backplane/backplane_pinout.csv`。本文仅保留为历史设计记录。


日期：2026-11-07  
适用：`Cache/CNN_74xx_System`，V2 架构  
用途：交给其他 agent 做模块绘制、端口补齐和顶层链接  
配套：`output/interconnect/interconnect_plan.csv`（机器可读连接表）

---

## 0. 先给结论

**不能只做“顶层连线”就收工。** 现有模块图基本齐全，但接口还没有闭合：

| 缺口 | 性质 | 只做顶层连线能否解决 |
|---|---|---|
| S05 Pool 没有 `POOL_MEM_REQ/WE`、`POOL_MEM_nCE_IN/OUT`、`POOL_BUSY_N` | 模块端口缺失 | **不能** |
| S05 的 `IN_ADDR/OUT_ADDR/OUT_DATA` 没有接到 S04 的 Pool 缓冲 | 顶层 + S04 缓冲缺失 | **不能** |
| S07/S08/S09 的 A、B 操作数流水都接 `DATA[7:0]`，LUT 实际算 `x*x` | 引擎内部数据通路错误 | **不能** |
| 8×574 流水线的 `Cp` 直接接 `CLK`，S02 等待期间继续移位 | 流水线没有保持/使能 | **不能** |
| S07/S08/S09 本地 FSM 的 2×27C512 没有 `.bin` 镜像 | ROM 内容缺失 | **不能** |
| 12 个 `LUT_Mult_Unit` 仍是块符号 | 封装/物理展开缺失 | **不能** |

因此本方案分两层：

- **L1 顶层互联**：用同名 `global_label` 把 14 张子图连起来；不改模块内部。
- **L2 模块接口/内部修复**：S05 补端口、S11 加 Pool master、S07/S08/S09 修 A/B 分流、生成本地 FSM 微码、展开 LUT。

> 如果其他 agent 只拿到“顶层连线”任务，他们会发现 S05 的地址/写回端口根本不存在。**必须把 L2 的 A2–A6 任务一起发下去。**

示意图：

- `output/interconnect/pool_bus_path.png`：Pool 总线（S05 → S11/S02 → S04）

---

## 1. 连接方式与命名约定

### 1.1 连接方式

推荐继续使用**全局标签（global label）**，不改成层次 sheet pin：

- 顶层 `CNN_74xx_System.kicad_sch` 只实例化 14 张子图，不画几百根跨页线。
- 每张子图把跨模块信号做成 `global_label`；KiCad 按同名网络连接。
- 同名网络**只能有一处驱动源**；双向总线用三态缓冲隔离。
- 不要在同一网络的一端再放一个同名 `local_label`，否则会分裂成两个网络。

如果后续坚持用层次 pin，必须同时改根图和所有子图符号，工作量大且容易漏；本方案不采用。

### 1.2 命名规则

| 类别 | 规则 | 例子 |
|---|---|---|
| 低有效 | 后缀 `_N` | `RESET_N`、`MEM_nCE`、`C1_BUSY_N` |
| 总线 | 逻辑名 `NAME[width]`，KiCad 实际用逐位标签 `NAME0..NAMEwidth-1` | `DATA[7:0]` → `DATA0..DATA7` |
| 阶段 | `C1/P1/C2/P2/FC1/FC2/ARGMAX` 前缀 | `C1_START`、`FC2_DONE` |
| Requant | `C1/C2/FC_REQ_*` | `C1_REQ_Q[7:0]`、`FC_REQ_QSTB` |
| 测试点 | `TP_` 前缀 | `TP_POOL_BUSY`、`TP_ARGMAX_RESULT_VALID` |

### 1.3 电源与时钟

- 全层次只在 S00 根图保留一对 `PWR_FLAG`（`+5V`、`GND`）。
- 每张子图用 `+5V`/`GND` 电源符号，不再放 `PWR_FLAG`。
- `CLK` 由 S10 输出，经 33 Ω 串联电阻后进全系统；每片 IC 旁 100 nF 去耦。
- `RESET_N` 由 S10 的 100k/1u RC + 74HC04 产生，低有效，约 69 ms 释放。

---

## 2. 模块清单与端口契约

页码是顶层 PDF 的页序；位号块见 `docs/INTEGRATION_NOTES.md`。

| 图页 | 模块 | 角色 | DIP | 关键端口 |
|---|---|---|---:|---|
| S01 | Supervisor | 20 状态微码调度 | 26 | 输入：`CLK/RESET_N/START/IMAGE_READY/MODEL_READY`、7 个 `*_DONE`、`RESULT_IN[3:0]`；输出：7 个 `*_START`、`POOL_SEL/FC_SEL`、`BUSY/DONE/RESULT_VALID/ERROR/ERROR_CODE[3:0]/RESULT[3:0]` |
| S02 | Timing | 存储读/写等待 | 11 | 输入：`CLK/RESET_N/REQ/WE`；输出：`MEM_nCE/nOE/nWE/MEM_ACK/MEM_DONE/MEM_BUSY` |
| S04 | Memories | 7×6264 + 12×28C256 + 8×27C512 | 50 | 输入：`ADDR[23:0]/MEM_SEL[4:0]/MEM_nCE/nOE/nWE/LOAD_*`、Pool 地址/写数据/`POOL_MEM_WE/POOL_BUSY_N/POOL_MEM_nCE_OUT`；双向：`DATA[7:0]`；输出：`IMAGE_READY/MODEL_READY`；新增 5×541 + 1×32 |
| S05 | Pool | 2×2 max，P1/P2 | 42 | 输入：`CLK/RESET_N/P1_START/P2_START/POOL_SEL/IN_DATA[7:0]/MEM_ACK/MEM_DONE`；输出：`IN_ADDR[12:0]/OUT_ADDR[11:0]/OUT_DATA[7:0]/OUT_WE/P1_DONE/P2_DONE/POOL_BUSY`；**新增** 5 个 Pool 总线控制 |
| S06 | Argmax | 10 类 signed32 | 45 | 输入：`CLK/RESET_N/ARGMAX_START/SCORE_DATA[31:0]/MEM_ACK/MEM_DONE`；输出：`SCORE_ADDR[5:0]/SCORE_RD/ARGMAX_DONE/ARGMAX_BUSY/ARGMAX_BUSY_N/RESULT_IN[3:0]` |
| S07 | CONV1 | 4-lane 乘加 | 111 | 输入：`CLK/RESET_N/C1_START/DATA[7:0]/MEM_ACK/MEM_DONE/MEM_BUSY`；输出：`C1_ADDR[15:0]/C1_BUSY/C1_BUSY_N/C1_MEM_REQ/WE/C1_MEM_nCE_*/C1_DONE/C1_ACC[31:0]/C1_REQ_START`；回读：`C1_REQ_Q[7:0]/QSTB/SAT/BUSY/DONE` |
| S08 | CONV2 | 4-lane 乘加 | 114 | 同 S07，前缀 `C2_` |
| S09 | FC1/FC2 | 4-lane 乘加 | 100 | 同 S07，前缀 `FC_`，另有 `FC_SEL` |
| S10 | Top I/O | 8 MHz/复位/加载/状态 | 9 | 输出：`CLK/RESET_N/START/LOAD_*/ADDR[23:0]/MEM_SEL[4:0]/IMAGE_DONE_N/MODEL_DONE_N`；输入：`BUSY/DONE/ERROR/ERROR_CODE/RESULT/RESULT_VALID/IMAGE_READY/MODEL_READY` |
| S11 | BusFabric | master/region → MEM_SEL | 12 | 输入：各 master 忙/请求/区域，Pool `POOL_BUSY(_N)/REQ/WE/nCE`；输出：`MEM_SEL[4:0]/ADDR[23:16]/REQ/WE`；**不接低 16 位地址** |
| S12 | DataAssembly | Pool 输入 + Argmax 32 位拼装 | 6 | 输入：`DATA[7:0]/SCORE_ADDR[1:0]/MEM_ACK`；输出：`IN_DATA[7:0]/SCORE_DATA[31:0]` |
| S13 | Requant C1 | `ACC>>8` clamp | 13 | 输入：`C1_ACC[31:0]/C1_REQ_START`；输出：`C1_REQ_Q[7:0]/QSTB/SAT/BUSY/DONE` |
| S15 | Requant C2 | `ACC>>9` clamp | 13 | 同 S13，前缀 `C2_` |
| S17 | Requant FC | FC1 `>>8` / FC2 raw | 24 | 输入：`FC_ACC[31:0]/FC_REQ_START/FC_SEL`；输出：`FC_REQ_Q[7:0]/QSTB/SAT/BUSY/DONE` |

> DIP 是当前值；完成 L2 后 S11 从 12→13（+1×74HC157），S04 从 50→56（+5×74HCT541 + 1×74HC32），S05 基本不变。

---

## 3. 顶层网络清单

> 以下 `source`/`dest` 用“模块.端口”表示；`width` 是逻辑位宽。完整逐行版本见 `output/interconnect/interconnect_plan.csv`。

### 3.1 时钟、复位、电源

| 网络 | 宽度 | 源 | 目的 | 有效 | 备注 |
|---|---:|---|---|---|---|
| `CLK` | 1 | S10.CLK | S01/S02/S04–S09/S11/S13/S15/S17 | 上升沿 | 33 Ω 串联 |
| `RESET_N` | 1 | S10.RESET_N | 同上 | 低 | 异步复位，约 69 ms |
| `+5V` | 1 | 电源 | 全部 | — | 每片 100 nF |
| `GND` | 1 | 电源 | 全部 | — | — |

### 3.2 主机加载与就绪

| 网络 | 宽度 | 源 | 目的 | 有效 | 备注 |
|---|---:|---|---|---|---|
| `START` | 1 | S10.START | S01.START | 高 | 同步后单拍 |
| `LOAD_EN` | 1 | S10.LOAD_EN | S04.LOAD_EN | 高 | **必须与 `BUSY` 互锁** |
| `ADDR[23:16]` | 8 | S10 或 S11 | S04.ADDR | — | `LOAD_EN=1` 时由 S10 驱动；否则 S11 |
| `ADDR[15:0]` | 16 | S10 或 S04 内部 master mux | S04.ADDR | — | 加载时 S10；推理时由 S04 在 C1/C2/FC/Argmax/Pool 地址缓冲间选择 |
| `LOAD_DATA[7:0]` | 8 | S10 | S04.LOAD_DATA | — | 主机写数据 |
| `LOAD_nOE` | 1 | S10 | S04 | 低 | 主机读 |
| `LOAD_nWE` | 1 | S10 | S04 | 低 | 主机写 |
| `IMAGE_DONE_N` | 1 | S10 | S04 | 低 | 图像加载完成脉冲 |
| `MODEL_DONE_N` | 1 | S10 | S04 | 低 | 权重加载完成脉冲 |
| `IMAGE_READY` | 1 | S04 | S01/S10 | 高 | 就绪锁存 |
| `MODEL_READY` | 1 | S04 | S01/S10 | 高 | 就绪锁存 |

### 3.3 阶段控制

| 网络 | 宽度 | 源 | 目的 | 有效 | 备注 |
|---|---:|---|---|---|---|
| `C1_START` | 1 | S01 | S07 | 高 | 单拍 |
| `C1_DONE` | 1 | S07 | S01 | 高 | 单拍 |
| `P1_START` | 1 | S01 | S05 | 高 | `POOL_SEL=0` |
| `P1_DONE` | 1 | S05 | S01 | 高 | `POOL_DONE & ~POOL_SEL` |
| `C2_START` | 1 | S01 | S08 | 高 | 单拍 |
| `C2_DONE` | 1 | S08 | S01 | 高 | 单拍 |
| `P2_START` | 1 | S01 | S05 | 高 | `POOL_SEL=1` |
| `P2_DONE` | 1 | S05 | S01 | 高 | `POOL_DONE & POOL_SEL` |
| `FC1_START` | 1 | S01 | S09 | 高 | `FC_SEL=0` |
| `FC1_DONE` | 1 | S09 | S01 | 高 | 单拍 |
| `FC2_START` | 1 | S01 | S09 | 高 | `FC_SEL=1` |
| `FC2_DONE` | 1 | S09 | S01 | 高 | 单拍 |
| `ARGMAX_START` | 1 | S01 | S06 | 高 | 单拍 |
| `ARGMAX_DONE` | 1 | S06 | S01 | 高 | 单拍 |
| `POOL_SEL` | 1 | S01 | S05/S11 | 高 | 0=P1，1=P2 |
| `FC_SEL` | 1 | S01 | S09/S11/S17 | 高 | 0=FC1，1=FC2 |

### 3.4 存储 master 端口

#### C1（S07）

| 网络 | 宽度 | 源 | 目的 | 备注 |
|---|---:|---|---|---|
| `C1_ADDR[15:0]` | 16 | S07 | S04 | 仅 `C1_BUSY=1` 时驱动；S04 U44/U45 缓冲 |
| `C1_BUSY` | 1 | S07 | S11/S01 | 高 |
| `C1_BUSY_N` | 1 | S07 | S04/S11 | 低，地址缓冲 OE |
| `C1_MEM_REQ` | 1 | S07 | S11 | 高，直到 ACK |
| `C1_MEM_WE` | 1 | S07 | S11 | 高=写 |
| `C1_MEM_nCE_IN` | 1 | S07 | S11 | 低一热 |
| `C1_MEM_nCE_W` | 1 | S07 | S11 | 低一热 |
| `C1_MEM_nCE_OUT` | 1 | S07 | S11 | 低一热 |
| `C1_MEM_nCE_B` | 1 | S07 | S11 | 保留 |
| `C1_MEM_nCE_Q` | 1 | S07 | S11 | 保留 |
| `C1_MEM_nCE_MC` | 1 | S07 | S11 | LUT 低/高字节 |

#### C2（S08）与 FC（S09）

同 C1，分别把前缀换成 `C2_`、`FC_`。FC 额外有 `FC_SEL` 输入。

#### Pool（S05，**新增**）

| 网络 | 宽度 | 源 | 目的 | 备注 |
|---|---:|---|---|---|
| `POOL_IN_ADDR[12:0]` | 13 | S05 | S04 | 读地址，0..4607/1151 |
| `POOL_OUT_ADDR[11:0]` | 12 | S05 | S04 | 写地址，0..1151/399 |
| `POOL_OUT_DATA[7:0]` | 8 | S05 | S04 | 写数据，经 S04 541 上 DATA |
| `POOL_MEM_REQ` | 1 | S05 | S11 | 高，直到 ACK |
| `POOL_MEM_WE` | 1 | S05 | S11/S04 | 高=写；S04 读缓冲切换 |
| `POOL_MEM_nCE_IN` | 1 | S05 | S11 | 低，读窗口；S11 region 编码 |
| `POOL_MEM_nCE_OUT` | 1 | S05 | S11/S04 | 低，写窗口；S04 写地址/数据 OE |
| `POOL_BUSY` | 1 | S05 | S11/TP | 高 |
| `POOL_BUSY_N` | 1 | S05 | S11/S04 | 低；S11 74HC148 I2，S04 读缓冲保持使能 |


#### Argmax（S06）

| 网络 | 宽度 | 源 | 目的 | 备注 |
|---|---:|---|---|---|
| `SCORE_ADDR[5:0]` | 6 | S06 | S04/S12 | `class*4+byte` |
| `SCORE_RD` | 1 | S06 | S11/S04 | 高=读 |
| `ARGMAX_BUSY` | 1 | S06 | S11 | 高 |
| `ARGMAX_BUSY_N` | 1 | S06 | S04/S11 | 低 |

### 3.5 总线与存储时序

| 网络 | 宽度 | 源 | 目的 | 有效 | 备注 |
|---|---:|---|---|---|---|
| `MEM_SEL[4:0]` | 5 | S11（推理）/ S10（加载） | S04 | — | 窗口选择 |
| `ADDR[23:16]` | 8 | S11 或 S10 | S04 | — | `{000,MEM_SEL}` |
| `REQ` | 1 | S11 | S02 | 高 | 所有 master 合并 |
| `WE` | 1 | S11 | S02 | 高 | 所有 master 合并 |
| `MEM_nCE` | 1 | S02 | S04 | 低 | 片选 |
| `MEM_nOE` | 1 | S02 | S04 | 低 | 读使能 |
| `MEM_nWE` | 1 | S02 | S04 | 低 | 写使能 |
| `MEM_ACK` | 1 | S02 | S06/S07/S08/S09/S11/S12 | 高 | 单拍 |
| `MEM_DONE` | 1 | S02 | 同上 | 高 | 单拍 |
| `MEM_BUSY` | 1 | S02 | 同上 | 高 | 事务进行中 |
| `DATA[7:0]` | 8 | S04 读 / S07/S08/S09 写 / S04（Pool 写） | S04/S12 | — | 三态，见 3.8 |

### 3.6 数据装配与 Requant

| 网络 | 宽度 | 源 | 目的 | 备注 |
|---|---:|---|---|---|
| `IN_DATA[7:0]` | 8 | S12 | S05 | 由 `DATA` 缓冲 |
| `SCORE_DATA[31:0]` | 32 | S12 | S06 | 4 字节小端拼装 |
| `SCORE_ADDR[1:0]` | 2 | S06 | S12 | 字节 lane |
| `C1_ACC[31:0]` | 32 | S07 | S13 | 累加器 |
| `C1_REQ_START` | 1 | S07 | S13 | 单拍 |
| `C1_REQ_Q[7:0]` | 8 | S13 | S07 | 量化结果 |
| `C1_REQ_QSTB` | 1 | S13 | S07 | 单拍 |
| `C1_SAT_FLAG` | 1 | S13 | S07/TP | 高=饱和 |
| `C1_REQ_BUSY` | 1 | S13 | S07 | 高 |
| `C1_REQ_DONE` | 1 | S13 | S07 | 单拍 |
| `C2_*` | — | S08/S15 | — | 同 C1 |
| `FC_ACC[31:0]` | 32 | S09 | S17 | 累加器 |
| `FC_REQ_START` | 1 | S09 | S17 | 单拍 |
| `FC_REQ_Q[7:0]` | 8 | S17 | S09 | FC1 Q8 或 FC2 字节 |
| `FC_REQ_QSTB` | 1 | S17 | S09 | FC2 每字节一次 |
| `FC_SAT_FLAG` | 1 | S17 | S09/TP | 高=饱和 |
| `FC_REQ_BUSY` | 1 | S17 | S09 | 高 |
| `FC_REQ_DONE` | 1 | S17 | S09 | 单拍 |

### 3.7 状态与结果

| 网络 | 宽度 | 源 | 目的 | 备注 |
|---|---:|---|---|---|
| `BUSY` | 1 | S01 | S10 | 系统忙 |
| `DONE` | 1 | S01 | S10 | 单拍 |
| `RESULT_VALID` | 1 | S01 | S10 | 单拍/保持 |
| `RESULT[3:0]` | 4 | S01 | S10 | class 0..9 |
| `ERROR` | 1 | S01 | S10 | 高 |
| `ERROR_CODE[3:0]` | 4 | S01 | S10 | 错误码 |
| `RESULT_IN[3:0]` | 4 | S06 | S01 | Argmax 结果 |
| `TP_ARGMAX_RESULT_VALID` | 1 | S06 | TP | 仅测试点，不参与 S01 |
| `TP_POOL_BUSY` | 1 | S05 | TP | 仅测试点 |

### 3.8 `DATA[7:0]` 三态归属

| 主控 | 驱动条件 | 说明 |
|---|---|---|
| S04 | `MEM_nCE=0 & MEM_nOE=0` | 读数据 |
| S07 | `C1_BUSY=1 & C1_MEM_WE=1` | Conv1 写 |
| S08 | `C2_BUSY=1 & C2_MEM_WE=1` | Conv2 写 |
| S09 | `FC_BUSY=1 & FC_MEM_WE=1` | FC 写 |
| S04 Pool 写缓冲 | `POOL_MEM_nCE_OUT=0`（新增） | Pool 写，S04 541 驱动 DATA |
| S12 | 只读，不驱动 | `DATA → IN_DATA` |

因为 S01 串行化阶段，同一时刻只有一个 `*_BUSY=1`；`LOAD_EN` 必须与 `BUSY` 互锁，否则主机会和引擎争总线。

---

## 4. S11 映射与 S04 存储窗口

### 4.1 master 编码

| MASTER[2:0] | 引擎 | 忙信号 |
|---:|---|---|
| 0 | 保留（74HC148 不产生） | — |
| 1 | C1 | `C1_BUSY` |
| 2 | C2 | `C2_BUSY` |
| 3 | FC | `FC_BUSY` |
| 4 | Argmax | `ARGMAX_BUSY` |
| 5 | Pool | `POOL_BUSY_N`（新增，接 74HC148 的 I2） |
| 6 | 保留 | — |
| 7 | 无/idle | 所有忙信号无效时 74HC148 的自然输出 |

### 4.2 region 编码

| REGION[2:0] | 区域 | 说明 |
|---:|---|---|
| 0 | IN | 输入特征图 |
| 1 | W | 权重 |
| 2 | OUT | 输出特征图 |
| 3 | B | bias（V2 不用） |
| 4 | Q | qparam（V2 不用） |
| 5 | MC | LUT 低/高字节 |
| 7 | NONE | 无 |

### 4.3 map ROM 地址

```text
A[8:0] = {POOL_SEL, MASTER[2], FC_SEL, MASTER[1:0], REGION[2:0], 0}
D[4:0] = MEM_SEL[4:0]
```

- **保留现有 A0–A7 接线不动**（A0=GND、A1–A3=REGION、A4–A5=MASTER[1:0]、A6=FC_SEL、A7=MASTER[2]），只把新增的 `POOL_SEL` 接到 A8。这样只多一根线，不需要重排 map ROM 地址。
- 27C512 有 16 根地址线（A0–A15），9 位地址足够；未用地址写 `0x1F`（无设备）。
- 对非 FC master，`FC_SEL` 填 0；对非 Pool master，`POOL_SEL` 填 0。
- 对 Pool：`FC_SEL=0`，`POOL_SEL` 选 P1/P2。

### 4.4 Pool 映射（新增）

| MASTER | POOL_SEL | REGION | MEM_SEL | 窗口 |
|---:|---:|---:|---:|---|
| 5 | 0 | IN | 1 | `CONV1_OUT` |
| 5 | 0 | OUT | 2 | `POOL1_OUT` |
| 5 | 1 | IN | 3 | `CONV2_OUT` |
| 5 | 1 | OUT | 4 | `POOL2_OUT` |
| 5 | x | 其他 | 31 | 无 |

### 4.5 S04 存储窗口

| MEM_SEL | 器件 | 用途 | V2 |
|---:|---|---|---|
| 0 | 6264 | INPUT | 用 |
| 1 | 6264 | CONV1_OUT | 用 |
| 2 | 6264 | POOL1_OUT | 用 |
| 3 | 6264 | CONV2_OUT | 用 |
| 4 | 6264 | POOL2_OUT | 用 |
| 5 | 6264 | FC1_OUT | 用 |
| 6 | 6264 | FC2_LOGITS | 用 |
| 7 | — | 未映射 | 否 |
| 8–11 | 28C256 | W_CONV1/CONV2/FC1/FC2 | 用 |
| 12–15 | 28C256 | B_* | 否（bias=0） |
| 16–19 | 28C256 | Q_* | 否（固定移位） |
| 20–27 | 27C512 | LUT0–3 低/高 | 用（待展开） |
| 28–31 | — | 未映射 | 否 |

窗口地址：`ADDR[23:16]={000,MEM_SEL}`，`ADDR[15:0]` 是偏移。

---

## 5. 端到端握手顺序

```text
S10: RESET_N 释放，CLK 运行
S04: IMAGE_READY / MODEL_READY
S01: G_WAIT_READY → G_IDLE
S10: START 脉冲
S01: G_C1_START  →  C1_START  → S07
S07: 读 INPUT/W，MAC，S13 requant，写 CONV1_OUT
S07: C1_DONE → S01
S01: G_P1_START  →  P1_START + POOL_SEL=0 → S05
S05: 读 CONV1_OUT 4 字节（地址/写数据经 S04 缓冲），max，写 POOL1_OUT
S05: P1_DONE → S01
S01: G_C2_START  →  C2_START → S08
S08: 读 POOL1_OUT/W，MAC，S15 requant，写 CONV2_OUT
S08: C2_DONE → S01
S01: G_P2_START  →  P2_START + POOL_SEL=1 → S05
S05: 读 CONV2_OUT 4 字节（地址/写数据经 S04 缓冲），max，写 POOL2_OUT
S05: P2_DONE → S01
S01: G_FC1_START → FC1_START + FC_SEL=0 → S09
S09: 读 POOL2_OUT/W，MAC，S17 requant，写 FC1_OUT
S09: FC1_DONE → S01
S01: G_FC2_START → FC2_START + FC_SEL=1 → S09
S09: 读 FC1_OUT/W，MAC，S17 四字节，写 FC2_LOGITS
S09: FC2_DONE → S01
S01: G_AM_START → ARGMAX_START → S06
S06: 40 次读 FC2_LOGITS，S12 拼 32 位，比较，RESULT_IN
S06: ARGMAX_DONE → S01
S01: G_FINISH → DONE/RESULT_VALID
S01: G_WAIT_START_LOW → G_IDLE
```

每个存储事务：

```text
MASTER: 地址 + MEM_REQ + WE + region nCE
S11:    MEM_SEL + ADDR[23:16] + REQ + WE
S02:    MEM_nCE/nOE/nWE，等待 3/2 拍
S04:    读数据或写数据
S02:    MEM_ACK / MEM_DONE
MASTER: 采样数据或结束写
```

> 所有 master 的低 16 位地址都不经过 S11：C1/C2/FC 的 `*_ADDR[15:0]` 直接进 S04 的 U44–U49 缓冲，Argmax 进 U50/U51，Pool 进新增的 4×541 地址缓冲 + 1×541 写数据。S11 只产生 `MEM_SEL[4:0]`、`ADDR[23:16]`、`REQ`、`WE`。

---

## 6. 模块修改清单（L2）

### 6.1 S05 Pool：补 5 个总线控制输出

**新增端口**

| 端口 | 方向 | 有效 | 产生条件 |
|---|---|---|---|
| `POOL_MEM_REQ` | 输出 | 高 | 读/写事务期间 |
| `POOL_MEM_WE` | 输出 | 高 | 写 `POOL*_OUT` 时 |
| `POOL_MEM_nCE_IN` | 输出 | 低 | 读输入窗口时 |
| `POOL_MEM_nCE_OUT` | 输出 | 低 | 写输出窗口时 |
| `POOL_BUSY_N` | 输出 | 低 | `~POOL_BUSY`，供 S11 74HC148 |

**新增输入**

| 端口 | 方向 | 说明 |
|---|---|---|
| `MEM_ACK` | 输入 | 读数据有效；S05 在 `MEM_ACK=1` 时锁存 `IN_DATA` |
| `MEM_DONE` | 输入 | 事务结束；S05 在 `MEM_DONE=1` 后撤销 `POOL_MEM_REQ` 并推进状态 |

> S05 原来没有存储握手，只有 `IN_DATA`。作为 S11 master 后必须等 S02 的 `MEM_ACK/MEM_DONE`，不能按固定节拍假设数据已到。


**实现建议**

- 从现有 one-hot FSM 的读/写状态译码，**复用现有 U39（74HCT541）的空闲 Y3–Y6 通道**输出，不新增芯片；但读/写状态必须改成“发 REQ → 等 MEM_ACK/MEM_DONE → 推进”的握手，不能沿用固定节拍。
- `POOL_MEM_REQ` 必须限定在**读/写事务状态**（`POOL_RD | POOL_WR`），不能简单等于整个 `POOL_BUSY`；否则两次事务之间 region 会落到 OUT，产生伪写。`POOL_MEM_WE` 等于写状态下的 `OUT_WE`；先确认 `OUT_WE` 只在 WT 状态为高，若它在整个 Pool 期间为高，必须改用 WT 状态译码。
- `POOL_MEM_nCE_IN` 在读状态有效，`POOL_MEM_nCE_OUT` 在写状态有效；两者不能同时低。
- 读：`REQ=1, WE=0, nCE_IN=0`，等 `MEM_ACK` 锁存 `IN_DATA`，等 `MEM_DONE` 撤 REQ；写：`REQ=1, WE=1, nCE_OUT=0`，等 `MEM_DONE` 撤 REQ。
- `IN_ADDR`/`OUT_ADDR`/`OUT_DATA` 必须在 `nCE/REQ` 之前建立，并保持到 `MEM_DONE`；S04 的缓冲 OE 直接由 nCE 控制，地址/数据晚到会写错窗口。
- 现有 `IN_ADDR[12:0]`、`OUT_ADDR[11:0]`、`OUT_DATA[7:0]` 已经是 global label，保留。
- `POOL_BUSY_N` 用现有 U40（74HC02）的空闲门反相：`5=BUSY_I, 6=GND, 4=POOL_BUSY_N`，不新增芯片。
- **S05 BOM 基本不变（42 片）**；握手等待逻辑优先用现有 U38/U40/U41 的空闲门，若不够再 +1 片 74HC08/74HC32，并在报告中说明。

**验收**

- 顶层网表中 `POOL_MEM_REQ`、`POOL_MEM_WE`、`POOL_MEM_nCE_IN/OUT`、`POOL_BUSY_N` 至少 2 个节点。
- `POOL_MEM_nCE_IN` 与 `POOL_MEM_nCE_OUT` 不会同时为低。
- Pool 读 4 字节/写 1 字节的顶层测试通过。

### 6.2 S11：增加 Pool master（只做映射/请求，不搬地址数据）

S11 不接管 Pool 的 16 位低地址和 8 位写数据；这两组仍由 S04 的地址/数据缓冲处理。S11 只负责“Pool 现在访问哪个窗口”和“把 REQ/WE 合并”。

**新增输入**

- `POOL_BUSY`（region mux 选择）
- `POOL_BUSY_N`（74HC148 I2，低有效）
- `POOL_MEM_REQ`、`POOL_MEM_WE`
- `POOL_MEM_nCE_IN`、`POOL_MEM_nCE_OUT`
- `POOL_SEL`

**修改**

1. master 编码从 4 个扩到 5 个：`C1=1, C2=2, FC=3, ARGMAX=4, POOL=5`。Pool 的 `POOL_BUSY_N` 接到现有 74HC148 的空闲 `I2`（低有效），**不新增 148**。
2. map ROM 地址增加 `POOL_SEL` 到 A8：`A[8:0] = {POOL_SEL, MASTER[2], FC_SEL, MASTER[1:0], REGION[2:0], 0}`；现有 A0–A7 不动，数据仍是 `MEM_SEL[4:0]`。
3. Pool region 编码：`POOL_MEM_nCE_IN` → REGION=0；`POOL_MEM_nCE_OUT` → REGION=2（即 `REGION1=POOL_MEM_nCE_IN`：IN 时 nCE_IN=0→REGION=0，OUT 时 nCE_IN=1→REGION=2；REGION0/2=0）。
4. 新增 **1×74HC157** 作为第三级 region mux：`S=POOL_BUSY`，`I0=现有 REGION[2:0]`，`I1={1'b0, POOL_MEM_nCE_IN, 1'b0}`（利用 IN/OUT 互斥：IN 时 nCE_IN=0→REGION=0，OUT 时 nCE_IN=1→REGION=2，省一个反相器）；Pool 忙时选 Pool region，空闲时透传现有 C1/C2/FC region。
5. `POOL_MEM_REQ/WE` 并入 `REQ/WE` 合并逻辑。
6. **不要**在 S11 里加 Pool 地址 mux 或 DATA 缓冲；这些放在 S04（见 6.2b），避免和 S04 现有 `ADDR[15:0]` 三态缓冲冲突。

**BOM 影响**：S11 从 12 片增至 13 片（+1×74HC157）；不新增 74HC148。

**验收**

- S11 map ROM 生成器输出 Pool 4 行，`MEM_SEL` 分别 1/2/3/4。
- 顶层网表 `POOL_MEM_REQ/WE/nCE` 均 ≥2 节点。
- S11 不驱动 `ADDR[15:0]` 或 `DATA[7:0]`（除现有高 8 位地址/映射）。

### 6.2b S04：Pool 低 16 位地址与写数据缓冲

S04 现有 `ADDR[15:0]` 是三态共享总线，由 S10（加载）和 C1/C2/FC/Argmax 的 74HCT541 缓冲驱动。Pool 只需要再加两组缓冲，不要改 S11：

**新增输入**

- `POOL_IN_ADDR[12:0]`
- `POOL_OUT_ADDR[11:0]`
- `POOL_OUT_DATA[7:0]`
- `POOL_MEM_WE`
- `POOL_BUSY_N`
- `POOL_MEM_nCE_OUT`

**实现**

1. **读地址缓冲**：2×74HCT541，输入 `{3'b0, POOL_IN_ADDR[12:0]}`，输出 `ADDR[15:0]`，OE = `POOL_BUSY_N | POOL_MEM_WE`（Pool 忙且非写时使能，保证事务间 ADDR 不浮空）。
2. **写地址缓冲**：2×74HCT541，输入 `{4'b0, POOL_OUT_ADDR[11:0]}`，输出 `ADDR[15:0]`，OE = `POOL_MEM_nCE_OUT`（只在 Pool 写事务时有效）。
3. **写数据缓冲**：1×74HCT541，`A=POOL_OUT_DATA[7:0]`，`Y=DATA[7:0]`，`OE=POOL_MEM_nCE_OUT`。
4. 读/写地址缓冲的 OE 互斥：读缓冲在 `POOL_BUSY_N=0 & POOL_MEM_WE=0` 时使能，写缓冲只在 `POOL_MEM_nCE_OUT=0` 时使能；Pool 空闲时读缓冲关闭。
5. **BOM 影响**：S04 从 50 片增至 56 片（5×74HCT541 + 1×74HC32）。
6. 读缓冲 OE 的 OR 门用 1×74HC32（`POOL_BUSY_N | POOL_MEM_WE`）；如果不想加这 6 片，只能改 S04 现有 C1/C2/FC 地址缓冲的选择逻辑，风险更高，不推荐。

**验收**

- Pool 读时 `ADDR[15:0]` 等于 `{3'b0, POOL_IN_ADDR}`；写时等于 `{4'b0, POOL_OUT_ADDR}`。
- Pool 写时 `DATA[7:0]` 由 S04 541 驱动；其他时间高阻。
- 与 S10 加载、C1/C2/FC/Argmax 缓冲不冲突。

### 6.3 S07/S08/S09：A/B 操作数分流

这里其实有**两个**问题，只修 A/B 来源不够：

1. `A_ST` 和 `B_ST` 两条 4 级 74HCT574 流水都从 `DATA[7:0]` 进，LUT 的 A/B 实际同源，算出来是 `x*x`。
2. 8×574 的 `Cp` 直接接 `CLK`，**没有使能/保持**。S02 读等待 3 拍、写等待 2 拍期间流水线继续移位，操作数会错位。必须给流水线加保持或使能。

**方案 A（推荐，保留现有计数器/ACC 时序）**

- 在 A/B 流水线前各加 1×74HCT574 输入锁存（`A_LAT`/`B_LAT`），用 4×74HC157 做保持 mux；或加 74HC573/377 符号，省掉这 4 片 157。
- 8 级流水线每级加 2:1 保持 mux（74HC157），`SHIFT_EN=0` 时保持；共 16×74HC157/引擎。
- FSM：读 A → `A_LOAD`；读 B → `B_LOAD`；`SHIFT_EN` 一次，两条流水线同时移入对齐的 A/B；`MAC_EN`/`ACC_LD` 保持现有“每 MAC 一次、每 4 MAC 累加”的时序。
- 芯片增量（全用现有 574/157 符号）：+2×574 + 20×157/引擎（2 个输入锁存用 4×157，8 级保持用 16×157），共 +66 片。若给 74HC573/377 加符号，输入锁存可省 4×157：+2×573/377 + 16×157/引擎，共 +54 片。
- **CONV1 的 25 MAC 仍不是 4 的倍数**：方案 A 也要 padding 到 28（kx=5,6 权重为 0，权重布局改为每 oc 28 B，OC 步长 25→28）或加 lane mask；推荐 padding，避免第 7 组 stale lane。
- 优点：KX/KY/ACC/LANE 计数器完全不用改；缺点是芯片多。

**方案 B（8 级 FIFO，芯片少但 FSM/地址要重写）**

- 8×574 串成一条 8 级 FIFO，**仍需每级保持 mux**（16×157/引擎），否则等待态也会移位。
- FSM 按 `A0,B0,A1,B1,A2,B2,A3,B3` 读 8 个字节，`MAC_EN` 一次；`ACC_LD=MAC_EN`；KX/地址计数器必须改成**每操作数推进**，不能再由 `MAC_EN` 驱动；CONV1 的 25 MAC 还要 padding 到 28（kx=5,6 权重为 0），避免最后一组 stale lane。
- 只有确认 A4 愿意重写地址/ACC 时序时才选这个；否则不要用。

**方案 C（不推荐）：门控时钟**

- 用 `A_LOAD/B_LOAD` 门控 574 的 `Cp`；8 MHz 下可能可用，但时钟树/毛刺风险高，评审不应接受。

**验收**

- 给一组已知 3×3/5×5 输入和权重，逐 MAC 比对 `ACC` 与 golden；`PROD` 必须等于 `A*B`，不能是 `x*x`。
- 至少覆盖 4 个 lane 边界和 CONV1 padding 后的 7 组边界。

### 6.4 S07/S08/S09：本地 FSM 微码

- 每个引擎生成 `*_rom1.bin`、`*_rom2.bin`（27C512，64K×8）。
- ROM 地址：`{IMAGE_LAST, REQ_DONE, MEM_ACK, POINT_LAST, START_S, ST[4:0]}`（10 位）。
- **方案 A**：状态机增加 `S_READ_A`、`S_READ_B`、`S_SHIFT` 三个状态；`A_LOAD/B_LOAD/SHIFT_EN` 由 74HC138 状态译码 + 少量门产生，不占 ROM2 数据位。5 位状态寄存器有余量，ROM 地址仍 10 位。
- **方案 B**：增加 `OP_CNT[2:0]`（或把 8 个操作数周期展开成 8 个状态），ROM 地址扩到 13 位；27C512 仍足够。
- ROM1 数据：D0..D4 下一状态，D5 `BUSY`，D6 `DONE`，D7 `ACC_CLR`。
- ROM2 数据：D0 `MAC_EN`，D1 `MEM_REQ`，D2 `MEM_WE`，D3 `OUT_STB`，D4 `LUT_AB_LATCH`，D5 `LUT_PROD_LATCH`，D6/D7 `ADD_SEL`。方案 B 下 D0 只在第 8 个操作数周期为 1。
- 未用地址写 0（回 `E_RESET`）。
- 逐状态测试每个条件分支。

### 6.5 LUT 物理展开

- 当前 12 个 `LUT_Mult_Unit` 块符号必须变成 27C512 封装。
- **首版推荐“每引擎 8 片、共 24 片”**：4 条 lane 各自一对低/高字节 ROM，和现有 4 个 `LUT_Mult_Unit` 一一对应，调试最直观，也符合“不压缩芯片数量”的目标。
- 备选“8 片共享”：4 条 lane 共用一对 ROM，三引擎通过输入 mux 分时复用；BOM 小，但 lane/engine 选择逻辑和时序更复杂，建议作为后续降本版本。
- 需要补：A/B 地址锁存（`LUT_AB_LATCH`）、PROD 输出锁存（`LUT_PROD_LATCH`）、地址/数据缓冲、lane 选择、`LUT_CE_N/OE_N`、100 nF 去耦、未用地址下拉。

### 6.6 小改动

| 模块 | 改动 |
|---|---|
| S01 | 可增加 `POOL_BUSY` 输入做状态/超时监视；不改变 20 状态主序列 |
| S10 | `LOAD_EN` 增加 `& ~BUSY` 门控（优先用空闲门；不够则 +1×74HC08）；`POOL_BUSY` 可做状态 LED |
| S12 | 不变；确认 `SCORE_ADDR[1:0]`、`MEM_ACK` 已接 |
| S06 | `ARGMAX_RESULT_VALID` 改名为 `TP_ARGMAX_RESULT_VALID`，只做测试点 |
| S04 | Pool 读地址 OE=`POOL_BUSY_N` OR `POOL_MEM_WE`，写地址/数据 OE=`POOL_MEM_nCE_OUT`，见 6.2b |

---

## 7. Agent 任务拆分

建议按以下工包发任务；每个 agent 只改自己目录/文件，最后统一集成。

| 工包 | 负责内容 | 主要文件 | 交付/验收 | 依赖 |
|---|---|---|---|---|
| **A0** | 冻结网络名和端口表 | `docs/INTERCONNECT_PLAN.md`、CSV | 所有 agent 使用同一套名字 | 无 |
| **A1** | 顶层层次图/位号/ERC | `CNN_74xx_System.kicad_sch`、`tools/build_top.py`、`tools/renumber_refs.py` | 14 张子图实例化；0 error；无意外单节点 | A0 |
| **A2** | S05 Pool 端口补齐 | `S05_Pool.kicad_sch`、`tools/build_pool.py` | 5 个新控制输出 + `MEM_ACK/MEM_DONE` 握手（复用空闲门，BOM 基本不变）；Pool 读/写测试 | A0 |
| **A3** | S11 Pool master/map | `S11_BusFabric.kicad_sch`、`tools/build_bus.py`、`tools/gen_bus_map.py` | Pool 4 行 map；A8=POOL_SEL；+1×157 region mux；REQ/WE 合并；无总线冲突 | A2 |
| **A3b** | S04 Pool 地址/数据缓冲 | `S04_Memories.kicad_sch`、`tools/build_memories.py` | 5×541（2 读地址 + 2 写地址 + 1 写数据）+ 1×74HC32（读 OE）；S04 BOM +6 | A2 |
| **A4** | S07/S08/S09 A/B 分流 | `S07_Conv1.kicad_sch`、`S08_Conv2.kicad_sch`、`S09_FC.kicad_sch`、对应 builder | 方案 A：A/B 输入锁存 + 8 级保持 mux；`PROD=A*B`；等待态不错位 | A0 |
| **A5** | 本地 FSM 微码 | `tools/build_conv1.py`、`build_conv2.py`、`build_fc.py`、`sim/gen_engine_tb.py` | 6 个 `.bin`；逐状态测试 | A4 |
| **A6** | LUT 展开 | `S_LUT_Mult_1`、S07/S08/S09、BOM | 12 块 → 8/24 片 27C512；BOM/ERC 更新 | A4 |
| **A7** | 集成验证 | `sim/run_all.py`、`tools/export_review.py` | 11/11 + 新测试；顶层 ERC 0E；netlist audit | A1–A6 |
| **A8** | 文档/PDF | `docs/*`、`tools/md_to_pdf.py` | 更新手册/评审包 | A7 |

### 7.1 每个 agent 的边界

- **只改自己负责的 `.kicad_sch` 和 builder**；不要改别人的图。
- 所有跨模块网络名以本文件第 3 节为准；新增网络先加到 CSV。
- 修改后必须跑：
  ```bash
  python tools/renumber_refs.py
  python tools/strip_pwr_flags.py
  python tools/build_top.py
  python tools/export_review.py --no-preview
  python sim/run_all.py
  ```
- 不允许用“local label 同名”绕过跨页连接；必须用 `global_label`。
- 不允许在顶层用导线把两个输出直接短接；总线冲突必须靠三态/使能解决。

---

## 8. 验收标准

### 8.1 结构

- [ ] 顶层 ERC：**0 errors**；warning 分类有清单。
- [ ] 顶层 netlist：除显式 `TP_*` 外，无单节点模块边界网。
- [ ] `DATA[7:0]` 同时只有一个驱动源；`POOL_MEM_nCE_IN/OUT` 不同时为低。
- [ ] S11 map ROM 的 Pool 4 行、Argmax 8 行、C1/C2/FC 各 6 行全部正确。
- [ ] 所有 `*_START` 单拍；所有 `*_DONE` 单拍；`QSTB`/`DONE` 拍数符合 V2 表。

### 8.2 功能

- [ ] Pool：从 S04 读 4 字节、写 1 字节，P1/P2 各 1 个窗口。
- [ ] Conv1/Conv2/FC：已知输入/权重逐 MAC 比对，`PROD=A*B`；S02 读等待 3 拍/写等待 2 拍下也不错位。
- [ ] Requant：5000 随机 + 定向向量；FC2 四字节 LE。
- [ ] Argmax：10 类、并列、`-2^31/2^31-1`。
- [ ] 端到端：28×28 图像 → class 0..9，与软件 golden 一致。

### 8.3 规模/文档

- [ ] DIP 预算：当前 576；Pool +7、A/B +66、S10 +0–1；LUT 展开另计（24 片方案约 +24×27C512 + 缓冲）。
- [ ] BOM 不再有 `LUT_Mult_Unit` 块符号。
- [ ] DIP 数量、BOM 总数、ERC warning 数更新到文档。
- [ ] `docs/INTERCONNECT_PLAN.md` 与 CSV 和实际网表一致。

---

## 9. 需要用户/架构师拍板的决策

**已定基线（本文后续按此展开，不再作为开放选项）**：Pool 作为 S11 的第 5 个 master，S11 只做 map/REQ/WE 合并；Pool 的低 16 位地址和 8 位写数据在 S04 内用 5×74HCT541 缓冲（4 地址 + 1 数据）+ 1×74HC32 做读 OE。这样既保持“所有 master 经 S11”的结构，又不破坏 S04 现有的 `ADDR[15:0]` 三态总线。

仍需拍板：

1. **A/B 操作数流水怎么修？**
   - **推荐方案 A（574 + 157 保持，保留现有计数器/ACC 时序）**：+2×574 + 20×157/引擎，共 +66 片；若加 573/377 符号则 +54 片。最容易一次成功。
   - 方案 B（8 级 FIFO）：芯片少，但必须重写 KX/地址/ACC 时序，风险高，只在 A4 确认能重写时选。

2. **LUT 用 8 片共享还是 24 片独立？**
   - **推荐 24 片独立**：每引擎 8 片，和 4 条 lane 一一对应，首版调试最简单；BOM 大但符合“不压缩数量”。
   - 8 片共享：BOM 小，但需要 lane/engine 选择 mux，时序更复杂，建议后续降本再评估。

> A1（顶层）、A2/A3/A3b（Pool 总线）已按基线定义，可以直接发；A4/A5/A6 建议先拍板 A/B 与 LUT 方案再发。

---

## 10. 最小可运行顺序

如果目标是“先让系统跑起来”，按以下顺序：

1. **A2 S05 端口** + **A3 S11 Pool master** + **A3b S04 缓冲**：先让 POOL1/POOL2 能读写。
2. **A4 A/B 分流**：让乘加结果正确。
3. **A5 本地 FSM ROM**：让引擎会动。
4. **A1 顶层连线/ERC**：把所有 global label 接起来。
5. **A7 验证**：先跑 Pool/引擎数值测试，再跑端到端。
6. **A6 LUT 展开**：最后做 PCB 前物理展开。

---

**结论**：顶层连线不是“画几根线”，而是“统一 100 多个 global label 的名字、方向和驱动权”。本方案已经把网络名、源/目的、有效电平、Pool 新端口、S11 新 map、A/B 修复选项和 agent 工包拆开；按第 7 节发任务即可。


---

## 11. 可直接复制的 Agent 提示词

> 建议每个 agent 在独立工作副本/分支中修改，完成后由主进程统一合并；不要直接改备份目录。

### A1 顶层集成 Agent

```text
你在 D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System 工作。
只做顶层集成，不改模块内部。依据 docs/INTERCONNECT_PLAN.md 第 3 节和
output/interconnect/interconnect_plan.csv：
1. 检查 CNN_74xx_System.kicad_sch 是否实例化 S01/S02/S04–S13/S15/S17 共 14 张子图。
2. 检查每张子图的跨模块信号是否为同名 global_label；缺的补，重复驱动的拆。
3. 不改任何模块的 FSM、数据通路、BOM。
4. 跑 tools/renumber_refs.py、tools/strip_pwr_flags.py、tools/build_top.py、
   tools/export_review.py --no-preview、sim/run_all.py。
5. 交付：顶层 ERC 0 error；output/top.net 中除 TP_* 外无单节点模块边界网；
   一份 output/integration/TOP_REPORT.md，列出每个网络的源/目的/节点数。
禁止：改 S05/S07/S08/S09 内部；用 local_label 代替 global_label；短接输出。
```

### A2+A3+A3b S05/S11/S04 Pool 总线 Agent

```text
你在 D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System 工作。
任务：让 POOL1/POOL2 能通过 S11/S04 访问存储。依据 docs/INTERCONNECT_PLAN.md
6.1/6.2/6.2b。
S05：
- 新增输出 POOL_MEM_REQ、POOL_MEM_WE、POOL_MEM_nCE_IN、POOL_MEM_nCE_OUT、POOL_BUSY_N（5 个）。
- 新增输入 MEM_ACK、MEM_DONE；读状态等 MEM_ACK 锁存 IN_DATA，等 MEM_DONE 撤 REQ；
  写状态等 MEM_DONE 撤 REQ。不能按固定节拍假设数据已到。
- 复用现有 U39（74HCT541）空闲 Y3..Y6 输出前 4 个控制；POOL_BUSY_N 用现有
  U40（74HC02）空闲门反相（5=BUSY_I, 6=GND, 4=POOL_BUSY_N）。BOM 不变。
- 保留 IN_ADDR[12:0]、OUT_ADDR[11:0]、OUT_DATA[7:0] 为 global_label。
- REQ 只在实际读/写事务状态有效，不能等于整个 POOL_BUSY。
- 读状态拉低 nCE_IN，写状态拉低 nCE_OUT；两者不能同时低。
S11：
- master 编码增加 POOL=5（POOL_BUSY_N 接现有 74HC148 的空闲 I2，不新增 148）；
  map ROM 地址只增加 A8=POOL_SEL，现有 A0..A7 不动，数据仍为 MEM_SEL[4:0]。
- 新增 1×74HC157 第三级 region mux：S=POOL_BUSY，I0=现有 REGION，
  I1={1'b0,POOL_MEM_nCE_IN,1'b0}（IN→REGION=0，OUT→REGION=2）；S11 BOM +1 片。
- Pool map：P1 IN=1/OUT=2，P2 IN=3/OUT=4，其他 region=31。
- POOL_MEM_REQ/WE 并入 REQ/WE。
- 不要在 S11 里搬 Pool 低 16 位地址/写数据。
S04：
- 读地址缓冲 2×74HCT541：{3'b0,POOL_IN_ADDR}->ADDR[15:0]，
  OE=POOL_BUSY_N | POOL_MEM_WE（Pool 忙且非写时使能，防止 ADDR 浮空）。
- 写地址缓冲 2×74HCT541：{4'b0,POOL_OUT_ADDR}->ADDR[15:0]，
  OE=POOL_MEM_nCE_OUT。
- 写数据 1×74HCT541：POOL_OUT_DATA->DATA[7:0]，
  OE=POOL_MEM_nCE_OUT。
- 读/写地址 OE 互斥；Pool 空闲时读缓冲关闭。
验收：
- 顶层网表 Pool 地址/数据/控制均 >=2 节点；
- nCE_IN/nCE_OUT 不同时低；DATA 同时只有一个驱动；
- Pool 读/写地址 OE 互斥，且不与 S10/C1/C2/FC/Argmax 冲突；
- 跑 tools/gen_bus_map.py、tools/build_bus.py、tools/build_memories.py、
  tools/build_pool.py、build_top、export_review、sim/run_all.py；
  交付 output/integration/POOL_BUS_REPORT.md。
禁止：改 S07/S08/S09 内部；改 S04 存储窗口编号；用总线短接。
```

### A4+A5 引擎 A/B 与本地 FSM Agent

```text
你在 D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System 工作。
任务：修 S07/S08/S09 的 A/B 操作数同源，并生成本地 FSM 微码。
依据 docs/INTERCONNECT_PLAN.md 6.3/6.4 和 docs/REPORT_Conv_FC.md。
A/B：
- 当前有两个问题：A_ST/B_ST 都从 DATA[7:0] 进（LUT 算 x*x）；
  8×574 的 Cp 直接接 CLK，S02 读等待 3 拍期间流水线继续移位，操作数会错位。
- 推荐方案 A：A/B 前各加 1×574 输入锁存 + 4×157 保持 mux；
  8 级流水线每级加 2:1 保持 mux（16×157/引擎）；共 +2×574 + 20×157/引擎；
  FSM 读 A→A_LOAD，读 B→B_LOAD，SHIFT_EN 一次；
  MAC_EN/ACC_LD 保持现有“每 MAC 一次、每 4 MAC 累加”的时序。
- CONV1 的 25 MAC 也要 padding 到 28（kx=5,6 权重为 0，OC 步长 25→28），否则第 7 组有 stale lane。
- 若选方案 B（8 级 FIFO）：必须同时改 KX/地址/ACC 时序，并加保持 mux；
  不能只改接线；CONV1 还要 padding 到 28。
FSM：
- 为 CONV1/CONV2/FC 各生成 ROM1/ROM2 27C512 镜像（64K×8）。
- 方案 A 增加 S_READ_A/S_READ_B/S_SHIFT 三个状态，A_LOAD/B_LOAD/SHIFT_EN
  由 74HC138 状态译码 + 少量门产生，不占 ROM2 数据位。
- 地址 {IMAGE_LAST,REQ_DONE,MEM_ACK,POINT_LAST,START_S,ST[4:0]}；
  数据位按 docs/INTERCONNECT_PLAN.md 6.4。
验收：
- 已知 3×3/5×5 输入/权重逐 MAC 比对，PROD=A*B；
- 4 lane 边界 + CONV1 padding 后的 7 组边界；
- 每个 FSM 状态/条件分支测试；
- 跑 sim/gen_engine_tb.py、sim/run_all.py；交付 output/integration/ENGINE_REPORT.md。
禁止：只改地址/计数器而不改数据通路；用 x*x 结果冒充通过。
```

### A6 LUT 展开 Agent

```text
你在 D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System 工作。
任务：把 12 个 LUT_Mult_Unit 块符号展开成 27C512 物理封装。
依据 docs/INTERCONNECT_PLAN.md 6.5、docs/REQUANT_LUT_EXPANSION_PLAN.md。
- 首版推荐每引擎 8 片、共 24 片（4 lane × 低/高字节），与现有 LUT 块一一对应；
- 或 4 lane 共享 8 片、三引擎分时复用；二选一并在报告中说明。
- 补地址/数据缓冲、lane 选择、LUT_CE_N/OE_N、100 nF 去耦、未用地址下拉。
验收：BOM 不再有 LUT_Mult_Unit；S07/S08/S09 的 LUT 接口与 S_LUT_Mult_1 一致；
      ERC 0 error；交付 output/integration/LUT_REPORT.md。
```

### A7 集成验证 Agent

```text
你在 D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System 工作。
任务：在 A1–A6 合并后做回归，不改原理图。
1. 跑 tools/export_review.py --no-preview、sim/run_all.py。
2. 解析 output/top.net：除 TP_* 外无单节点模块边界网；DATA 单驱动；
   POOL nCE 不同时低；S11 Pool map 4 行正确。
3. 跑 28×28 端到端数值测试（若模型未就绪，先跑 16×16 替代并标注）。
4. 更新 docs/FINAL_STATUS.md、docs/INTERCONNECT_PLAN.md 的验收结果。
交付：output/integration/FINAL_VERIFY.md，含命令、日志、失败项和证据。
禁止：为了让测试通过而改 golden 或删检查。
```

### A8 文档/PDF Agent

```text
你在 D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System 工作。
任务：A7 通过后更新文档和 PDF。
- 更新 docs/FINAL_STATUS.md、docs/HW_MANUAL.md、docs/INTEGRATION_NOTES.md 的
  DIP/BOM/ERC/网络数；把本文件的“验收结果”补上。
- 重新生成 output/pdf/CNN_74xx_System.pdf、HW_MANUAL.pdf、
  CNN_74xx_Review_Package.pdf、CNN_74xx_System_Review_Guide.pdf。
- 交付：output/integration/DOC_REPORT.md，列出改动的文件、页数、BOM/ERC 数。
禁止：改原理图；改测试 golden；删失败记录。
```


---

## 9. 实施结果（2026-11-07）

本方案已由主进程直接实施，未使用隔离子代理合并流程。

### 9.1 Pool 总线（A2/A3/A3b）

- S05：补齐 `POOL_MEM_REQ/WE`、`POOL_MEM_nCE_IN/OUT`、`POOL_BUSY_N`；
  读事务等 `MEM_ACK`、写事务等 `MEM_DONE`；S05 45 片。
- S11：Pool 为 master 5；map ROM `A8=POOL_SEL`；新增 U13 74HC157
  第三级 region mux；REQ/WE 合并；S11 14 片。
- S04：2×74HCT541 读地址、2×74HCT541 写地址、1×74HCT541 写数据、
  1×74HC32 读 OE；S04 56 片。
- 验证：`sim/pool` PASS；顶层 ERC 0 error。

### 9.2 A/B 分流与本地 FSM（A4/A5）

- S07/S08/S09 全部改为 A_LAT/B_LAT + 4 级保持流水线 + 13 状态 FSM。
- CONV1 25→28 padding；CONV2 72、FC1 400、FC2 32 均为 4 的倍数。
- 微码镜像已生成：`model/microcode/{c1,c2,fc}_rom{1,2}.bin`。
- 验证：`sim/harness_ab_path.py` 81 结构检查 + 行为模型 PASS；
  `sim/conv_fc_engines` 地址序列 PASS。

### 9.3 LUT 展开（A6）

- 选择“每引擎 8 片、共 24 片独立 27C512”；地址 `A[15:8]=A`、`A[7:0]=B`。
- BOM 中 `LUT_Mult_Unit` = 0；S04 原 8 片共享 LUT ROM 保留为备用。
- 验证：`sim/lut_contents`（65536 项 errors=0）、`sim/lut_spice` PASS。

### 9.4 集成结果（A7/A8）

| 项目 | 结果 |
|---|---|
| 顶层 ERC | 0 errors / 1041 warnings |
| `sim/run_all.py` | 12/12 PASS |
| BOM | 1060 件 / 681 DIP / 0 块符号 / 40 片 2x20P 背板排针 |
| S07/S08/S09 DIP | 143 / 144 / 132 |
| S04/S05/S11 DIP | 56 / 45 / 14 |
| 未展开总线 | 0 |
| 单节点模块网 | `ARGMAX_RESULT_VALID`（测试点）、`OUT_WE`（预留） |

### 9.5 未关闭项

- FC2 四字节写回：S17 的 `FC_REQ_QSTB` 是 4 拍电平，S09 只有 1 个
  OUTHOLD 字节寄存器；需要 4×574 暂存 + 4 个写状态，或把 S17 改成
  4 个单拍 QSTB 并在每个 QSTB 后等 S02 写完成。该项不影响 FC1/
  CONV1/CONV2/Argmax 的现有验证。
- S04 的 8 片共享 LUT ROM 目前未接入引擎；保留为备用/降本路径。

### 9.6 背板 2x20P 连接器（2026-11-07 追加）

- 14 张模块图全部增加 2x20P 背板排针，共 40 片。
- 电源脚统一：1–4 +5V、5–8 +3.3V（预留）、9–14 GND、15–40 信号。
- 每片 26 个信号脚；超过 26 个跨模块网络的板放多片：
  S01 2、S02 1、S04 6、S05 3、S06 2、S07 4、S08 4、S09 4、
  S10 3、S11 3、S12 2、S13 2、S15 2、S17 2。
- 375 个跨模块网络全部覆盖；最终引脚表：
  `output/backplane/backplane_pinout.csv`。
- 生成器：`tools/backplane.py`、`tools/gen_backplane_csv.py`。
- 顶层 ERC 0 error / 1041 warning；BOM 1060 件 / 681 DIP。
