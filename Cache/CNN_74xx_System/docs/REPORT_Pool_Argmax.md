# POOL / ARGMAX 模块交付报告

日期：2026-11-04  
工程：`D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System`  
范围：S05_Pool、S06_Argmax 原理图、ERC、SPICE 功能仿真、PDF。

## 1. 交付文件

| 类型 | 路径 |
|---|---|
| POOL 原理图 | `S05_Pool.kicad_sch` |
| POOL 生成脚本 | `tools/build_pool.py` |
| POOL ERC | `output/s05-erc.rpt` |
| POOL PDF | `output/pdf/S05_Pool.pdf` |
| POOL 网表 | `output/S05_Pool.net` |
| POOL 仿真脚本 | `sim/gen_pool_tb.py` |
| POOL SPICE 网表 | `sim/tb_pool.cir` |
| POOL 仿真日志 | `output/sim/pool.log` |
| POOL 波形数据 | `output/sim/pool_wave.txt` |
| ARGMAX 原理图 | `S06_Argmax.kicad_sch` |
| ARGMAX 生成脚本 | `tools/build_argmax.py` |
| ARGMAX ERC | `output/s06-erc.rpt` |
| ARGMAX PDF | `output/pdf/S06_Argmax.pdf` |
| ARGMAX 网表 | `output/S06_Argmax.net` |
| ARGMAX 仿真脚本 | `sim/gen_argmax_tb.py` |
| ARGMAX SPICE 网表 | `sim/tb_argmax.cir` |
| ARGMAX 仿真日志 | `output/sim/argmax.log` |
| ARGMAX 波形数据 | `output/sim/argmax_wave.txt` |
| 本报告 | `docs/REPORT_Pool_Argmax.md` |

未修改 `S01_Supervisor.kicad_sch`、`S02_Timing.kicad_sch`、`S_LUT_Mult_1.kicad_sch` 及已有 `tools/*`。

## 2. S05_Pool 设计摘要

- 功能：2×2 窗口、stride 2、uint8 无符号最大值，覆盖 POOL1/POOL2，由 `POOL_SEL` 选择。
- POOL1：C=8, H=24, W=24 → 12×12×8 = 1152 输出，输入 4608 字节（13 位地址）。
- POOL2：C=16, H=10, W=10 → 5×5×16 = 400 输出，输入 1600 字节。
- 接口（全局标签）：`CLK`、`RESET_N`、`START`、`POOL_SEL`、`IN_DATA[7:0]`、`IN_ADDR[12:0]`、`OUT_DATA[7:0]`、`OUT_ADDR[11:0]`、`OUT_WE`、`BUSY`、`DONE`。
- 四值读取顺序：`v0=(2oy,2ox)`、`v1=(2oy,2ox+1)`、`v2=(2oy+1,2ox)`、`v3=(2oy+1,2ox+1)`。
- 线性窗口基地址：`WB = c*H*W + 2*oy*W + 2*ox`；v0..v3 分别加 `0,1,W,W+1`。
- 列步进 +2；由于 `H=2*OH`、`W=2*OW`，行步进与通道步进都等于 `W+2`（POOL1=26，POOL2=12）。该规则已标注在图纸上。
- MAX 规则：INIT 清 MAX；每个窗口第一个值（V=0）强制装载 v0，v1..v3 仅在 `IN_DATA > MAX` 时更新（74HC85 级联，严格大于）。相等值保持当前 MAX；0/255 边界由 8 位无符号比较覆盖。
- 器件：74HC161×4（ox/oy/c/v）、74HC688×3（末索引比较）、74HC85×2（8 位无符号比较）、74HCT273×3（MAX 8 位 + WB 13/16 位）、74HCT574×1（输出寄存器）、74HC157×2（MAX 更新选择）、74HC283×8（WB 增量与读地址加法）、74HC161×3（OUT_ADDR）、74HCT273×1（8 状态 one-hot FSM）、74HC74×1（RUN）、74HC02×1（IDLE = NOR(RUN,S_WAIT)）、74HC04/08/32 胶合逻辑、74HCT541×1（OUT_WE/DONE/BUSY 缓冲）。
- 输出地址采用顺序 12 位计数器；OUT_WE 在 NEXT 状态有效，OUT_DATA 已在前一 OUTLD 状态锁存。
- 所有 IC 引脚均接短线+网络标签、+5V/GND 电源符号或显式 NC；内部网络用局部标签，模块接口用全局标签。

## 3. S06_Argmax 设计摘要

- 功能：读 10 个 signed32 little-endian 分数；class0 初始化 MAX；class1..9 有符号比较；严格大于才更新 MAX/INDEX（并列取小编号）；输出 4 位类别。
- 接口：`CLK`、`RESET_N`、`START`、`SCORE_DATA[31:0]`、`SCORE_ADDR[5:0]`、`SCORE_RD`、`RESULT[3:0]`、`RESULT_VALID`、`BUSY`、`DONE`。
- 有符号比较：将 SCORE 和 MAX 的最高位分别取反，转为 offset-binary，再用 8×74HC85 从低 nibble 到高 nibble 级联比较；`Oa>b` 为严格大于。并列时 GT=0，MAX/INDEX 不更新，因此保留小编号。
- 读序列：`INIT → RD0(addr=0) → WT0 → LD0(装载 score0/INDEX=0) → NEXT(class=1) → {RD → WT → CMP → NEXT}×9 → DONE → WAIT → IDLE`。74HC688 检测 class=9；`EQ9_N` 用于 NEXT→RD，`EQ9` 用于 NEXT→DONE。
- 器件：74HC161×1（class）、74HC688×1（class==9）、74HCT574×9（32 位 SCORE、32 位 MAX、4 位 INDEX）、74HC85×8（32 位有符号比较）、74HC157×9（32 位 MAX 更新 + 4 位 INDEX 更新）、74HCT273×2（10 状态 FSM）、74HC74×1（RUN）、74HC04/08/32 胶合逻辑、74HCT541×1（SCORE_ADDR[5:0]/DONE/BUSY 缓冲）。
- `RESULT_VALID = DONE | WAIT`，在下次 START 之前保持；`BUSY = RUN & ~DONE`；`SCORE_RD` 在 RD0/WT0/RD/WT 为高。
- 所有引脚均接线、接电源/地或显式 NC；内部网络局部标签，模块接口全局标签。

## 4. ERC 结果（kicad-cli 10.0.4）

命令：

```bat
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc --severity-all --output output/s05-erc.rpt S05_Pool.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc --severity-all --output output/s06-erc.rpt S06_Argmax.kicad_sch
```

### S05_Pool

| 项目 | 数量 | 说明 |
|---|---:|---|
| error 合计 | 12 | 全部为 `pin_not_driven` |
| warning 合计 | 127 | 见下 |
| `pin_not_driven` | 12 | 外部输入未驱动：`CLK`、`RESET_N`、`START`、`POOL_SEL`、`IN_DATA0..7`（每个网络报 1 处） |
| `isolated_pin_label` | 37 | 单页模块边界的全局标签（外部输入/输出） |
| `lib_symbol_issues` | 57 | 74HC161/283/157/08/32/HCT541/HCT574 别名不在原库中 |
| `lib_symbol_mismatch` | 33 | 派生/别名符号与库内符号的图形差异 |

### S06_Argmax

| 项目 | 数量 | 说明 |
|---|---:|---|
| error 合计 | 35 | 全部为 `pin_not_driven` |
| warning 合计 | 108 | 见下 |
| `pin_not_driven` | 35 | 外部输入未驱动：`CLK`、`RESET_N`、`START`、`SCORE_DATA0..31`（每个网络报 1 处） |
| `isolated_pin_label` | 42 | 单页模块边界的全局标签 |
| `lib_symbol_issues` | 35 | 别名符号库警告 |
| `lib_symbol_mismatch` | 31 | 派生/别名符号图形差异 |

结论：

- 两张图均**没有**重复驱动、输出短路、输出悬空、`pin_not_connected`、`conflicting_outputs` 等错误；所有非边界网络至少有 2 个引脚连接。
- 12/35 个 `pin_not_driven` 都是单页交付时的外部输入（顶层尚未连接），按任务约定可接受并在此记录；顶层 S00/S10 集成时由外部驱动即可消除。
- `isolated_pin_label` 是单页模块的全局接口标签（每个网络在本页只有 1 个引脚），属于正常边界现象。
- 别名符号警告与已有 S01/S02 的生成方式一致；不影响力网表连接。若后续要求零 warning，可把别名改成库内 74LS 符号、Value 仍标 74HC。

## 5. SPICE 功能仿真

使用 `tools/ngspice_runner.py` 驱动 KiCad 自带 `ngspice.dll`；XSPICE `d_dff` 建模寄存器，B 源用 C 三元表达式实现组合逻辑；`wrdata` 每向量写 `(time,value)` 两列，采样点在时钟上升沿后 30 ns（80 ns + n×100 ns），避免状态位偏斜毛刺。

### POOL

命令：`cd sim && python gen_pool_tb.py`  
结果：**PASS**（退出码 0）  
日志：`output/sim/pool.log`

覆盖内容：

- 10 个连续窗口，最大值位置轮换：位置 1、3、0、2 均出现。
- 相等值窗口 `[7,7,7,7]` → 7。
- 0 边界 `[0,0,0,0]` → 0。
- 255 边界：`[255,0,0,0]`、`[0,255,0,0]`、`[0,0,255,0]`、`[0,0,0,255]` → 255。
- 40 次读地址检查：每个窗口 `2n, 2n+1, 2n+24, 2n+25`（W=24）。
- 状态序列包含 IDLE→INIT→{RD→WT→CP}×4→OUTLD→NEXT→DONE→WAIT→IDLE，RUN/IDLE 行为正确。
- 日志关键行：

```
addr_ok=True rd_checks=40 max_ok=True init_clear=True done_seen=True seq_ok=True v_ok=True
PASS: POOL 2x2 max, 4-value order, 0/255 and equal-value coverage
```

### ARGMAX

命令：`cd sim && python gen_argmax_tb.py`  
结果：**PASS**（退出码 0）  
日志：`output/sim/argmax.log`

5 个测试向量：

| 向量 | 分数特征 | 期望结果 | 期望 MAX |
|---|---|---:|---:|
| 0 | 正负混合，最大值在首位 class0 | 0 | 100 |
| 1 | 含 -2^31 与 2^31-1，最大值在末位 class9 | 9 | 2147483647 |
| 2 | 10 个分数全相等 | 0 | 5 |
| 3 | class2/5/7 并列最大，取小编号 | 2 | 12345 |
| 4 | 全负，含 -2^31，最大值在 class4 | 4 | -1 |

日志关键行：

```
test 0: result=0 max=100 expected_result=0 expected_max=100 valid=True
test 1: result=9 max=2147483647 expected_result=9 expected_max=2147483647 valid=True
test 2: result=0 max=5 expected_result=0 expected_max=5 valid=True
test 3: result=2 max=12345 expected_result=2 expected_max=12345 valid=True
test 4: result=4 max=-1 expected_result=4 expected_max=-1 valid=True
result_ok=True cmp_ok=True addr_ok=True srd_ok=True seq_ok=True
PASS: ARGMAX signed32, ties, first/last and -2^31/2^31-1 boundaries
```

说明：32 位分数在测试平台中以 4 个 8 位字节常量给出，位级比较链直接按“翻转最高位后从 MSB 到 LSB”实现，避免在模拟节点里用 float32 表示 2^31 级整数造成精度损失；这与硬件的 74HC85 级联完全对应。

## 6. PDF / 网表

```bat
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export pdf --output output/pdf/S05_Pool.pdf S05_Pool.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export pdf --output output/pdf/S06_Argmax.pdf S06_Argmax.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export netlist --output output/S05_Pool.net S05_Pool.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export netlist --output output/S06_Argmax.net S06_Argmax.kicad_sch
```

- `output/pdf/S05_Pool.pdf`：A1，1 页，600 439 字节（2026-11-04 12:01）。
- `output/pdf/S06_Argmax.pdf`：A1，1 页，578 522 字节（2026-11-04 12:01）。
- 网表导出成功；单节点网络仅为模块边界输出/输入或显式 `unconnected-(...)` NC，无内部悬空网络。

## 7. 已知限制与说明

1. **单页 ERC 的外部输入**：S05 的 `CLK/RESET_N/START/POOL_SEL/IN_DATA0..7` 和 S06 的 `CLK/RESET_N/START/SCORE_DATA0..31` 在本页无驱动源，表现为 12/35 个 `pin_not_driven`。这是单页交付的预期现象，顶层 S00/S10 连接后消除；没有重复驱动/短路/输出悬空。
2. **别名符号 warning**：74HC161/283/157/08/32、74HCT541/574 使用与 74LS 同引脚的派生符号（契约允许），因此 ERC 报 `lib_symbol_issues`/`lib_symbol_mismatch`；不影响网表。
3. **SPICE 建模层级**：仿真在寄存器/功能级验证状态机、地址序列、比较规则和边界值，不代表晶体管级延时、扇出、建立/保持或存储器模拟时序。POOL 的读接口假设 S02 时序控制器提供 2 个等待周期的读；实际 `nCE/nOE` 由 S02/存储器接口产生。`IN_RD` 仅引到测试点 TP1，不在模块接口中。
4. **ARGMAX 数据总线**：本图采用 32 位并行 `SCORE_DATA[31:0]`；若顶层存储器为字节宽，需要在 S04/S10 做 4 字节拼装（little-endian）。`SCORE_RD` 为高有效。
5. **未集成到根图**：S05/S06 目前是独立图纸，未插入 `CNN_74xx_System.kicad_sch` 根图；全局网络名遵循契约，便于后续 S00 集成。
6. **POOL 单引擎复用**：POOL1/POOL2 共用本引擎，`POOL_SEL` 在一次运行期间必须稳定；POOL1/POOL2 的末索引常数由 `POOL_SEL` 选择。
7. **去耦**：图底部按每个 IC 封装画了 1 个 100 nF 去耦电容（S05 C1..C40，S06 C1..C38），仅作原理图表示，未做 PCB 布局/电源完整性分析。
8. **PDF 排版**：多单元门电路的 Reference/Value 文本在 A1 缩略图下较密，放大 PDF 可读；不影响网表与 ERC。

## 8. 复现命令

```bat
cd D:\Document\tempPrj\74Series-CNN\Cache\CNN_74xx_System\tools
python build_pool.py
python build_argmax.py

cd ..
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc --severity-all --output output/s05-erc.rpt S05_Pool.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch erc --severity-all --output output/s06-erc.rpt S06_Argmax.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export pdf --output output/pdf/S05_Pool.pdf S05_Pool.kicad_sch
"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export pdf --output output/pdf/S06_Argmax.pdf S06_Argmax.kicad_sch

cd sim
python gen_pool_tb.py
python gen_argmax_tb.py
```

## 9. 要求对照

| 要求 | 状态 |
|---|---|
| 真实 74 系列符号、短线+网络标签、每引脚连接/电源/NC | 已完成 |
| 复用 snap/网格；内部局部标签、跨模块全局标签 | 已完成 |
| 图面标题、接口说明、循环/比较规则说明 | 已完成 |
| kicad-cli ERC；记录外部输入；无重复驱动/短路/悬空输出 | 已完成（外部输入 12/35 条已记录；无其他错误） |
| SPICE 使用 ngspice_runner；d_dff；三元 B 源；wrdata 成对；沿后 30 ns 采样 | 已完成 |
| POOL 覆盖 ≥4 窗口、四位置轮换、相等值、0/255 | 已完成（10 窗口） |
| ARGMAX 覆盖正负、首/尾最大、并列、-2^31/2^31-1 | 已完成（5 向量） |
| PASS/FAIL 日志 | 已输出，两个模块均 PASS |
| PDF → output/pdf、ERC → output、仿真日志 → output/sim、报告 → docs | 已完成 |
| 不修改已有 S01/S02/S_LUT 与 tools/* | 已遵守 |
