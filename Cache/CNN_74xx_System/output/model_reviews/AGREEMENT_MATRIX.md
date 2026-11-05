# 模型说法一致性矩阵（最终版）

日期：2026-11-05  
图例：`✓` = 明确报告且主进程核实；`△` = 提到但未证实/低估；`✗` = 与主进程证据冲突；`—` = 未覆盖；`?` = 无报告返回。

> 2026-11-05 更新：S17/S18 已关闭 M-09（S09 FC1/FC2 signed-32 门级化）；当前 12/12 仿真、0E/3434W、2 单节点/0 未展开总线、BOM 2845/1941/12。

| 主进程 ID | 问题 | Gemini | Muse→DeepSeek | qwen→DeepSeek 网表 | Beam | Iceman | 主进程判定 |
|---|---|---|---|---|---|---|---|
| M-01 | P1/P2/ARGMAX_START 无负载，Pool/Argmax 用通用 START | ? | ✓（3 个 stage FAIL） | ? | ✓（joint_audit FAIL） | △（F-006 minor） | 确认 blocker，已修复 |
| M-02 | Cx_ADDR/Cx_MEM_nCE 未接 S04 | ? | ✓（16×3 网 0 到达） | ? | ✓（C1/C2/FC_ADDR FAIL） | △（F-002 medium） | 确认 blocker，**已修复（S11）** |
| M-03 | MEM_DATA/ACK/DONE/BUSY 未闭环 | ? | ✓（ACK/DONE/BUSY 无消费者） | ? | ✓（MEM_ACK 等 FAIL） | △（F-001） | 确认 blocker，**已修复（S11）** |
| M-04 | DONE 双 74HCT541 驱动 | ? | ✓（FAIL） | ? | ✓（WARN） | △（F-007 minor） | 确认 blocker，已修复 |
| M-05 | Requant 参数总线未展开 | ? | — | ? | — | △（F-004 macro） | 确认 blocker；S07/S08/S09 已修复（S13–S18） |
| M-06 | S02_MEM_IF WAIT/ACK/DONE/BUSY 悬空 | ? | ✓（REQ/WE 无驱动） | ? | ✓（joint_audit FAIL） | △（F-001） | 确认 blocker，**已修复（S11）** |
| M-07 | 42 ERC 是 Pool/Argmax 数据输入断链 | ? | ✓（分类一致） | ? | ✓（0E/2479W） | △（F-005 未分类） | 确认 blocker，**已修复**：S12 + Argmax 四字节事务后顶层 0E/2479W |
| M-08 | 12 LUT 块 vs 4 lane/8 ROM | ? | — | ? | — | ✓（F-003 major） | 确认 major |
| M-09 | Requant 仅宏块 | ? | — | ? | — | ✓（F-004 major） | 确认 major；S07/S08/S09 已门级化（FC2 signed-32 四字节 LE） |
| M-10 | 10–100 Hz 下 wait/timeout/脉宽失配 | ? | — | ? | — | — | 确认 major（设计参数） |
| M-11 | BOM 490 与 18 块符号/封装缺口 | ? | ✓（861 refs/490 IC/135 无封装） | ? | — | △（BOM 提到） | 确认 major（现 2845 件/1941 IC/12 个 LUT 块） |
| M-12 | Conv2 输入 HWC vs Pool1/规格 CHW | ? | ✓（layout FAIL） | ? | — | — | 确认 blocker，已修复 |
| M-13 | S02 74HC138 五输出无负载 | ? | ✓（FAIL） | ? | — | — | 降级 low（不影响功能） |
| F-01 | S02 读写等待值接反 | ? | ✗（误报） | ? | — | — | 否定（TB 命名问题） |
| F-02 | S01 首/末状态检查失败 | ? | ✗（harness 采样错位） | ? | — | — | 否定（FSM 序列正确） |

## 逐方评价

### Gemini（`gemini-3.8-flash-high`）

- 两次运行均以 `empty_stream` 结束，报告目录为空。
- 无法评价其技术结论；不计入“已获得五份报告”。

### Muse 位（DeepSeek 独立上下文）

- 产物：`net_audit.json`、`harness_s01.log`、`harness_s02.log`、`harness_layout.log`、`commands.log`。
- 有效贡献：
  - 首先用实际导出的层次网表证实 M-01/M-04；
  - 证实 M-02/M-03/M-06 的具体节点与缺载；
  - 发现 M-12（Pool1→Conv2 地址不一致），这是其他方没有发现的真实问题；
  - 发现 M-13（S02 译码器冗余输出）。
- 错误/误报：
  - S02 等待值“接反”：TB 的 `we` 是高=读、低=写，行为与图纸一致，只是变量名反了；
  - S01 首/末状态：harness 在寄存器输出更新前/状态多走一步后采样，FSM 序列本身正确。
- 原始 `net_audit.json` 的 49 个多驱动/425 未驱动/528 单节点包含大量三态总线成员与层次命名，不能直接当故障数；主进程的 90/27 是层次感知后的结果。

### qwen 位（DeepSeek 网表专项上下文）

- 只留下 `netparse.py`，没有最终报告；无法评价。qwen3.8-flash 不在 `ListModels` 中，MiMo 也无可用渠道。

### Beam

- 实际跑完：11/11 仿真、逐页 ERC、顶层与 10 张子图网表导出、joint_audit。
- 有效贡献：独立复现 11/11、0E/2479W、M-01/M-02/M-03/M-04/M-06。
- 缺少最终 REPORT.md（API `ECONNRESET`），但 `commands.log` 与 `joint_audit.py` 足以复核其结论。
- 其 joint_audit 对 `MEM_ACK` 的期望集合写得偏宽（只要求 S02 自身），实际应要求 S02→引擎消费者；主进程按后者判定。

### Iceman

- 唯一完整落盘的报告（`REPORT.md` + `findings.json`）。
- 有效贡献：F-001/F-003/F-004 方向正确；F-006/F-007 与主进程 M-01/M-04 对应。
- 问题：
  - ERC 计数写反：实际 42 errors / 898 warnings / 940 messages，不是 940 errors / 42 warnings；
  - F-002/F-006/F-007 只写“可能/需评审”，未导出网表；主进程已证实并升级为 blocker；
  - F-005 未分类；主进程已分为 32（S06 D0–D7）+ 8（S05 A0–A3）+ U5005.P2 + U9005.S；
  - “all tests pass”只覆盖模块级行为，不能作为系统连通性的证明。

## 结论

- 五方中没有任何一方给出“可以制板”的完整证据；Iceman 的“全部通过”是模块级结论，Beam/Muse 的网表审计才暴露系统级断链。
- 主进程接受：M-01–M-13 中除 M-13 降级外的全部问题；否定 F-01/F-02 两项误报。
- 已修复：M-01、M-04（F1/F5 patch）、M-12（CHW 地址修复）、M-02/M-03/M-06（S11 总线适配层）、M-07 的数据输入与 Argmax 四字节事务（S12/S06/S04/S11，顶层 ERC 归零）。  
- 未修复：M-08、M-10/M-11/M-13，以及 S09 本地 FSM 微码镜像。
- S12 效果：单节点模块网 4→3、顶层 ERC 40E→0E；Argmax 四字节事务由 S06/S04/S11 闭环；S17/S18 后单节点 2/未展开 0，`sim/run_all.py` 12/12；证据在 `repair_s12/`、`repair_argmax4/`、`repair_requant/`、`repair_fc_requant/`。
