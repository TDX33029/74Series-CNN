# 审查与修复报告索引

日期：2026-11-05  
主工程：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System`

## 先看这三个

1. **`FINAL_JOINT_REVIEW.md`** — 五模型/替代上下文审查的最终结论、逐项判定、误报解释、剩余风险。
2. **`AGREEMENT_MATRIX.md`** — 每个问题在各模型/主进程之间的一致性矩阵。
3. **`../pdf/CNN_74xx_Review_Package.pdf`** — S13–S18 集成后的总评审包：手册、18 张模块图、状态矩阵、连接矩阵、F1/F5/M-12/S11/S12/Argmax/Requant/FC-Requant 修复报告。

## 模型报告与证据

| 目录 | 内容 | 状态 |
|---|---|---|
| `iceman-contributor-free/` | `REPORT.md`、`findings.json`、`commands.log` | 完整报告 |
| `beam-free/` | 顶层/子图网表、ERC、`commands.log`、`joint_audit.py` | 证据完整，最终 API `ECONNRESET`，无 REPORT |
| `muse-slot-session-model/` | `net_audit.json`、S01/S02/layout harness 与日志 | 证据完整，无最终 REPORT；发现 M-12/M-13 |
| `qwen-slot-netlist-review/` | `netparse.py` | 未完成 |
| `gemini-3.8-flash-high/` | 空 | 两次 `empty_stream` |

模型可用性/替代关系：`MODEL_ASSIGNMENTS.md`。  
主进程原始审计：`MAIN_PROCESS_FINDINGS.md`、`main_findings.json`、`../top.audit.json`。

## 修复报告

| 目录 | 内容 | 状态 |
|---|---|---|
| `repair_f1f5/` | START/DONE 修复：patch、前后网表审计、ERC、9/9 日志、REPAIR_REPORT | 已应用到主工程 |
| `repair_m12/` | Conv2 HWC→CHW 修复：patch、REPAIR_REPORT、位级穷举/布局 harness 证据 | 已应用到主工程 |
| `repair_bus/` | S11 总线适配层（M-02/M-03/M-06；M-07 选择信号）：patch、REPAIR_REPORT、审计/ERC/harness 日志 | 已应用到主工程 |
| `repair_s12/` | S12 数据拼装（M-07 数据输入）：Pool 541 缓冲、Argmax 4×574 + 74HC238、ERC/仿真证据 | 已应用到主工程 |
| `repair_argmax4/` | Argmax 四字节事务：S06 字节计数/{class,byte}、S04 地址缓冲、S11 master、S12 MEM_ACK 锁存 | 已应用到主工程 |
| `repair_requant/` | S07/S08 Requant 门级展开：S13/S15 核心、S14/S16 参数装载、103 项 TB、顶层 0E | 已应用到主工程 |
| `repair_fc_requant/` | S09 FC1/FC2 门级展开：S17 signed-32 核心、S18 装载器、FC2 四字节 LE、81 项 TB | 已应用到主工程 |

## 设计/后续方案

- `docs/BUS_FABRIC_REPAIR_PLAN.md`：S11 总线层（master/region 编码、27C512 映射 ROM、ADDR/MEM_SEL/REQ/WE/ACK 分发）。
- `docs/REQUANT_LUT_EXPANSION_PLAN.md`：Requant 门级展开的原始估算（单块约 95–117 片，3 块约 300–350 片）；实际 S13/S15 各 429 片、S17 510 片，差异见 `repair_requant/REPAIR_REPORT.md` 与 `repair_fc_requant/REPAIR_REPORT.md`。LUT lane 映射仍待完成。
- `docs/HW_MANUAL.md`：S01 监督 FSM、S02 时序控制器、各模块说明。
- `docs/FINAL_STATUS.md`：当前逐图 ERC/仿真/修复状态。

## 当前结论

- 12/12 模块级仿真通过；S13–S18 集成后顶层 ERC **0E/3434W**，单节点模块网 2、未展开总线 0，**仍不能据此投板**。
- 已修复：M-01（阶段 START）、M-04（DONE 双驱动）、M-12（Conv2 HWC→CHW）、M-02/M-03/M-06（S11 总线）、M-07 数据输入与 Argmax 四字节事务（S12/S06/S04/S11）、M-05 的 S07/S08 部分（S13/S14/S15/S16）、M-09（S17/S18 FC signed-32）。
- 未修复：M-08（LUT）、M-10（10–100 Hz 时序）、M-11（12 个 LUT 块符号/BOM 封装）、M-13（S02 未用译码输出）；S09 本地 FSM 微码镜像尚未导出。
