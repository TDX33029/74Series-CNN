# S04 存储器阵列 / S10 顶层 I/O 完成报告

日期：2026-11-04  
工程：`Cache/CNN_74xx_System`  
范围：`S04_Memories.kicad_sch`、`S10_Top_IO.kicad_sch`、地址译码测试、PDF/BOM。  
未修改已有的 `S01_Supervisor.kicad_sch`、`S02_Timing.kicad_sch`、`S_LUT_Mult_1.kicad_sch` 和既有 `tools/*`。

## 1. 交付文件

| 文件 | 说明 |
|---|---|
| `S04_Memories.kicad_sch` | 27 片存储器阵列、片选译码、数据缓冲、加载/编程口、READY 锁存 |
| `S10_Top_IO.kicad_sch` | 8 MHz 时钟、复位监督、START 同步、加载口、状态缓冲/LED/测试点、电源入口 |
| `tools/build_memories.py` | S04 生成脚本（新增） |
| `tools/build_top_io.py` | S10 生成脚本（新增） |
| `sim/gen_mem_decode_tb.py` | S04 片选唯一性/地址标签测试（Python） |
| `output/sim/mem_decode.log` | 译码测试 PASS 日志 |
| `output/S04_ERC.rpt`、`output/S10_ERC.rpt` | KiCad ERC 原始报告 |
| `output/pdf/S04_Memories.pdf`、`output/pdf/S10_Top_IO.pdf` | A1 单页原理图 PDF |
| `output/S04_BOM.csv` | S04 分组 BOM（已排除 PWR_FLAG） |
| `output/S04.net`、`output/S10.net` | KiCad XML 网表（用于连线审计） |

## 2. S04 存储器阵列

### 2.1 器件与数量

| 位号 | 型号 | 数量 | 用途 |
|---|---|---:|---|
| U1–U7 | 6264 (8K×8) | 7 | INPUT、CONV1_OUT、POOL1_OUT、CONV2_OUT、POOL2_OUT、FC1_OUT、FC2_LOGITS |
| U8–U11 | 28C256 (32K×8) | 4 | 权重：CONV1、CONV2、FC1、FC2 |
| U12–U15 | 28C256 | 4 | 偏置：CONV1、CONV2、FC1、FC2 |
| U16–U19 | 28C256 | 4 | qparam：CONV1、CONV2、FC1、FC2 |
| U20–U27 | 27C512 (64K×8) | 8 | 4 对 LUT：LUT0…LUT3 的 LO/HI |
| U28–U31 | 74HC138 | 4 | MEM_SEL[2:0] 的 3-to-8 片选译码 |
| U32 | 74HC688 | 1 | ADDR[23:16] 与 MEM_SEL 的地址标签比较 |
| U33 | 74HC04 | 1 | 译码/加载/方向取反 |
| U34 | 74HC08 | 1 | DEC_EN、MEM_CE_OK 组合 |
| U35 | 74HC157 | 1 | 运行/加载模式的 nOE、nWE、DIR 选择 |
| U36、U37 | 74HC245 | 2 | 系统数据总线 / 加载数据总线缓冲 |
| U38 | 74HC74 | 1 | IMAGE_READY、MODEL_READY 置位/复位锁存 |
| U40–U43 | 74HCT541 | 4 | ADDR[23:0]、MEM_SEL、LOAD_EN/WE/OE 输入缓冲 |
| J1 | 2×12 排针 | 1 | 本地加载/编程口 |
| C1–C42 | 100 nF | 42 | 每个 IC 一只去耦 |
| R1–R10 | 10 k | 10 | MEM_SEL 上拉、LOAD_EN 下拉、加载控制上拉 |

### 2.2 独立地址空间（每片 64 KB 窗口）

`MEM_SEL[4:0]` 即器件号；器件 n 的窗口为 `0x{n:02X}0000–0x{n:02X}FFFF`，窗口内偏移为 `ADDR[15:0]`。地址线直接广播到各片，不经任何复用器。

| MEM_SEL | 位号 | 器件 | 窗口基址 | 有效容量 | 独立片选 |
|---:|---|---|---:|---:|---|
| 0 | U1 | INPUT_SRAM | 0x000000 | 8 KB | `nCS_SRAM_INPUT` |
| 1 | U2 | CONV1_OUT_SRAM | 0x010000 | 8 KB | `nCS_SRAM_C1OUT` |
| 2 | U3 | POOL1_OUT_SRAM | 0x020000 | 8 KB | `nCS_SRAM_P1OUT` |
| 3 | U4 | CONV2_OUT_SRAM | 0x030000 | 8 KB | `nCS_SRAM_C2OUT` |
| 4 | U5 | POOL2_OUT_SRAM | 0x040000 | 8 KB | `nCS_SRAM_P2OUT` |
| 5 | U6 | FC1_OUT_SRAM | 0x050000 | 8 KB | `nCS_SRAM_FC1OUT` |
| 6 | U7 | FC2_LOGITS_SRAM | 0x060000 | 8 KB | `nCS_SRAM_FC2LOG` |
| 7 | — | 未用 | — | — | — |
| 8 | U8 | W_CONV1 | 0x080000 | 32 KB | `nCS_W_CONV1` |
| 9 | U9 | W_CONV2 | 0x090000 | 32 KB | `nCS_W_CONV2` |
| 10 | U10 | W_FC1 | 0x0A0000 | 32 KB | `nCS_W_FC1` |
| 11 | U11 | W_FC2 | 0x0B0000 | 32 KB | `nCS_W_FC2` |
| 12 | U12 | B_CONV1 | 0x0C0000 | 32 KB | `nCS_B_CONV1` |
| 13 | U13 | B_CONV2 | 0x0D0000 | 32 KB | `nCS_B_CONV2` |
| 14 | U14 | B_FC1 | 0x0E0000 | 32 KB | `nCS_B_FC1` |
| 15 | U15 | B_FC2 | 0x0F0000 | 32 KB | `nCS_B_FC2` |
| 16 | U16 | Q_CONV1 | 0x100000 | 32 KB | `nCS_Q_CONV1` |
| 17 | U17 | Q_CONV2 | 0x110000 | 32 KB | `nCS_Q_CONV2` |
| 18 | U18 | Q_FC1 | 0x120000 | 32 KB | `nCS_Q_FC1` |
| 19 | U19 | Q_FC2 | 0x130000 | 32 KB | `nCS_Q_FC2` |
| 20 | U20 | LUT0_LO | 0x140000 | 64 KB | `nCS_LUT0_LO` |
| 21 | U21 | LUT0_HI | 0x150000 | 64 KB | `nCS_LUT0_HI` |
| 22 | U22 | LUT1_LO | 0x160000 | 64 KB | `nCS_LUT1_LO` |
| 23 | U23 | LUT1_HI | 0x170000 | 64 KB | `nCS_LUT1_HI` |
| 24 | U24 | LUT2_LO | 0x180000 | 64 KB | `nCS_LUT2_LO` |
| 25 | U25 | LUT2_HI | 0x190000 | 64 KB | `nCS_LUT2_HI` |
| 26 | U26 | LUT3_LO | 0x1A0000 | 64 KB | `nCS_LUT3_LO` |
| 27 | U27 | LUT3_HI | 0x1B0000 | 64 KB | `nCS_LUT3_HI` |
| 28–31 | — | 未用 | — | — | — |

### 2.3 片选译码

```
ADDR_TAG_OK = (ADDR[23:16] == {000, MEM_SEL[4:0]})       U32 74HC688 + U33C
BOTH_IDLE   = MEM_nCE AND (NOT LOAD_EN)                  U34B
MEM_CE_OK   = NOT BOTH_IDLE                              U33E
DEC_EN      = ADDR_TAG_OK AND MEM_CE_OK                  U34A
```

- U28 组 00：`MSEL4=0, MSEL3=0`，Y0–Y6 为 7 个 SRAM 片选，Y7 未用。
- U29 组 01：`MSEL4=0, MSEL3=1`，Y0–Y7 为 4 个权重 + 4 个偏置。
- U30 组 10：`MSEL4=1, MSEL3=0`，Y0–Y7 为 4 个 qparam + LUT0/LUT1。
- U31 组 11：`MSEL4=1, MSEL3=1`，Y0–Y3 为 LUT2/LUT3，Y4–Y7 未用。

四个 138 的组使能互斥，同一组内 138 输出 one-hot；DEC_EN 为低时全部片选无效。因此任意时刻最多只有一个 `nCS_*` 为低。每个 `nCS_*` 只连到一片存储器的片选引脚（网表审计：27 个片选网络均为 2 个节点）。

### 2.4 数据与加载路径

- U36（74HC245）：`MEM_D[7:0]` ↔ `DATA[7:0]`，`DIR = ~nOE_SEL`，正常运行时读为 A→B、写为 B→A。
- U37（74HC245）：`LOAD_DATA[7:0]` ↔ `MEM_D[7:0]`，`DIR = nOE_SEL`，加载时写为 A→B、回读为 B→A。
- `LOAD_EN=1` 时 U36 关闭、U37 打开；U35 把存储器 `nOE/nWE` 切换到 `LOAD_nOE/LOAD_nWE`；`DEC_EN` 同时旁路 `MEM_nCE`，允许编程器直接写 EEPROM/SRAM。
- J1 定义：`LOAD_DATA[7:0]`、`LOAD_EN`、`LOAD_nWE`、`LOAD_nOE`、`~IMAGE_DONE`、`~MODEL_DONE`、`IMAGE_READY`、`MODEL_READY`、+5V/GND。J1 与 S10 的 J5/J6 共用 `LOAD_*` 网络，二者只能任选其一使用；J1 只带数据/控制与 READY 脉冲，不带地址，本地编程时 `ADDR[23:0]`/`MEM_SEL` 由 S10 的 J5/J6 经 U93–U96 提供。
- 27C512 无在线 VPP 引脚，LUT ROM 由外部编程器/出厂编程；板上只提供读访问。

### 2.5 READY 锁存

U38A/U38B 为 D=Q 反馈的置位/复位锁存：

- `~R = RESET_N`，`~S = IMAGE_DONE_N` / `MODEL_DONE_N`，`C = CLK`，`D = Q`。
- 加载完成脉冲异步置 1，随后 CLK 边沿保持；复位清 0。
- 输出为 `IMAGE_READY`、`MODEL_READY`（同时送 S01 和 J1）。

### 2.6 电源与空闲状态

- 每片 IC 的 VCC/GND 均用电源符号连接；C1–C42 为每片 IC 一只 100 nF 去耦。
- `MEM_SEL[4:0]` 上拉 10 k 到 +5V，空闲为 `11111`（未映射，无片选）。
- `LOAD_EN` 下拉 10 k；`LOAD_nWE/LOAD_nOE`、`IMAGE_DONE_N/MODEL_DONE_N` 上拉 10 k。
- PWR_FLAG 声明 +5V/GND 已驱动。

## 3. S10 顶层 I/O

### 3.1 时钟

- X1：`Oscillator:ASE-xxxMHz`，值 `8.000MHz`，EN/Vdd 接 +5V。
- JP1 三脚选择：1-2 接内部振荡器，2-3 接 J4 外部时钟；`CLK_SEL` 有 10 k 下拉。
- U70E（74HC04）缓冲 `CLK_SEL`，R5 33 Ω 串联后产生全局 `CLK`；J4 外部时钟输入有 10 k 下拉。
- **JP1 必须始终插好**；无跳线时 CLK 被拉低而不是悬空。

### 3.2 复位监督

- R1 100 k 上拉 / C90 1 µF 到地构成上电 RC（约 70 ms）；SW1 和 J3 可强制拉低。
- U70A/U70B 两级 74HC04 整形，输出全局 `RESET_N`。
- 已知限制：74HC04 非施密特输入，慢沿时建议换 74HC14；当前 5 V/100 k/1 µF 工作点可用。

### 3.3 START

- J2 + R2 10 k 下拉产生 `START_RAW`。
- U91A/U91B（74HC74）用 CLK 做两级同步，输出 `START`；异步复位为 `RESET_N`。

### 3.4 加载/编程接口

| 连接器 | 内容 |
|---|---|
| J5（2×16，IMAGE LOAD） | H_D[7:0]、H_A[12:0]、LOAD_EN、H_LOAD_nWE/nOE、IMAGE_DONE_N、IMAGE_READY、+5V/GND |
| J6（2×20，PARAM PROG） | H_D[7:0]、H_A[14:0]、H_MEM_SEL[4:0]、LOAD_EN、H_LOAD_nWE/nOE、MODEL_DONE_N、MODEL_READY、+5V/GND |

- U92（74HCT245）：`H_D[7:0]` ↔ `LOAD_DATA[7:0]`，`DIR = LOAD_nOE`，`CE = NOT_LOAD_EN`。
- U93–U95（74HCT541×3）：`H_A[23:0]` → `ADDR[23:0]`，`G1=G2=NOT_LOAD_EN`。
- U96（74HCT541）：`H_MEM_SEL[4:0]` → `MEM_SEL[4:0]`，`H_LOAD_nWE/nOE` → `LOAD_nWE/LOAD_nOE`。
- RN1–RN3（8×10 k 排阻）：`H_A[23:0]` 下拉；`H_MEM_SEL[4:0]` 各 10 k 下拉；`H_LOAD_nWE/nOE` 上拉；`LOAD_EN` 下拉。
- 加载时系统侧地址/`MEM_SEL` 驱动器必须高阻（由 S00 复位/空闲协议保证）；S10 缓冲器本身为三态。

### 3.5 状态、LED、测试点、电源

- U97/U98（74HCT541）：缓冲 `BUSY`、`DONE`、`RESULT_VALID`、`ERROR`、`RESULT[3:0]`、`ERROR_CODE[3:0]`、`IMAGE_READY`、`MODEL_READY` 到 `ST_*`。
- J7（2×10 STATUS）：输出全部状态；D1–D7 + 470 Ω 指示 PWR/BUSY/DONE/RESULT_VALID/ERROR/IMAGE_READY/MODEL_READY。
- TP1–TP10：CLK、RESET_N、START、IMAGE_READY、MODEL_READY、BUSY、DONE、RESULT_VALID、ERROR、LOAD_EN。
- J1（2×2）为 +5V 电源入口；C91 10 µF + C92 100 nF 为 bulk，C1–C10 为每个 IC 一只 100 nF；FLG1/FLG2 为 PWR_FLAG。

## 4. 验证结果（实际命令输出）

### 4.1 ERC

```
kicad-cli sch erc S04_Memories.kicad_sch -o output/S04_ERC.rpt --severity-all
发现 86 条违规项
kicad-cli sch erc S10_Top_IO.kicad_sch -o output/S10_ERC.rpt --severity-all
发现 71 条违规项
```

| 报告 | 总计 | error | warning | 分类 |
|---|---:|---:|---:|---|
| S04 | 86 | 29 | 57 | `pin_not_driven` 29、`isolated_pin_label` 34、`lib_symbol_mismatch` 17、`lib_symbol_issues` 6 |
| S10 | 71 | 8 | 63 | `pin_not_driven` 8、`isolated_pin_label` 46、`lib_symbol_mismatch` 16、`lib_symbol_issues` 1 |

S04 的 29 个 `pin_not_driven` 全部是外部接口输入，没有内部断线：

- U38 `C/~R`：`CLK`、`RESET_N`（来自 S02/S10）
- U40–U42 的 `A0–A7`：`ADDR[23:0]`（来自引擎/加载口）
- U35 `I0a/I0b`：`MEM_nOE`、`MEM_nWE`（来自 S02）
- U34 pin4：`MEM_nCE`（来自 S02）

S10 的 8 个 `pin_not_driven` 为 U97 `A4–A7`（`RESULT[3:0]`）和 U98 `A0–A3`（`ERROR_CODE[3:0]`），均由 S01 驱动。

`isolated_pin_label` 是单页 ERC 下单引脚全局总线标签（ADDR/DATA/MEM_SEL/LOAD_DATA 等）的告警；`lib_symbol_mismatch` 为生成器内嵌符号与库缓存差异；`lib_symbol_issues` 为 74HC157/74HC08/74HCT245 由同引脚 74LS/74HC 符号派生（项目契约允许）。  
**两份报告中均不存在 `pin_to_pin`、`short`、`multiple_net_names`、`different_unit_net`、`pin_not_connected`/`unconnected` 冲突类违规**；所有未连接引脚均为显式 NC（备用门输出、`~Q`、连接器备用针，或 6264 的库定义 `no_connect` 引脚），详见 `output/S04.net`、`output/S10.net`。

### 4.2 网表审计

- S04：97 个元件（95 个实体 + 2 个 PWR_FLAG），无重复位号。
- 27 个 `nCS_*` 网络均恰好 2 个节点（138 输出 + 唯一存储器片选）。
- U1–U27 每片的 28 个引脚均已处理（连接、接电源/地或库定义/显式 NC）；6264 pin1 为库定义 `no_connect` 类型。
- U28–U31、U32、U33、U34、U35、U38 关键引脚经网表逐脚核对与设计方程一致。
- S10：76 个元件；`CLK` 4 节点、`RESET_N` 4 节点、`START` 2 节点、`NOT_LOAD_EN` 10 节点；U92/U93–U96/U97/U98 关键引脚已核对。

### 4.3 地址译码测试

```
python sim/gen_mem_decode_tb.py
checks: 323  failures: 0
RESULT: PASS
```

覆盖：

- 27 个映射器件在各自基址/窗口偏移下唯一片选；
- 全部 32 个 `MEM_SEL` 值的一热扫描（7、28–31 无片选）；
- 地址标签不匹配、`MEM_nCE=1` 空闲、`LOAD_EN=1` 加载旁路；
- 20 000 个随机输入向量，最大同时有效片选数 = 1。

日志：`output/sim/mem_decode.log`。

### 4.4 PDF / BOM

- `output/pdf/S04_Memories.pdf`：A1，1 页。
- `output/pdf/S10_Top_IO.pdf`：A1，1 页。
- `output/S04_BOM.csv`：14 个分组行，合计 95 个实体元件；已排除 PWR_FLAG。
  - 6264 ×7、28C256 ×12、27C512 ×8、74HC138 ×4、74HC688 ×1、74HC04 ×1、74HC08 ×1、74HC157 ×1、74HC245 ×2、74HC74 ×1、74HCT541 ×4、100 nF ×42、10 k ×10、2×12 排针 ×1。

## 5. 已知限制

1. **单页 ERC 的外部输入错误**：S04/S10 作为独立图纸运行时，来自 S01/S02/加载口的输入没有输出驱动，ERC 报 `pin_not_driven`。这是单页检查的预期结果；接入 S00 层次后应由上层驱动，建议集成后重跑层次 ERC。
2. **符号别名**：74HC157、74HC08 由 74LS157/74LS08 派生，74HCT245 由 74HC245 派生；位号值与 BOM 为 HC/HCT，但 ERC 报 `lib_symbol_issues`。
3. **27C512 不可在线编程**：无 VPP/PGM 引脚，LUT ROM 需外部编程器或出厂编程；J1/S10 的加载口用于 6264 图像和 28C256 参数。
4. **窗口内镜像**：每个器件占 64 KB 标签窗口，但 6264 只译 A0–A12、28C256 只译 A0–A14，因此窗口内分别每 8 KB/32 KB 出现镜像。软件必须使用文档基址和有效容量；如需严格尺寸译码，应增加按容量的高位比较器。
5. **加载期间系统侧必须高阻**：S10 的 U93–U96/U92 为三态，但引擎的地址/`MEM_SEL` 驱动器是否高阻由 S00 复位协议保证，原理图本身无法强制。
6. **J1 与 J5/J6 共用 LOAD_\***：同一时刻只能使用一个加载口；J1 只带数据/控制/READY，不带地址。若需完全独立的单板编程器，应把 J1 扩展到 2×20 并加入 A0–A15。
7. **复位使用 74HC04 而非 74HC14**：RC 慢沿下建议改用施密特输入；当前约 70 ms 上电复位可用。
8. **S10 只监视 READY**：`IMAGE_READY`/`MODEL_READY` 由 S04 的 U38 产生，S10 仅缓冲到状态口/LED/测试点，不重复驱动。
9. **S00 未改动**：本次按任务范围只新增 S04/S10 独立图纸，未把两张图加入根层次图。
10. **BOM 不含 PWR_FLAG**：PWR_FLAG 为 ERC 辅助符号，非实体元件；S10 未要求导出 BOM。
11. **电源保护/时序未包含**：J1 为 5 V 入口，未加保险丝、反接保护或上电时序电路。

## 6. 复现命令

```bash
cd Cache/CNN_74xx_System

# 生成图纸
python tools/build_memories.py
python tools/build_top_io.py

# 地址译码测试（PASS 日志）
python sim/gen_mem_decode_tb.py

# ERC
kicad-cli sch erc S04_Memories.kicad_sch -o output/S04_ERC.rpt --severity-all
kicad-cli sch erc S10_Top_IO.kicad_sch -o output/S10_ERC.rpt --severity-all

# 网表
kicad-cli sch export netlist --format kicadxml S04_Memories.kicad_sch -o output/S04.net
kicad-cli sch export netlist --format kicadxml S10_Top_IO.kicad_sch -o output/S10.net

# PDF
kicad-cli sch export pdf S04_Memories.kicad_sch -o output/pdf/S04_Memories.pdf
kicad-cli sch export pdf S10_Top_IO.kicad_sch -o output/pdf/S10_Top_IO.pdf

# BOM（原始分组），随后删除 FLG1/FLG2 两行得到 output/S04_BOM.csv
kicad-cli sch export bom S04_Memories.kicad_sch -o output/S04_BOM_raw.csv \
  --fields "Reference,Value,Footprint,QUANTITY,DNP" \
  --labels "Refs,Value,Footprint,Qty,DNP" \
  --group-by "Value,Footprint"
```

## 7. 结论

- S04 的 7×6264、4+4+4×28C256、8×27C512（四对）及 74HC138/688/245 译码与数据缓冲全部完成并逐脚接线。
- S10 的时钟、复位、START、加载/编程口、状态输出、LED、测试点和电源去耦全部完成。
- 地址译码测试 **PASS**（323 检查、0 失败、20 000 随机向量最大 1 个片选）。
- ERC 无重复驱动/短路/悬空输出类违规；存在的 29/8 个 error 均为单页检查下的外部输入未驱动，已记录。
- PDF、BOM、网表和测试日志均已生成并可复现。
