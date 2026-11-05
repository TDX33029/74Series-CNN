# 五模型联合审查与主进程评估（最终）

日期：2026-11-05  
状态：**已完成可完成部分**。Gemini 两次 `empty_stream`，Beam/Muse-slot/qwen-slot 最终 `ECONNRESET`；Iceman 完整报告已返回。详细逐项证据见 `FINAL_JOINT_REVIEW.md` 与 `AGREEMENT_MATRIX.md`。

## 1. 审查范围与方法

- 工程：`D:/Document/tempPrj/74Series-CNN/Cache/CNN_74xx_System`
- 规划书：`CNN_74xx_MNIST_28x28_v1.txt`
- 共享 brief：`docs/MODEL_REVIEW_BRIEF.md`
- 每个审查员在独立副本运行 `python sim/run_all.py` 和关键单项测试，并至少做两种联合逻辑验证。
- 主进程独立审计：`tools/audit_top_connectivity.py` + 顶层 netlist 解析，不依赖模型结论。

## 2. 模型可用性与替代

| 审查位 | 用户指定 | 实际 | 状态 |
|---|---|---|---|
| 1 | gemini-3.8-flash-high | Gemini 3.8 Flash High | 两次 `empty_stream`，无报告 |
| 2 | muse-spark-1.3-contributor | provider `invalid_request`；改用会话模型 DeepSeek 独立上下文 | 证据完整，无最终 REPORT |
| 3 | qwen3.8-flash | 未配置；MiMo 无渠道；改用会话模型 DeepSeek 独立网表专项 | 只有 netparse.py |
| 4 | beam-free | Beam Free | 9/9、ERC、netlist、joint_audit 齐全；最终 `ECONNRESET`，无 REPORT |
| 5 | iceman-contributor-free | Iceman Contributor Free | 完成 |

provider 侧问题不是审查脚本问题。第 2、3 位用会话模型补足，并在报告中明确标注替代关系。

## 3. Iceman 报告评估

| Iceman 说法 | 主进程核对 | 结论 |
|---|---|---|
| `sim/run_all.py` 9/9 PASS | 历史与副本结果一致；模块级行为测试通过 | 认可，但只覆盖模块级 |
| 顶层 ERC “940 Errors / 42 Warnings / 898” | 实际 940 messages / 42 errors / 898 warnings；数字顺序写反 | 部分错误，需更正 |
| F-001 共享 S02 vs 3 个 S02_MEM_IF 占位符 | 与主进程审计一致 | 认可，major |
| F-002 引擎到 S04 的可达性“unclear” | 已确认 C1/C2/FC_ADDR 与 Cx_MEM_nCE_* 共 48+18 个单节点网络未接 S04 | 认可，升级 blocker |
| F-003 12 LUT 块 vs 4 lane/8 ROM | 与架构审计一致 | 认可，major |
| F-004 Requant 宏块未展开 | 与符号/文档一致；单块约 95–117 片 | 认可，major |
| F-005 42 pin_not_driven 需分类 | 已分类：32 个 S06 D0–D7、8 个 S05 A0–A3、U5005.P2、U9005.S | 认可方向，升级 blocker |
| F-006 START 同时到 S01/S05/S06 | 已确认；F1 修复完成 | 认可，升级 blocker，已修复 |
| F-007 DONE 可能多驱动 | 已确认 U1009.17 + U5039.17；F5 修复完成 | 认可，升级 blocker，已修复 |

## 4. 其他审查员的增量贡献

- **Muse 位（DeepSeek）**：用实际层次网表复现 M-01/M-02/M-03/M-04/M-06；**新发现 M-12（Pool1→Conv2 地址布局不一致）** 和 M-13（S02 译码器冗余输出）；两项误报（S02 等待值、S01 harness 采样）已在最终报告中否定。
- **Beam**：独立复现 9/9、42E/898W、joint_audit 的 M-01/M-02/M-03/M-04/M-06；无最终报告。
- **Gemini/qwen 位**：没有可用结论，不计入证据。

## 5. 主进程确认的问题与修复状态

| ID | 问题 | 状态 |
|---|---|---|
| M-01 | P1/P2/ARGMAX_START 未到 S05/S06 | **已修复**（F1） |
| M-02 | Cx_ADDR/Cx_MEM_nCE 未接 S04 | 未修复 |
| M-03 | MEM_DATA/ACK/DONE/BUSY 未闭环 | 未修复 |
| M-04 | DONE 双 74HCT541 驱动 | **已修复**（F5） |
| M-05 | Requant 参数总线未展开 | 未修复 |
| M-06 | S02_MEM_IF REQ/WE/ACK/DONE/BUSY 悬空 | 未修复 |
| M-07 | 42 个顶层 ERC 是 Pool/Argmax 数据输入断链 | 未修复（已分类） |
| M-08 | 12 LUT 块 vs 4 lane/8 ROM | 未修复 |
| M-09 | Requant 仅宏块 | 未修复 |
| M-10 | 10–100 Hz 与 wait/timeout/脉宽失配 | 未修复 |
| M-11 | BOM 490 不含 18 个未展开块 | 未修复 |
| M-12 | Conv2 输入 HWC vs 规格 CHW | **已修复** |
| M-13 | S02 74HCT138 五输出无负载 | 降级 low |

## 6. 修复状态

- F1/F5 已应用到主工程，网表审计 93→90 单节点、DONE 2→1 驱动，9/9 仿真通过，ERC 42 errors 不变。
- M-12 已应用并验证（9/9、layout harness PASS）。
- M-02/M-03/M-05/M-06/M-07 是下一阶段的总线/Requant 工作，不能靠小补丁解决。

## 7. 结论

当前模块级 SPICE 全部通过，但顶层联合逻辑存在确定的断链和多驱动，不能仅凭 9/9 认为可制板。Iceman 的报告方向正确但证据不足；主进程的 netlist 审计已把关键问题从“可能”升级为可复现的 blocker。详细结论、误报解释和修复顺序见 `FINAL_JOINT_REVIEW.md`。
