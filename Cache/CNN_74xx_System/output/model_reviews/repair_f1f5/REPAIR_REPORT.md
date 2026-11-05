# F1/F5 原型修复报告（隔离副本验证）

日期：2026-11-05
隔离副本：`D:/Document/tempPrj/74Series-CNN/Cache/_repair_f1f5/work`
主工程：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System`（未写入）
备份：`D:/Document/tempPrj/74Series-CNN/Cache/_backup_CNN_74xx_System_20261105`（未写入）

## 0. 结论

| 项目 | 结果 |
|---|---|
| F1 阶段启动脉冲 | 已接通：`P1_START`/`P2_START` -> S05 U42 或门 -> 页内 `POOL_START`；`ARGMAX_START` -> S06 启动门 |
| F5 DONE 多驱动 | 已消除：S05 U39 Y1 改名页内 `POOL_DONE`；顶层 `DONE` 只剩 S01 U1009.17 一个 74HCT541 输出 |
| 顶层审计 | `done_74hct541_outputs=1`，`done_multidriver=false`；`P1_START/P2_START/ARGMAX_START` 已从单节点列表消失 |
| 顶层 ERC | 42 errors -> 42 errors（逐条相同）；无 short / multi-driver / different_net；warnings 898 -> 899（新增 U42 备用门警告） |
| 仿真 | `sim/run_all.py` 9/9 PASS；未修改任何 testbench |
| 主工程误改 | 无（仅按任务要求在 `output/model_reviews/repair_f1f5/` 新建交付物） |

## 1. 修改点

### 1.1 F1：Pool/Argmax 阶段启动

`tools/build_pool.py`：

| 行号 | 修改 |
|---|---|
| 28 | `GLOBAL` 增加 `P1_START`、`P2_START` |
| 39 | `GLOBAL` 移除 `START`（S05 已无该负载） |
| 98-101 | 接口说明改为 `P1_START/P2_START/POOL_BUSY/P1_DONE/P2_DONE`，注明 `POOL_START = P1_START | P2_START (U42a)` |
| 503-510 | 新增 74HC32 包 **U42**：`U42a: 1=P1_START, 2=P2_START, 3=POOL_START`；`U42p` 为电源单元（7=GND, 14=+5V） |
| 513 | U36.1 启动输入 `START` -> `POOL_START` |
| 526 | U37.5 启动输入 `START` -> `POOL_START` |
| 419, 621 | FSM 注释/图面说明同步为 `POOL_START`、`S_DONE` |

位号选择：S05 原最大位号为 U41，U42 空闲；经 `renumber_refs.py` 后为 **U5042**，未与任何现有位号冲突。新增去耦电容为 C5042（每个 IC 封装一颗，沿用原规则）。

`tools/build_argmax.py`：

| 行号 | 修改 |
|---|---|
| 27 | `GLOBAL` 的 `START` -> `ARGMAX_START` |
| 101-106 | 接口说明改为 `ARGMAX_START`，结果保持到下一个 `ARGMAX_START` |
| 328 | U36b.4 `START` -> `ARGMAX_START` |
| 339 | U37b.5 `START` -> `ARGMAX_START` |
| 401-402, 409 | FSM/结果保持说明同步为 `ARGMAX_START` |

顶层接口说明/连接矩阵同步（`tools/build_top.py`）：

| 行号 | 修改 |
|---|---|
| 77-84 | S05 关键输入改为 `P1_START/P2_START`，输出移除 `DONE`；S06 输入改为 `ARGMAX_START` |
| 162-199 | `net_hints` 更新 `DONE`/`START`/`P1_START`/`P2_START`/`ARGMAX_START` 的源/目的说明 |
| 299-305 | `docs/CONNECTION_MATRIX.md` 的“审阅提示”改为修复后状态 |
| 432-437 | 根图备注改为 S05 U42 合成 `POOL_START`、S06 由 `ARGMAX_START` 启动、`DONE` 单驱动 |

`docs/HW_MANUAL.md` 293-294：S05/S06 控制/握手列由 `START` 改为 `P1_START/P2_START` 与 `ARGMAX_START`。

生成文件中的落点（副本行号）：

- `S05_Pool.kicad_sch`：U5042 36617、U5042 电源单元 36757；`P1_START` 36690、`P2_START` 36713；`POOL_START` 36736/37054/38001；U5039 Y1 的 `POOL_DONE` 41272；U5041 输入 `POOL_DONE` 41545/41685。
- `S06_Argmax.kicad_sch`：`ARGMAX_START` 32524/33331。

### 1.2 F5：Pool 本地 DONE 改名

`tools/build_pool.py`：

| 行号 | 修改 |
|---|---|
| 39 | S05 `GLOBAL` 移除 `DONE` |
| 559-568 | U39（74HCT541）Y1 `DONE` -> `POOL_DONE`；注释说明该网络为页内网络 |
| 573-578 | U41/U41b 的 `DONE` 输入 -> `POOL_DONE`；`P1_DONE/P2_DONE` 仍为全局输出 |

结果：S05 不再驱动顶层 `DONE`；`P1_DONE/P2_DONE` 功能与极性不变（`POOL_DONE & ~POOL_SEL` / `POOL_DONE & POOL_SEL`）。

## 2. 重生成命令与结果

在副本根目录依次执行，全部成功：

```bash
python tools/build_pool.py          # 95 IC units, 42 caps
python tools/build_argmax.py        # 66 IC units, 38 packages
python tools/promote_engine_status.py  # 0 labels promoted (已是 global)
python tools/renumber_refs.py       # S05 87 refs, S06 79 refs, 共 166 refs
python tools/strip_pwr_flags.py     # S05/S06 各移除 2 个 PWR_FLAG
python tools/build_top.py           # 257 nets (90 shared)
python tools/export_review.py       # 11 张图 ERC + PDF + BOM + preview
```

顶层网表导出：

```bash
"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe" sch export netlist \
  --format kicadsexpr -o output/visual_fix/after/top.net CNN_74xx_System.kicad_sch
python tools/audit_top_connectivity.py output/visual_fix/after/top.net
```

## 3. 顶层连通性审计（before/after）

任务开始时读取的旧版审计产物（旧脚本）为 `80` 个单节点网络、`2` 个 DONE 541 输出。任务执行期间主工程的 `tools/audit_top_connectivity.py` 与 `output/visual_fix/after/top.audit.json` 被其它进程更新（新增 unexpanded bus 分类），因此下表用**当前最新脚本**对主工程当前网表与修复后网表做同口径比较：

| 检查 | before（主工程当前） | after（副本） |
|---|---|---|
| `single_node_module_nets` | 93 | **90** |
| `unexpanded_bus_nets` | 27 | 27 |
| `done_541_output_count` | 2 | **1** |
| `done_multidriver` | true | **false** |
| `net_count` | 2775 | 2777 |

单节点列表的差异是精确的：

- 从列表移除：`P1_START`、`P2_START`、`ARGMAX_START`（正好 3 个）
- 新增：无

修复后关键网络节点：

| 网络 | 节点 |
|---|---|
| `P1_START` | `U1008.17`（S01 74HCT541 源） + `U5042.1`（S05 负载） |
| `P2_START` | `U1008.15`（S01 源） + `U5042.2`（S05 负载） |
| `ARGMAX_START` | `U1008.12`（S01 源） + `U6036.4`、`U6037.5`（S06 两个启动门负载） |
| `DONE` | `U1009.17`（S01 74HCT541 输出）、`U10097.3`（S10 输入）、`TP1005.1`、`TP10007.1` |
| `DONE` 的 74HCT541 输出 | 仅 `U1009.17`（`U5039.17` 已改为页内 `POOL_DONE`） |
| `START` | `U10091.9`（S10 输出缓冲）、`U1011.2`（S01 同步输入）、`TP1003/TP10003` |

`POOL_START`/`POOL_DONE` 是 S05 页内标签，不出现在顶层网表中；S05 单页网表验证其节点为：

- `/POOL_START`：`U5042.3`、`U5036.1`、`U5037.5`
- `/POOL_DONE`：`U5039.17`、`U5041.1`、`U5041.4`

## 4. 单页网络级回归（证明未改功能逻辑）

对主工程旧 S05/S06 与副本新 S05/S06 分别导出单页网表，按网络名/节点集合比较（`net_changes.txt`）：

- **S05**：208 -> 210 nets。除新增 U5042 的 `+5V/GND` 节点和 C5042 外，变化只有：
  - `START` 删除（原 `U5036.1`、`U5037.5`）；`/POOL_START` 新增（`U5042.3`、`U5036.1`、`U5037.5`）
  - `DONE` 删除；`/POOL_DONE` 新增，节点完全相同（`U5039.17`、`U5041.1`、`U5041.4`）
  - `P1_START`/`P2_START` 新增，仅接 `U5042.1/2`
  - 其余 200+ 个内部网络节点集合逐位相同
- **S06**：229 -> 229 nets。唯一变化：`START` 删除，`ARGMAX_START` 新增，节点同为 `U6036.4`、`U6037.5`。

因此没有改变任何池化/argmax 的数据通路、FSM 次态或输出逻辑。

## 5. 顶层 ERC

| 指标 | before | after |
|---|---|---|
| violations | 940 | 941 |
| errors | 42 | **42** |
| warnings | 898 | 899 |

- 42 个 error 逐条相同，全部为 `pin_not_driven`：32×`SCORE_DATA`（U6004-U6007）、8×`IN_DATA`（U5012/U5013）、`POOL_SEL`（U5005.6）、`FC_SEL`（U9005.1）。**前后无变化**。
- 两份报告中均不存在 `short`、`multi-driver`/`multiple drivers`、`different_net` 类型错误。
- 警告类型变化：`isolated_pin_label` 223 -> 220（`P1_START`/`P2_START`/`DONE` 不再孤立）；`lib_symbol_issues` 387 -> 389、`missing_input_pin` 10 -> 11、`missing_unit` 10 -> 11。后三项来自新 74HC32 包 U5042 只放置 A 门（B/C/D 备用门未放置），与现有 U5041 等包的处理方式一致，属非结构性警告；如需清零，可在后续把 U42 B/C/D 输入接地、输出 NC。
- 单页 ERC 中 S05 15 errors / S06 37 errors 仍为模块级未驱动输入，与顶层 42 个错误的统计口径不同，不构成新增结构问题。

## 6. 仿真

`python sim/run_all.py` -> **9/9 PASS**（日志：`sim_run_all.log`）：

```
PASS  lut_contents
PASS  lut_spice
PASS  glue
PASS  supervisor
PASS  timing
PASS  mem_decode
PASS  pool
PASS  argmax
PASS  conv_fc_engines
```

Pool/Argmax testbench 是行为级模型（自带 `start`/`done` 节点），不读取原理图网络名；`sim/tb_pool.cir`、`sim/tb_argmax.cir` 与修复前逐字节相同，因此没有因旧网名而失败，也无需修改 testbench。

## 7. 剩余问题（不在本任务范围）

修复后 `single_node_module_nets=90` 的构成：

- 48×引擎地址：`C1_ADDR[15:0]`、`C2_ADDR[15:0]`、`FC_ADDR[15:0]`
- 18×片选：`C1/C2/FC_MEM_nCE_*`（各 6）
- 8×`MEM_DATA[7:0]`（仅 S04 U2010 侧）
- 12×引擎本地握手：`C1/C2/FC_MEM_BUSY/DONE/nOE/nWE`
- `FC_MODE_SPARE`、`POOL_BUSY`、`ARGMAX_BUSY`、`ARGMAX_RESULT_VALID`
- 27 个未展开总线（每个引擎 9 个：`*_B_DATA[31:0]`、`*_M[31:0]`、`*_N_MACS[15:0]`、`*_SHIFT[5:0]`、`*_WAIT_READ/WRITE[3:0]`、`*_ZP_OUT/W/X`）

这些属于下一阶段 F2/F3/F4 的总线 owner/展开工作；`MEM_ACK/MEM_DONE/MEM_BUSY` 目前只存在于 S02 页内，顶层网表没有同名网络，同样留待总线修复。`POOL_BUSY`/`ARGMAX_BUSY`/`ARGMAX_RESULT_VALID` 仍为单节点，按修复计划属后续状态回送范围。

## 8. 交付物与主工程保护

本目录 `D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System/output/model_reviews/repair_f1f5/`：

| 文件 | 说明 |
|---|---|
| `REPAIR_REPORT.md` | 本报告 |
| `f1f5.patch` | 相对主工程当前文件的 unified diff（9 个文件，`a/`/`b/` 前缀，可用 `git apply` 或 `patch -p1`） |
| `top.audit.json` | 修复后顶层审计 JSON（最新脚本，90 single + 27 unexpanded，1 driver） |
| `top.audit.before.json` | 修复前主工程当前审计 JSON（93 single + 27 unexpanded，2 drivers） |
| `top.net` | 修复后顶层网表（kicadsexpr，2777 nets） |
| `top-erc-before.rpt` / `top-erc-after.rpt` | 顶层 ERC 前后报告 |
| `net_changes.txt` | S05/S06 单页网表精确差异 |
| `sim_run_all.log` | 9/9 PASS 仿真日志 |

Patch 覆盖：`tools/build_pool.py`、`tools/build_argmax.py`、`tools/build_top.py`、`docs/HW_MANUAL.md`、`docs/CONNECTION_MATRIX.md`、`output/connection_matrix.csv`、`S05_Pool.kicad_sch`、`S06_Argmax.kicad_sch`、`CNN_74xx_System.kicad_sch`。已在主工程基线文件的临时副本上执行 `patch -p1 --dry-run`，9 个文件全部检查通过。生成原理图因重建会刷新 UUID，patch 中 UUID 行有大量差异（约 1.1 MB）；功能语义差异见第 4 节与 `net_changes.txt`。

主工程保护：

- 所有构建、ERC、仿真、网表导出均在 `_repair_f1f5/work` 中完成。
- 主工程 `S05_Pool.kicad_sch`、`S06_Argmax.kicad_sch`、`CNN_74xx_System.kicad_sch`、`tools/build_pool.py`、`tools/build_argmax.py`、`tools/build_top.py` 的 mtime 仍为 2026-11-04/2026-11-05 02:xx（本任务开始前），未写入。
- S01/S02/S04/S07/S08/S09/S10/S_LUT 原理图，以及抽查的未涉及工具（build_supervisor/build_timing/build_memories/build_conv1/build_conv2/build_fc/build_top_io、sim/gen_pool_tb.py、sim/gen_argmax_tb.py）与主工程逐字节相同（SHA-256 比对）。
- 备份目录未写入。
- 说明：任务期间主工程 `output/model_reviews/` 下其它评审文件与 `tools/audit_top_connectivity.py` 被其它并发进程更新（mtime 晚于本任务开始），非本任务写入；本报告的 before 基线采用更新后的主工程审计产物，并同时记录了任务开始时的旧基线（80 single / 2 drivers）。

## 9. 主工程应用记录（2026-11-05 后续）

本报告最初记录的是隔离副本验证。随后主进程已把同一补丁应用到主工程：

```bash
cd D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System
patch -p1 < output/model_reviews/repair_f1f5/f1f5.patch   # 9 个文件全部成功
kicad-cli sch export netlist --format kicadsexpr -o output/top.net CNN_74xx_System.kicad_sch
python tools/audit_top_connectivity.py output/top.net     # 90 single / 27 bus / 1 DONE driver
python sim/run_all.py                                     # 9/9 PASS
kicad-cli sch erc --severity-all -o output/top-erc-after-f1f5.rpt CNN_74xx_System.kicad_sch
```

主工程应用后的证据：

| 检查 | 结果 |
|---|---|
| `output/top.audit.json` | `single_node_module_nets=90`、`unexpanded_bus_nets=27`、`done_541_output_count=1`、`done_multidriver=false` |
| `output/sim_run_all_after_f1f5.log` | 9/9 PASS |
| `output/top-erc-after-f1f5.rpt` | 42 errors / 899 warnings / 941 messages |
| Muse S01 harness 复跑 | 7/7 阶段连通 PASS、DONE 单驱动 PASS；仅剩 2 个 harness 采样误报 |

因此本报告第 0 节的“主工程未写入”已不再适用；补丁现已成为主工程当前状态。
