# S12 数据拼装修复报告（M-07 的 40 个数据输入）

日期：2026-11-05  
主工程：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System`  
目标：把 Pool 的 `IN_DATA[7:0]` 接到 S04 `DATA[7:0]`，为 Argmax 的 `SCORE_DATA[31:0]` 增加 4×74HCT574 + 地址译码，消除剩余 40 个顶层 ERC error。

## 0. 结论

| 项目 | 结果 |
|---|---|
| 新增 S12_DataAssembly | 1×74HCT541、4×74HCT574、1×74HC238 + 6 去耦 + 4 测试点 |
| Pool 输入 | `DATA[7:0]` → 74HCT541 → `IN_DATA[7:0]` |
| Argmax 输入 | 4×74HCT574 字节锁存 → `SCORE_DATA[31:0]`；74HC238 用 `SCORE_ADDR[1:0]`/`SCORE_RD` 产生 4 个锁存时钟 |
| 顶层 ERC | 40 errors → **0 errors / 799 warnings** |
| 网表审计 | 4 单节点模块网 / 21 未展开总线 / 1 个 DONE 驱动（不变） |
| 仿真 | `sim/run_all.py` **9/9 PASS** |
| 布局 harness | **PASS，0 failures** |
| BOM | 917 → **933**（517 片 IC + 15 个块符号 + 无源件/连接器/测试点） |
| 主工程 | 已应用 |

## 1. 设计

### 1.1 Pool 输入缓冲

- U13001 74HCT541：`A[7:0]=DATA[7:0]`，`Y[7:0]=IN_DATA[7:0]`，`G1=G2=GND`（常开）。
- 输入缓冲只读取共享 `DATA` 总线，不会驱动它；Pool 只在 `IN_RD` 窗口使用 `IN_DATA`。

### 1.2 Argmax 32 位拼装

- U13002–U13005 74HCT574：四片并联，`D[7:0]=DATA[7:0]`，`OE=GND`；
  `Q[7:0]` 分别接 `SCORE_DATA[7:0]`、`[15:8]`、`[23:16]`、`[31:24]`。
- U13006 74HC238：`A0=SCORE_ADDR0`、`A1=SCORE_ADDR1`、`~E1=~E2=GND`、`E3=SCORE_RD`；
  `Y0..Y3` 接四个 `Cp`，`Y4..Y7` 明确 NC。
- 这样 `SCORE_DATA[31:0]` 每个位都有唯一的锁存器输出驱动，`SCORE_RD` 也有了真实负载。

## 2. 修改文件

| 文件 | 修改 |
|---|---|
| `tools/build_s12.py` | 新增 S12 生成器 |
| `S12_DataAssembly.kicad_sch` | 新增原理图 |
| `CNN_74xx_System.kicad_sch` | 增加 S12 层次页（page 12） |
| `tools/build_top.py` | SHEETS、模块表、net_hints、评审注记位置、数据流表 |
| `tools/export_review.py` | 导出/ERC/PDF 列表加入 S12 |
| `tools/build_review_pdf.py` | 评审包加入 S12 图 |
| `tools/strip_pwr_flags.py`、`tools/renumber_refs.py` | S12 纳入去耦/位号块（13000） |
| `docs/*.md`、`output/model_reviews/*.md` | 计数、状态和边界说明同步 |

## 3. 验证

```text
kicad-cli sch export netlist --format kicadsexpr -o output/top.net CNN_74xx_System.kicad_sch
python tools/audit_top_connectivity.py output/top.net
kicad-cli sch erc --severity-all -o output/top-erc-s12.rpt CNN_74xx_System.kicad_sch
python sim/run_all.py
python output/model_reviews/muse-slot-session-model/harness_datapath_layout.py
```

关键节点（`output/top.net`）：

| 网络 | 节点 |
|---|---|
| `IN_DATA0` | `U13001.18`（541 输出）+ `U5012.10` |
| `SCORE_DATA0` | `U13002.19`（574 Q0）+ `U6004.2` |
| `SCORE_DATA31` | `U13005.12`（574 Q7）+ `U6007.9` |
| `SCORE_RD` | `U13006.6`（74HC238 E3） |

## 4. 后续闭环（已完成）

S12 最初只完成数据宽度/寄存；随后 S06 增加 2 位字节计数器并把 `SCORE_ADDR` 改为 `{class,byte}`，S04 增加 Argmax 地址缓冲，S11 增加 Argmax master，S12 的锁存使能改为 `MEM_ACK`。四字节 REQ/ACK 事务已闭环，详见 `repair_argmax4/REPAIR_REPORT.md`。

## 5. 未完成

- S06/S04 的 Argmax 四字节事务闭环（字节计数、地址拼接、REQ/ACK）。
- Requant 门级展开（M-05/M-09）、LUT 物理 lane 映射（M-08）、10–100 Hz 时序重算（M-10）、BOM 封装（M-11）、S02 未用译码输出（M-13）。
