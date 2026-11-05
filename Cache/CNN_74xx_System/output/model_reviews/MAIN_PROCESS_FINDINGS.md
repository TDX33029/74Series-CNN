# 主进程独立网表审计（候选发现，待与五份模型报告对照）

日期：2026-11-05
证据：`output/visual_fix/after/top.net`（2775 nets / 10007 nodes / 861 components）
方法：解析顶层 netlist 的 net→node 成员，检查跨模块 START/DONE、引擎地址/片选、S02 应答、S04 数据总线。

> 2026-11-05 后续状态：本文记录的 F1（阶段 START）和 F5（DONE 双驱动）已修复并应用到主工程；M-12（Conv2 HWC→CHW）也已修复。当前 `output/top.audit.json` 为 **90 个单节点模块网 / 27 个未展开总线 / 1 个 DONE 驱动**。F2/F3/F4 仍未修复，正在按 `docs/BUS_FABRIC_REPAIR_PLAN.md` 设计 S11 总线适配层。本文保留原始审计证据，不再作为当前状态快照。

## 候选问题

### F1. P1_START / P2_START / ARGMAX_START 只有源端，没有目的端

- `P1_START`：仅 `U1008.17`（S01 74HCT541 输出）
- `P2_START`：仅 `U1008.15`
- `ARGMAX_START`：仅 `U1008.12`
- 但 `START` 网络连接了 `U5036.1/U5037.5/U6036.4/U6037.5`（Pool/Argmax 的启动门），说明 S05/S06 实际用的是通用 `START`，不是 S01 的阶段启动脉冲。
- 影响：Supervisor 进入 P1/P2/ARGMAX 阶段时，Pool/Argmax 不会被该阶段脉冲启动；它们可能被主机 START 直接触发。属于功能/握手错误，优先级 blocker（待模型确认）。

### F2. 引擎地址与片选只在本页，未接到 S04

- `C1_ADDR0..15` 每个网络只有 1 个节点（U7147 的 Q 输出）。
- `C2_ADDR0..15` 每个只有 1 个节点（U8150）。
- `FC_ADDR0..15` 每个只有 1 个节点（U9137）。
- `C1_MEM_nCE_IN/W/OUT/B/Q/MC`、`C2_*`、`FC_*` 每个只有 1 个节点（U7146/U8149/U9136 输出）。
- S04 的 `ADDR0..23` 只连接 S10 的 U10093 和 S04 的 U4040；`MEM_SEL0..4` 只连接 S10/S04。
- 影响：引擎运行时的存储访问没有进入 S04 地址/片选网络，实际只能靠主机加载路径；联合逻辑不完整。blocker（待确认）。

### F3. S02 的 MEM_DATA / ACK / DONE / BUSY 没有接回引擎或 S04

- `MEM_DATA0..7` 每个只有 1 个节点（U2010 的 B 侧引脚），未连接到 S04 的 `DATA0..7` 或 `MEM_D0..7`。
- `MEM_ACK`：`U2005.15` + `TP2007`；`MEM_DONE`：`U2005.14` + `TP2008`；`MEM_BUSY`：`U2005.13` + `TP2009`。没有引擎侧接收端。
- 影响：S02 事务应答/数据没有形成闭环。blocker（待确认）。

### F4. POOL/ARGMAX 状态没有回到 Supervisor/主机

- `POOL_BUSY` 仅 `U5039.16`。
- `ARGMAX_BUSY` 仅 `U6038.11`。
- `ARGMAX_RESULT_VALID` 仅 `U6034.11`。
- `P1_DONE/P2_DONE` 有接 S01 微码 ROM，`ARGMAX_DONE` 也有；但 BUSY/RESULT_VALID 没有到 S01/S10。
- 影响：状态可见性和结果有效握手可能缺失；至少是 major。

### F5. `DONE` 网络有多个输出候选

- `DONE` 网络节点：`TP10007.1`、`TP1005.1`、`U1009.17`、`U10097.3`、`U5039.17`、`U5041.1`、`U5041.4`。
- U1009（S01 状态缓冲）、U10097（S10 状态缓冲）、U5039（S05 状态缓冲）都可能是 74HCT541 输出；若 OE 同时有效，会多驱动。
- 需要检查三片 541 的 OE 是否互斥；若互斥，则是三态共享，不是错误。暂列 major，待确认。

### F6. `START` 网络同时接主机与 Pool/Argmax 启动门

- `START` 节点：`TP10003.1`、`TP1003.1`、`U10091.9`、`U1011.2`、`U5036.1`、`U5037.5`、`U6036.4`、`U6037.5`。
- 如果 S01 也把 `START` 当作全局启动，而 S05/S06 直接用它，可能与阶段启动冲突；与 F1 相关。

## 复现命令与量化结果

```bash
cd D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System
python tools/audit_top_connectivity.py output/visual_fix/after/top.net
```

输出（`output/visual_fix/after/top.audit.json`）：

```json
{
  "single_node_module_nets": 93,
  "unexpanded_bus_nets": 27,
  "done_74hct541_outputs": [["U1009","17","74HCT541"], ["U5039","17","74HCT541"]],
  "done_multidriver": true
}
```

- 93 个单节点标量模块边界网络；27 个“有总线标签但没有位成员”的未展开总线（Requant 参数 + S02 WAIT 总线）。
- 27 个未展开总线：`C1/C2/FC_B_DATA[31:0]`、`M[31:0]`、`SHIFT[5:0]`、`ZP_X/W/OUT[15:0]`、`N_MACS[15:0]`、`WAIT_READ[3:0]`、`WAIT_WRITE[3:0]`。
- `C1_ACC[31:0]` 不在此列：它的位成员 `C1_ACC0..31` 存在且各有 3 个节点，说明 ACC 总线实际接通。
- `C1_OUT_DATA0..7` 的两个候选驱动：U7126 是 574 输出，U7127 是 245 的 A 侧（A->B 方向时 A 为输入）；这是三态/方向问题，不能仅凭网表节点判为双驱动。主进程不把它列为已确认错误。
- 引擎的 `C1_MEM_REQ/WE`、`Cx_WAIT_READ/WRITE`、`Cx_MEM_ACK/DONE/BUSY` 只存在于 S07–S09 页内，未进入顶层网表；说明引擎到共享 S02/S04 的请求/应答链路整体缺失，不只是地址线没接。

## DeepSeek 网表专项（第 5 位）初步结果

其 `output/model_reviews/muse-slot-session-model/net_audit.json` / `net_audit_stdout.txt` 给出：

- 861 components / 2775 nets；49 个“多驱动”候选、425 个未驱动输入候选、528 个单节点网络。
- `DONE` 两个 74HCT541 输出：`U1009.17`、`U5039.17`（与主进程一致）。
- Requant 块输入并非全部悬空，需要区分总线成员：
  - `C1_ACC[31:0]` 是总线标签，成员 `C1_ACC0..31` 实际存在（例如 `C1_ACC0` 有 U7079.5/U7087.19/U7091.1 三个节点），所以 ACC 是接上的；
  - `C1_B_DATA[31:0]`、`C1_M[31:0]`、`C1_SHIFT[5:0]`、`C1_ZP_X/W/OUT[15:0]`、`C1_N_MACS[15:0]` 没有对应的位成员网络，块引脚是孤立的（U7123.9-15）；这些才是真断链；
  - `C2_*`/`FC_*` 同样。
- S02_MEM_IF 侧：
  - `C1_WAIT_READ[3:0]`/`C1_WAIT_WRITE[3:0]` 没有位成员网络，块输入孤立；
  - `C1_MEM_nOE/nWE`（U7145.8/9）、`C1_MEM_DONE/BUSY`（U7145.11/12）单节点输出；
  - `C1_MEM_nCE_*` 单节点输出，未接 S04；
  - `C1_MEM_ACK` 只连到 U7136/U7137 微码 ROM 地址脚和 U7145.10，没有 S02 源，属于“有负载但无源”。
- 因此 DeepSeek 报告里“Requant 所有输入悬空”应修正为“ACC 已接，其余参数总线未接”；“S02_MEM_IF 全部未接”基本成立，但 ACK 有局部负载。
- `C1_OUT_DATA0..7` 的两个候选驱动：U7126 是 574 输出，U7127 是 245 的 A 侧（A->B 方向时 A 为输入）；这是三态/方向问题，不能仅凭网表节点判为双驱动。主进程不把它列为已确认错误。
- `MEM_D0..7`、`DATA0..7` 的“多驱动”包含大量三态存储器/245 输出；必须结合片选/OE 判断，不能全部认定为错误。
- 其余单节点包括 `C1_REQ_BUSY/SAT_FLAG` 等 Requant 输出、`C1_MEM_*`、`C1_WAIT_*`；这些是真实的未连接或未使用，不是三态总线。

## 顶层 ERC 42 errors 的真实分类

此前文档/报告把 42 个 `pin_not_driven` 说成“顶层外部输入未驱动”，这是错误的。实际报告：

- 32 个：`/S06_Argmax/` 的 U6004/U6005/U6006/U6007 的 D0..D7（SCORE_DATA 输入寄存器）全部未驱动。
- 8 个：`/S05_Pool/` 的 U5012/U5013 的 A0..A3（比较器/数据输入）未驱动。
- 1 个：`/S05_Pool/` U5005 Pin 6 P2。
- 1 个：`/S09_FC/` U9005 Pin 1 S。
- 另有 `missing_input_pin` 警告（U5041 未放置单元 C/D、U9016 未放置单元 D/E/F），不是错误计数。

因此 42 errors 的主体是 **Pool/Argmax 数据输入断链**，不是外部连接器。主进程已确认，Iceman 的 F-005 “需分类”方向正确但未分类；文档中的“外部输入”说法需要更正。

## 待模型报告对照

- 五个审查员会独立跑 `sim/run_all.py`、ERC/netlist 审计和联合逻辑 harness；上述发现只有在他们的证据或主进程复现实验都支持时才进入修复清单。
- 修复顺序建议：先修 F1/F2/F3（联合逻辑断链），再处理 F4/F5/F6 的状态/多驱动，最后再谈 LUT/S02/Requant 的层次展开。
